import os
from datetime import datetime, timezone

import databases

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://transcription_dev:KsCMxF669GyX@localhost:5432/transcription_dev")

database = databases.Database(DATABASE_URL)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS transcription_jobs (
    id UUID PRIMARY KEY,
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    progress INT NOT NULL DEFAULT 0,
    request_params JSONB,
    result JSONB,
    error TEXT,
    audio_path TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""

CREATE_INDEX_SQL = """CREATE INDEX IF NOT EXISTS idx_transcription_jobs_status ON transcription_jobs(status)"""

ADD_PROCESSING_TIME_SQL = """ALTER TABLE transcription_jobs ADD COLUMN IF NOT EXISTS processing_time FLOAT"""


async def init_db():
    await database.connect()
    await database.execute(CREATE_TABLE_SQL)
    await database.execute(CREATE_INDEX_SQL)
    await database.execute(ADD_PROCESSING_TIME_SQL)


async def shutdown_db():
    await database.disconnect()


async def create_job(job_id, audio_path, request_params):
    query = """
        INSERT INTO transcription_jobs (id, status, progress, request_params, audio_path, created_at, updated_at)
        VALUES (:id, 'queued', 0, :request_params, :audio_path, :now, :now)
    """
    now = datetime.now(timezone.utc)
    await database.execute(query, {
        "id": str(job_id),
        "request_params": request_params,
        "audio_path": audio_path,
        "now": now,
    })


async def update_job_status(job_id, status, progress=None, result=None, error=None, processing_time=None):
    parts = ["status = :status", "updated_at = :now"]
    values = {"id": str(job_id), "status": status, "now": datetime.now(timezone.utc)}

    if progress is not None:
        parts.append("progress = :progress")
        values["progress"] = progress
    if result is not None:
        parts.append("result = :result")
        values["result"] = result
    if error is not None:
        parts.append("error = :error")
        values["error"] = error
    if processing_time is not None:
        parts.append("processing_time = :processing_time")
        values["processing_time"] = processing_time

    query = f"UPDATE transcription_jobs SET {', '.join(parts)} WHERE id = :id"
    await database.execute(query, values)


async def get_job(job_id):
    query = "SELECT * FROM transcription_jobs WHERE id = :id"
    return await database.fetch_one(query, {"id": str(job_id)})


async def get_stale_jobs():
    query = "SELECT * FROM transcription_jobs WHERE status IN ('queued', 'processing') ORDER BY created_at ASC"
    return await database.fetch_all(query)


async def get_all_jobs(status=None, limit=50, offset=0):
    if status:
        query = "SELECT * FROM transcription_jobs WHERE status = :status ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        return await database.fetch_all(query, {"status": status, "limit": limit, "offset": offset})
    query = "SELECT * FROM transcription_jobs ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
    return await database.fetch_all(query, {"limit": limit, "offset": offset})
