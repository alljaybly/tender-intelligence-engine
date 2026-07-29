"""
Tender model — represents an uploaded tender document in the processing pipeline.
"""
from typing import Any, Dict, Optional


class Tender:
    """
    Lightweight Tender model mapped to the `tenders` SQLite table.

    Attributes match DB columns directly to keep the model simple
    without requiring SQLAlchemy or an ORM.
    """
    TABLE_NAME = "tenders"

    __slots__ = (
        "id", "job_id", "user_id", "filename", "original_filename",
        "file_hash", "mime_type", "file_size", "status",
        "pipeline_version", "created_at", "updated_at", "completed_at",
    )

    def __init__(
        self,
        id: int = 0,
        job_id: str = "",
        user_id: str = "",
        filename: str = "",
        original_filename: str = "",
        file_hash: str = "",
        mime_type: str = "",
        file_size: int = 0,
        status: str = "queued",
        pipeline_version: str = "v1",
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        completed_at: Optional[str] = None,
    ):
        self.id = id
        self.job_id = job_id
        self.user_id = user_id
        self.filename = filename
        self.original_filename = original_filename
        self.file_hash = file_hash
        self.mime_type = mime_type
        self.file_size = file_size
        self.status = status
        self.pipeline_version = pipeline_version
        self.created_at = created_at
        self.updated_at = updated_at
        self.completed_at = completed_at

    def to_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self.__slots__}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Tender":
        return cls(**{k: data.get(k) for k in cls.__slots__})

    # SQL DDL — called during init_db
    DDL = """
        CREATE TABLE IF NOT EXISTS tenders (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id            TEXT UNIQUE NOT NULL,
            user_id           TEXT,
            filename          TEXT,
            original_filename TEXT,
            file_hash         TEXT DEFAULT '',
            mime_type         TEXT DEFAULT '',
            file_size         INTEGER DEFAULT 0,
            status            TEXT DEFAULT 'queued',
            pipeline_version  TEXT DEFAULT 'v1',
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at      TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_tenders_job_id ON tenders(job_id);
        CREATE INDEX IF NOT EXISTS idx_tenders_user_id ON tenders(user_id);
        CREATE INDEX IF NOT EXISTS idx_tenders_status ON tenders(status);
        CREATE INDEX IF NOT EXISTS idx_tenders_file_hash ON tenders(file_hash);
    """