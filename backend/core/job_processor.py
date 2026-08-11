"""Async Job Processor — manages background jobs for ingestion, clustering, and RAG.

Provides thread-pool / async background task execution with pollable status.
"""
import concurrent.futures
import datetime
import json
import uuid
from typing import Callable, Dict, Any, Optional

from backend.config import Config
from backend.models.database import JobRecord, SessionLocal, init_db
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Executor for background tasks
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)


def create_job(run_id: str, job_type: str) -> str:
    """Create a new job record in the database.

    Args:
        run_id: Run UUID identifier.
        job_type: Type of job ('ingestion', 'clustering', 'rag').

    Returns:
        Generated job UUID string.
    """
    job_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        job = JobRecord(
            id=job_id,
            run_id=run_id,
            job_type=job_type,
            status='queued',
            progress=0.0
        )
        db.add(job)
        db.commit()
        logger.info("Created job %s (%s) for run %s", job_id, job_type, run_id)
        return job_id
    finally:
        db.close()


def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve job status from the database.

    Args:
        job_id: Job UUID string.

    Returns:
        Dict with job status fields or None if not found.
    """
    db = SessionLocal()
    try:
        job = db.query(JobRecord).filter(JobRecord.id == job_id).first()
        if not job:
            return None
        return {
            "job_id": job.id,
            "run_id": job.run_id,
            "job_type": job.job_type,
            "status": job.status,
            "progress": job.progress,
            "result": json.loads(job.result_json) if job.result_json else None,
            "error": job.error_message,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        }
    finally:
        db.close()


def submit_async_job(job_id: str, fn: Callable, *args, **kwargs) -> None:
    """Submit a task function to the background thread pool.

    Args:
        job_id: Job UUID.
        fn: Target function to execute.
    """
    _executor.submit(_run_job_wrapper, job_id, fn, *args, **kwargs)


def _run_job_wrapper(job_id: str, fn: Callable, *args, **kwargs) -> None:
    """Internal wrapper that updates database job status upon completion or error."""
    db = SessionLocal()
    try:
        job = db.query(JobRecord).filter(JobRecord.id == job_id).first()
        if job:
            job.status = 'processing'
            job.progress = 0.2
            db.commit()

        # Execute actual task logic
        result = fn(*args, **kwargs)

        job = db.query(JobRecord).filter(JobRecord.id == job_id).first()
        if job:
            job.status = 'completed'
            job.progress = 1.0
            job.result_json = json.dumps(result) if result is not None else None
            db.commit()
            logger.info("Job %s completed successfully", job_id)

    except Exception as e:
        logger.error("Job %s failed: %s", job_id, e)
        job = db.query(JobRecord).filter(JobRecord.id == job_id).first()
        if job:
            job.status = 'failed'
            job.error_message = str(e)
            db.commit()
    finally:
        db.close()
