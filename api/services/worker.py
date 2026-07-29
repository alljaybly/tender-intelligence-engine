import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from .job_store import get_job, update_job

logger = logging.getLogger(__name__)

# Dedicated thread pool for blocking Selenium work.
# max_workers=2 prevents spawning too many Chrome instances simultaneously.
_SCRAPE_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="scraper")


async def process_job(job_id: str, filename: str, cost_per_hour: float):
    logger.info(f"[JOB] job_id=%s status=processing", job_id)
    
    update_job(job_id, status="processing")
    
    try:
        steps = ["extraction", "validation", "pricing"]
        for step in steps:
            logger.info(f"[STEP] {step}")
            update_job(job_id, progress=step)
            await asyncio.sleep(0.5)
        
        update_job(
            job_id,
            status="complete",
            result={
                "summary": "Processed successfully",
                "price_estimate": cost_per_hour * 10
            }
        )
        logger.info(f"[JOB] job_id=%s status=complete", job_id)
    except Exception as e:
        update_job(job_id, status="failed", error=str(e))
        logger.info(f"[JOB] job_id=%s status=failed", job_id)


def _run_scrape_tenders(job_id: str) -> None:
    """
    Blocking function executed inside a thread-pool worker.
    Imports scrape_tenders here to avoid importing Selenium at module load time.
    Updates the job store with progress and final results.
    """
    from .scraper import scrape_tenders  # local import keeps Selenium out of the main thread

    logger.info("[SCRAPE_JOB] job_id=%s status=processing", job_id)
    update_job(job_id, status="processing", progress="scraping")

    try:
        tenders = scrape_tenders() or []
        update_job(
            job_id,
            status="complete",
            progress="done",
            result={
                "total": len(tenders),
                "tenders": tenders,
            },
        )
        logger.info("[SCRAPE_JOB] job_id=%s status=complete tenders=%d", job_id, len(tenders))
    except Exception as exc:
        logger.exception("[SCRAPE_JOB] job_id=%s status=failed error=%s", job_id, exc)
        update_job(job_id, status="failed", progress="error", error=str(exc))


async def run_scrape_job(job_id: str) -> None:
    """
    Async wrapper that offloads the blocking Selenium scrape to the thread-pool
    executor so the FastAPI event loop is never blocked.
    """
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(_SCRAPE_EXECUTOR, _run_scrape_tenders, job_id)
