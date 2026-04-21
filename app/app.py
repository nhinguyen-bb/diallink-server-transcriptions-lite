import asyncio
import json
import os
import sys
import traceback
import uuid
from pathlib import Path
from typing import Optional

import torch
from fastapi import Depends, FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from utils.common import verify_api_key
from utils.constants import ASR_COMPUTE_TYPE, ASR_DEVICE, DEFAULT_MODEL_TYPE, UPLOAD_DIR
from utils.database import create_job, get_all_jobs, get_job, get_stale_jobs, init_db, shutdown_db, update_job_status
from utils.exceptions import UserException
from utils.logger import app_logger
from utils.s3 import audio_exists, upload_audio

app = FastAPI()

WORKER_SCRIPT = Path(__file__).parent / "worker.py"
MAX_CONCURRENT_WORKERS = int(os.getenv("MAX_CONCURRENT_WORKERS", "2"))
_worker_semaphore = asyncio.Semaphore(MAX_CONCURRENT_WORKERS)


@app.on_event("startup")
async def startup():
    await init_db()
    await _recover_stale_jobs()


async def _recover_stale_jobs():
    stale_jobs = await get_stale_jobs()
    for job in stale_jobs:
        s3_key = job["audio_path"]
        if s3_key and audio_exists(s3_key):
            app_logger.info(f"Recovering stale job: {job['id']}")
            await update_job_status(job["id"], "queued", progress=0)
            asyncio.create_task(_spawn_worker(str(job["id"]), "", s3_key, job["request_params"]))
        else:
            app_logger.warning(f"Marking stale job {job['id']} as failed: audio file missing from S3")
            await update_job_status(job["id"], "failed", error="Audio file missing from S3")


@app.on_event("shutdown")
async def shutdown():
    await shutdown_db()


@app.get("/healthz")
async def health_check():
    try:
        gpu_available = torch.cuda.is_available()
        gpu_count = torch.cuda.device_count() if gpu_available else 0
        gpu_name = torch.cuda.get_device_name(0) if gpu_available else None

        return {
            "status": "healthy",
            "default_model": DEFAULT_MODEL_TYPE,
            "device": ASR_DEVICE,
            "compute_type": ASR_COMPUTE_TYPE,
            "gpu_available": gpu_available,
            "gpu_count": gpu_count,
            "gpu_name": gpu_name,
        }
    except Exception as e:
        app_logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
        }


@app.post("/v1/transcriptions", dependencies=[Depends(verify_api_key)])
async def transcribe(
    file: UploadFile,
    model: str = Form(DEFAULT_MODEL_TYPE),
    prompt: Optional[str] = Form(""),
    response_format: str = Form("json", enum=["json", "text", "verbose_json"]),
    temperature: float = Form(0.0, ge=0.0, le=1.0),
    language: Optional[str] = Form("en"),
    diarize: bool = Form(False),
    min_speakers: Optional[int] = Form(None),
    max_speakers: Optional[int] = Form(None),
):
    app_logger.info(f"Transcription request received for file: {file.filename}")

    if not file.filename.endswith((".wav", ".mp3", ".flac")):
        app_logger.warning(f"Unsupported file format: {file.filename}")
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Please upload a valid audio file.",
        )

    job_id = uuid.uuid4()
    ext = os.path.splitext(file.filename)[-1]
    s3_key = f"audio/{job_id}{ext}"
    local_path = os.path.join(UPLOAD_DIR, f"{job_id}{ext}")

    try:
        content = await file.read()
        if not content:
            app_logger.error("Uploaded file is empty.")
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        with open(local_path, "wb") as f:
            f.write(content)

        upload_audio(s3_key, content)
        app_logger.info(f"Saved audio locally and to S3: {s3_key}")

        request_params = json.dumps({
            "model": model,
            "prompt": prompt,
            "response_format": response_format,
            "temperature": temperature,
            "language": language,
            "diarize": diarize,
            "min_speakers": min_speakers,
            "max_speakers": max_speakers,
        })

        await create_job(job_id, s3_key, request_params)

        asyncio.create_task(_spawn_worker(str(job_id), local_path, s3_key, request_params))

        return JSONResponse(
            status_code=202,
            content={
                "job_id": str(job_id),
                "status": "queued",
            },
        )

    except HTTPException:
        raise
    except UserException as e:
        app_logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        app_logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error submitting transcription job: {str(e)}")


async def _spawn_worker(job_id: str, local_path: str, s3_key: str, params_json: str):
    async with _worker_semaphore:
        app_logger.info(f"Worker slot acquired for job {job_id}")
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, str(WORKER_SCRIPT), job_id, local_path, s3_key, params_json,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if stdout:
                app_logger.info(stdout.decode().strip())
            if stderr:
                app_logger.warning(stderr.decode().strip())
            if proc.returncode != 0:
                app_logger.error(f"Worker process for job {job_id} exited with code {proc.returncode}")
        except Exception as e:
            app_logger.error(f"Failed to spawn worker for job {job_id}: {e}")


@app.get("/v1/transcriptions", dependencies=[Depends(verify_api_key)])
async def list_transcription_jobs(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    jobs = await get_all_jobs(status=status, limit=limit, offset=offset)
    return {
        "jobs": [
            {
                "job_id": str(job["id"]),
                "status": job["status"],
                "progress": job["progress"],
                "processing_time": job["processing_time"],
                "created_at": job["created_at"].isoformat(),
                "updated_at": job["updated_at"].isoformat(),
            }
            for job in jobs
        ],
        "limit": limit,
        "offset": offset,
    }


@app.get("/v1/transcriptions/results", dependencies=[Depends(verify_api_key)])
async def list_transcription_results(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    jobs = await get_all_jobs(status=status, limit=limit, offset=offset)
    return {
        "jobs": [
            {
                "job_id": str(job["id"]),
                "status": job["status"],
                "progress": job["progress"],
                "result": (json.loads(job["result"]) if isinstance(job["result"], str) else job["result"]) if job["result"] else None,
                "error": job["error"] if job["status"] == "failed" else None,
                "processing_time": job["processing_time"],
                "created_at": job["created_at"].isoformat(),
                "updated_at": job["updated_at"].isoformat(),
            }
            for job in jobs
        ],
        "limit": limit,
        "offset": offset,
    }


@app.get("/v1/transcriptions/{job_id}", dependencies=[Depends(verify_api_key)])
async def get_transcription_status(job_id: str):
    try:
        uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id format.")

    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    response = {
        "job_id": str(job["id"]),
        "status": job["status"],
        "progress": job["progress"],
        "processing_time": job["processing_time"],
        "created_at": job["created_at"].isoformat(),
        "updated_at": job["updated_at"].isoformat(),
    }

    if job["status"] == "failed":
        response["error"] = job["error"]

    return response


@app.get("/v1/transcriptions/{job_id}/result", dependencies=[Depends(verify_api_key)])
async def get_transcription_result(job_id: str):
    try:
        uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id format.")

    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    response = {
        "job_id": str(job["id"]),
        "status": job["status"],
        "progress": job["progress"],
        "processing_time": job["processing_time"],
        "result": None,
    }

    if job["status"] == "failed":
        response["error"] = job["error"]
    elif job["status"] == "completed":
        response["result"] = json.loads(job["result"]) if isinstance(job["result"], str) else job["result"]

    return response
