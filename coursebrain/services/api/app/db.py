from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, JSON, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import uuid
from app.config import settings

Base = declarative_base()

engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Upload(Base):
    __tablename__ = "uploads"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    content_type = Column(String, nullable=False)
    duration_seconds = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    jobs = relationship("AnalysisJob", back_populates="upload")


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    upload_id = Column(String, ForeignKey("uploads.id"), nullable=False)
    course_title = Column(String, nullable=True)
    target_learner = Column(String, nullable=True)
    lesson_objective = Column(String, nullable=True)
    difficulty = Column(String, nullable=True)  # beginner, intermediate, advanced
    quiz_questions = Column(JSON, nullable=True, default=list)
    status = Column(String, default="queued")  # queued, processing, completed, failed
    progress = Column(Integer, default=0)
    current_step = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    upload = relationship("Upload", back_populates="jobs")
    report = relationship("Report", back_populates="job", uselist=False)


class Report(Base):
    __tablename__ = "reports"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("analysis_jobs.id"), unique=True, nullable=False)
    coursebrain_score = Column(Float, nullable=True)
    summary = Column(Text, nullable=True)
    video_duration_seconds = Column(Float, nullable=True)
    metrics = Column(JSON, nullable=True)
    timeline = Column(JSON, nullable=True)
    issues = Column(JSON, nullable=True)
    quiz_alignment = Column(JSON, nullable=True)
    disclaimer = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("AnalysisJob", back_populates="report")


def init_db():
    Base.metadata.create_all(bind=engine)
