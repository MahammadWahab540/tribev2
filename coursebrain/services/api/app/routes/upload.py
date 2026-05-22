from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from app.db import get_db, Upload
from app.schemas import UploadResponse
from app.utils.storage import save_upload
from app.config import settings
import os

router = APIRouter(prefix="/uploads", tags=["uploads"])

# Allowed video content types
ALLOWED_CONTENT_TYPES = [
    "video/mp4",
    "video/quicktime",
    "video/x-msvideo",
    "video/webm",
    "video/x-matroska",
]

# Allowed file extensions
ALLOWED_EXTENSIONS = [".mp4", ".mov", ".avi", ".webm", ".mkv"]


@router.post("", response_model=UploadResponse)
async def create_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a video file for analysis.
    Returns an upload_id that can be used to create an analysis job.
    """
    # Validate file type by content-type header
    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_CONTENT_TYPES)}",
        )

    # Validate file extension
    if file.filename:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file extension. Allowed extensions: {', '.join(ALLOWED_EXTENSIONS)}",
            )
    else:
        raise HTTPException(status_code=400, detail="Filename is required")

    # Check file size if possible (some clients don't send content_length)
    if file.size and file.size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE / (1024*1024):.0f}MB",
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
        content_type=file.content_type or "video/mp4",
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)

    return UploadResponse(
        upload_id=upload.id,
        filename=upload.filename,
        size_bytes=upload.file_size,
    )


@router.get("/{upload_id}", response_model=dict)
async def get_upload_info(upload_id: str, db: Session = Depends(get_db)):
    """
    Get metadata about an uploaded video.
    """
    upload = db.query(Upload).filter(Upload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    return {
        "upload_id": upload.id,
        "filename": upload.filename,
        "size_bytes": upload.file_size,
        "content_type": upload.content_type,
        "duration_seconds": upload.duration_seconds,
        "stream_url": f"/api/uploads/{upload_id}/stream",
    }


@router.get("/{upload_id}/stream")
async def stream_video(upload_id: str, db: Session = Depends(get_db)):
    """
    Stream an uploaded video file.
    """
    from fastapi.responses import FileResponse

    upload = db.query(Upload).filter(Upload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    if not os.path.exists(upload.file_path):
        raise HTTPException(status_code=404, detail="Video file not found")

    return FileResponse(
        upload.file_path,
        media_type=upload.content_type,
        filename=upload.filename,
    )
