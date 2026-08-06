import os
import uuid
import shutil
from fastapi import UploadFile
from app.config import settings


def save_upload(file: UploadFile) -> tuple:
    """
    Save an uploaded file to the storage directory.
    Returns (file_path, file_size).
    """
    # Create storage directory if it doesn't exist
    os.makedirs(settings.STORAGE_PATH, exist_ok=True)

    # Generate unique filename
    file_extension = os.path.splitext(file.filename)[1] or ".mp4"
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(settings.STORAGE_PATH, unique_filename)

    # Save file
    total_size = 0
    with open(file_path, "wb") as buffer:
        while chunk := file.file.read(8192):
            buffer.write(chunk)
            total_size += len(chunk)

    return file_path, total_size


def get_upload_path(upload_id: str) -> str:
    """Get the file path for an upload by ID."""
    # This would normally query the database
    # For now, we'll search the storage directory
    storage_path = settings.STORAGE_PATH
    if not os.path.exists(storage_path):
        raise FileNotFoundError(f"Storage directory not found: {storage_path}")

    # Find file starting with upload_id
    for filename in os.listdir(storage_path):
        if filename.startswith(upload_id):
            return os.path.join(storage_path, filename)

    raise FileNotFoundError(f"Upload not found: {upload_id}")


def create_temp_dir(prefix: str = "") -> str:
    """Create a temporary directory for processing."""
    temp_base = os.path.join(settings.STORAGE_PATH, "temp")
    os.makedirs(temp_base, exist_ok=True)

    temp_dir = os.path.join(temp_base, f"{prefix}{uuid.uuid4()}")
    os.makedirs(temp_dir, exist_ok=True)

    return temp_dir


def cleanup_temp_dir(temp_dir: str):
    """Remove a temporary directory and its contents."""
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)
