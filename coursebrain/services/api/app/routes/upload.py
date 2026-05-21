from fastapi import APIRouter, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db, Upload
from app.schemas import UploadResponse
from app.utils.storage import save_upload
import os

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("", response_model=UploadResponse)
async def create_upload(file: UploadFile = File(...), db: Session = None):
    """
    Upload a video file for analysis.
    Returns an upload_id that can be used to create an analysis job.
    """
    if db is None:
        db = next(get_db())

    # Validate file type
    allowed_types = ["video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}",
        )

    # Save the file
    try:
        file_path, file_size = save_upload(file)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    # Create database record
    upload = Upload(
        filename=file.filename,
        file_path=file_path,
        file_size=file_size,
        content_type=file.content_type,
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)

    return UploadResponse(
        upload_id=upload.id,
        filename=upload.filename,
        size_bytes=upload.file_size,
    )
