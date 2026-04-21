import asyncio
import json
import os
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
import boto3

S3_BUCKET = os.getenv("S3_BUCKET", "diallink-transcription-audio")
S3_REGION = os.getenv("AWS_REGION", "us-east-1")
s3_client = boto3.client("s3", region_name=S3_REGION)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://transcription_dev:transcription_dev@localhost:5432/transcription_dev")
DSN = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


async def update_job(conn, job_id, status, progress=None, result=None, error=None, processing_time=None):
    parts = ["status = $1", "updated_at = $2"]
    values = [status, datetime.now(timezone.utc)]
    idx = 3

    if progress is not None:
        parts.append(f"progress = ${idx}")
        values.append(progress)
        idx += 1
    if result is not None:
        parts.append(f"result = ${idx}")
        values.append(result)
        idx += 1
    if error is not None:
        parts.append(f"error = ${idx}")
        values.append(error)
        idx += 1
    if processing_time is not None:
        parts.append(f"processing_time = ${idx}")
        values.append(processing_time)
        idx += 1

    values.append(job_id)
    query = f"UPDATE transcription_jobs SET {', '.join(parts)} WHERE id = ${idx}"
    await conn.execute(query, *values)


def run_transcription(audio_path_str, params):
    import torch
    from faster_whisper import WhisperModel

    model_name = params.get("model", os.getenv("WHISPER_MODEL", "medium"))
    device = os.getenv("ASR_DEVICE")
    if not device:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = os.getenv("ASR_COMPUTE_TYPE")
    if not compute_type:
        compute_type = "float16" if device == "cuda" else "int8"

    model = WhisperModel(model_name, device=device, compute_type=compute_type)

    transcribe_kwargs = {}
    if params.get("prompt"):
        transcribe_kwargs["initial_prompt"] = params["prompt"]
    if params.get("language"):
        transcribe_kwargs["language"] = params["language"]
    if params.get("temperature", 0.0) > 0.0:
        transcribe_kwargs["temperature"] = params["temperature"]

    segments_generator, info = model.transcribe(audio_path_str, **transcribe_kwargs)

    segments = []
    for seg in segments_generator:
        segments.append({
            "start": seg.start,
            "end": seg.end,
            "text": seg.text.strip(),
            "words": [{"word": w.word, "start": w.start, "end": w.end, "probability": w.probability} for w in (seg.words or [])],
        })

    if params.get("diarize") and segments:
        segments = _apply_diarization(audio_path_str, segments, params, device)

    transcription = " ".join([seg["text"] for seg in segments])

    if not transcription:
        raise ValueError("No transcription text returned by the model.")

    audio_duration = info.duration
    if not audio_duration and segments:
        audio_duration = max(seg["end"] for seg in segments)

    response_format = params.get("response_format", "json")
    temperature = params.get("temperature", 0.0)

    if response_format == "json":
        return {
            "text": transcription,
            "usage": {
                "type": "tokens",
                "input_tokens": 14,
                "input_token_details": {"text_tokens": 10, "audio_tokens": 4},
                "output_tokens": len(transcription.split()),
                "total_tokens": 14 + len(transcription.split()),
            },
        }
    elif response_format == "text":
        return {"text": transcription}
    elif response_format == "verbose_json":
        verbose = {
            "task": "transcribe",
            "language": info.language or params.get("language", "en"),
            "duration": audio_duration,
            "text": transcription,
            "segments": [],
            "usage": {"type": "duration", "seconds": int(audio_duration) if audio_duration else 0},
        }
        for i, seg in enumerate(segments):
            fs = {
                "id": i,
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"],
                "temperature": temperature,
            }
            if "speaker" in seg:
                fs["speaker"] = seg["speaker"]
            verbose["segments"].append(fs)
        return verbose

    return {"text": transcription}


def _apply_diarization(audio_path_str, segments, params, device):
    try:
        from pyannote.audio import Pipeline

        hf_token = os.getenv("HUGGINGFACE_ACCESS_TOKEN")
        import torch

        pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=hf_token)
        pipeline.to(torch.device(device))

        diarize_kwargs = {}
        if params.get("min_speakers") is not None:
            diarize_kwargs["min_speakers"] = params["min_speakers"]
        if params.get("max_speakers") is not None:
            diarize_kwargs["max_speakers"] = params["max_speakers"]

        diarization = pipeline(audio_path_str, **diarize_kwargs)

        diarize_segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            diarize_segments.append({"start": turn.start, "end": turn.end, "speaker": speaker})

        for seg in segments:
            seg_mid = (seg["start"] + seg["end"]) / 2
            best_speaker = None
            best_overlap = 0.0
            for dseg in diarize_segments:
                overlap_start = max(seg["start"], dseg["start"])
                overlap_end = min(seg["end"], dseg["end"])
                overlap = max(0.0, overlap_end - overlap_start)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_speaker = dseg["speaker"]
            if best_speaker is None:
                for dseg in diarize_segments:
                    if dseg["start"] <= seg_mid <= dseg["end"]:
                        best_speaker = dseg["speaker"]
                        break
            if best_speaker:
                seg["speaker"] = best_speaker

    except Exception as e:
        print(f"Diarization failed: {e}", file=sys.stderr)

    return segments


async def main(job_id, local_path, s3_key, params_json):
    params = json.loads(params_json)
    conn = await asyncpg.connect(DSN)

    try:
        await update_job(conn, job_id, "processing", progress=10)
        start_time = time.time()

        if local_path and Path(local_path).exists():
            print(f"Using local file: {local_path}")
        else:
            suffix = os.path.splitext(s3_key)[-1] or ".wav"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            s3_client.download_fileobj(S3_BUCKET, s3_key, tmp)
            tmp.close()
            local_path = tmp.name
            print(f"Downloaded from S3: {s3_key} -> {local_path}")

        job_result = run_transcription(local_path, params)

        elapsed = time.time() - start_time
        print(f"Transcription completed for job: {job_id} in {elapsed:.2f}s")

        await update_job(conn, job_id, "completed", progress=100, result=json.dumps(job_result), processing_time=round(elapsed, 2))

    except Exception as e:
        print(f"Job {job_id} failed: {traceback.format_exc()}", file=sys.stderr)
        await update_job(conn, job_id, "failed", error=str(e))

    finally:
        await conn.close()
        if local_path and Path(local_path).exists():
            try:
                os.remove(local_path)
            except Exception as cleanup_error:
                print(f"Failed to delete local file {local_path}: {cleanup_error}", file=sys.stderr)
        try:
            s3_client.delete_object(Bucket=S3_BUCKET, Key=s3_key)
            print(f"Deleted S3 audio: {s3_key}")
        except Exception as s3_error:
            print(f"Failed to delete S3 audio {s3_key}: {s3_error}", file=sys.stderr)


if __name__ == "__main__":
    job_id = sys.argv[1]
    local_path = sys.argv[2]
    s3_key = sys.argv[3]
    params_json = sys.argv[4]
    asyncio.run(main(job_id, local_path, s3_key, params_json))
