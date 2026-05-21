from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db, Upload, AnalysisJob
from app.schemas import CreateJobRequest, JobStatusResponse
from app.workers.analyze_video import analyze_video_task

router = APIRouter(prefix="/analysis-jobs", tags=["analysis-jobs"])


@router.post("", response_model=JobStatusResponse)
async def create_analysis_job(request: CreateJobRequest, db: Session = None):
    """
    Create a new analysis job for an uploaded video.
    The job will be processed asynchronously by a Celery worker.
    """
    if db is None:
        db = next(get_db())

    # Verify upload exists
    upload = db.query(Upload).filter(Upload.id == request.upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    # Create job record
    job = AnalysisJob(
        upload_id=request.upload_id,
        course_title=request.course_title,
        target_learner=request.target_learner,
        lesson_objective=request.lesson_objective,
        difficulty=request.difficulty,
        quiz_questions=request.quiz_questions or [],
        status="queued",
        current_step="Queued for processing",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Queue Celery task
    analyze_video_task.delay(job.id)

    return JobStatusResponse(
        job_id=job.id,
        status="queued",
        progress=0,
        current_step="Queued for processing",
    )


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str, db: Session = None):
    """
    Get the status of an analysis job.
    """
    if db is None:
        db = next(get_db())

    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        current_step=job.current_step,
        error_message=job.error_message,
    )
