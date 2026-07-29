import asyncio
import uuid
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ..services.job_store import create_job, get_job
from ..services.worker import run_scrape_job

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/scrape")
async def scrape():
    """
    Kick off a background scrape job and return a job_id immediately.
    Selenium runs in a thread-pool executor — the FastAPI event loop is never blocked.
    Poll /api/status/{job_id} to check progress.
    Retrieve final data from /api/results/{job_id} once status == 'complete'.
    """
    job_id = uuid.uuid4().hex
    create_job(job_id)

    logger.info("[SCRAPE] Queued scrape job job_id=%s", job_id)

    # Fire-and-forget: schedules the coroutine on the running event loop.
    # run_scrape_job offloads blocking Selenium work to a ThreadPoolExecutor.
    asyncio.create_task(run_scrape_job(job_id))

    return JSONResponse(
        status_code=202,
        content={
            "status": "queued",
            "job_id": job_id,
            "message": "Scrape job started. Poll /api/status/{job_id} for progress, "
                       "then fetch /api/results/{job_id} when complete.",
        },
    )


@router.get("/results/{job_id}")
def get_results(job_id: str):
    """
    Return the scraped tender data for a completed scrape job.
    Returns 404 if the job does not exist.
    Returns 202 with current status if the job is still running.
    Returns 200 with full tender list once the job is complete.
    Returns 500 with error detail if the job failed.
    """
    job = get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    status = job.get("status")

    if status == "complete":
        result = job.get("result") or {}
        return JSONResponse(
            status_code=200,
            content={
                "job_id": job_id,
                "status": "complete",
                "total": result.get("total", 0),
                "tenders": result.get("tenders", []),
            },
        )

    if status == "failed":
        return JSONResponse(
            status_code=500,
            content={
                "job_id": job_id,
                "status": "failed",
                "error": job.get("error", "Unknown error"),
            },
        )

    # Still queued or processing
    return JSONResponse(
        status_code=202,
        content={
            "job_id": job_id,
            "status": status,
            "progress": job.get("progress"),
            "message": "Job is still running. Try again shortly.",
        },
    )
