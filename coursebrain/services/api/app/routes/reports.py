from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db, Report, AnalysisJob
from app.schemas import ReportResponse

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{job_id}", response_model=ReportResponse)
async def get_report(job_id: str, db: Session = None):
    """
    Get the full CourseBrain report for a completed analysis job.
    """
    if db is None:
        db = next(get_db())

    # Check if job exists and is completed
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed. Current status: {job.status}",
        )

    # Get report
    report = db.query(Report).filter(Report.job_id == job_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return ReportResponse(
        coursebrain_score=report.coursebrain_score,
        summary=report.summary,
        disclaimer=report.disclaimer,
        video_duration_seconds=report.video_duration_seconds,
        metrics=report.metrics,
        timeline=report.timeline,
        issues=report.issues,
        quiz_alignment=report.quiz_alignment,
    )
