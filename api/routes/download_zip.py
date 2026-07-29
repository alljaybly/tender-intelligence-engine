import os
import io
import zipfile
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List

router = APIRouter()
logger = logging.getLogger(__name__)


class ZipDownloadRequest(BaseModel):
    paths: List[str]


@router.post("/download-zip")
async def download_zip(req: ZipDownloadRequest):
    """
    Accept a list of absolute file paths on the server and bundle them
    into a single ZIP file streamed back to the client.
    """
    if not req.paths:
        raise HTTPException(status_code=400, detail="No file paths provided")

    buf = io.BytesIO()

    try:
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for filepath in req.paths:
                normalized = os.path.normpath(filepath)
                if not os.path.isfile(normalized):
                    logger.warning("[ZIP] File not found, skipping: %s", normalized)
                    continue

                # Use the filename (basename) as the archive entry name to avoid
                # leaking the full server path structure.
                arcname = os.path.basename(normalized)
                if not arcname:
                    continue

                # Handle duplicate filenames by prepending a parent folder name
                zf.write(normalized, arcname=arcname)

                logger.info("[ZIP] Added: %s", normalized)
    except Exception as e:
        logger.exception("[ZIP] Failed to create archive: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to create ZIP: {e}")

    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="tender-documents.zip"'},
    )