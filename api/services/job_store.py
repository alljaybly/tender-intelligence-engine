import threading
from datetime import datetime
from typing import Dict, Any, Optional

_JOBS: Dict[str, Dict[str, Any]] = {}
_LOCK = threading.Lock()


def create_job(job_id: str) -> Dict[str, Any]:
    with _LOCK:
        entry = {
            'job_id': job_id,
            'status': 'queued',
            'progress': 'starting',
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'result': None,
            'error': None
        }
        _JOBS[job_id] = entry
        return entry


def update_job(job_id: str, **kwargs) -> Optional[Dict[str, Any]]:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return None
        job.update(kwargs)
        job['updated_at'] = datetime.utcnow().isoformat()
        return job


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with _LOCK:
        job = _JOBS.get(job_id)
        return dict(job) if job else None
