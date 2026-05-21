from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime


# Upload schemas
class UploadResponse(BaseModel):
    upload_id: str
    filename: str
    size_bytes: int


# Job schemas
class CreateJobRequest(BaseModel):
    upload_id: str
    course_title: Optional[str] = None
    target_learner: Optional[str] = None
    lesson_objective: Optional[str] = None
    difficulty: Optional[Literal["beginner", "intermediate", "advanced"]] = None
    quiz_questions: Optional[List[str]] = Field(default_factory=list)


class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "processing", "completed", "failed"]
    progress: int
    current_step: Optional[str] = None
    error_message: Optional[str] = None


# Report schemas
class TimelineWindow(BaseModel):
    start_sec: float
    end_sec: float
    clarity_score: float
    pacing_score: float
    cognitive_load_score: float
    engagement_score: float
    visual_audio_alignment_score: float
    tribe_activation_energy: Optional[float] = None
    tribe_signal_variation: Optional[float] = None
    transcript_excerpt: str
    detected_concepts: List[str]
    issue_count: int


class Issue(BaseModel):
    id: str
    type: Literal[
        "cognitive_load",
        "passive_stretch",
        "visual_audio_overload",
        "unclear_explanation",
        "pacing_issue",
        "missing_example",
        "jargon_burst",
        "quiz_mismatch",
        "objective_mismatch",
        "accessibility",
    ]
    severity: Literal["low", "medium", "high"]
    start_sec: float
    end_sec: float
    title: str
    diagnosis: str
    evidence: List[str]
    recommended_fix: str
    rewrite_example: str
    confidence: float


class QuizAlignmentQuestion(BaseModel):
    question: str
    covered_in_video: bool
    evidence_timestamps: List[Dict[str, float]]
    comment: str


class QuizAlignment(BaseModel):
    score: float
    matched_questions: List[QuizAlignmentQuestion]


class TribeSignalSummary(BaseModel):
    avg_activation_energy: float
    low_variation_windows: int
    high_variation_windows: int


class Metrics(BaseModel):
    avg_speech_rate_wpm: float
    pause_frequency_per_min: float
    avg_slide_text_density: float
    visual_change_rate_per_min: float
    tribe_signal_available: bool
    tribe_signal_summary: Optional[TribeSignalSummary] = None


class ReportResponse(BaseModel):
    coursebrain_score: float
    summary: str
    disclaimer: str
    video_duration_seconds: float
    metrics: Metrics
    timeline: List[TimelineWindow]
    issues: List[Issue]
    quiz_alignment: QuizAlignment
