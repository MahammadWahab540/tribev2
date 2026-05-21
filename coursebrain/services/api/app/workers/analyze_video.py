from celery import Task
from app.main import celery_app
from app.db import SessionLocal, AnalysisJob, Report, Upload
from app.utils.storage import get_upload_path, create_temp_dir, cleanup_temp_dir
from app.utils.ffmpeg import get_video_duration, extract_audio, sample_frames
from app.analyzers.audio_analyzer import AudioAnalyzer
from app.analyzers.transcript_analyzer import TranscriptAnalyzer
from app.analyzers.visual_analyzer import VisualAnalyzer
from app.analyzers.tribe_analyzer import TribeAnalyzer
from app.analyzers.issue_detector import IssueDetector
from app.analyzers.llm_reporter import LLMReporter
from app.analyzers.scoring import Scorer
from app.config import settings
from datetime import datetime
import json


@celery_app.task(bind=True, max_retries=0)
def analyze_video_task(self, job_id: str):
    """
    Celery task to analyze a video and generate a CourseBrain report.
    """
    db = SessionLocal()

    try:
        # Get job
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        # Update status
        job.status = "processing"
        job.current_step = "Starting analysis"
        job.progress = 5
        db.commit()

        # Get video path
        upload = db.query(Upload).filter(Upload.id == job.upload_id).first()
        video_path = upload.file_path

        # Create temp directory for processing
        temp_dir = create_temp_dir(prefix=f"job_{job_id}_")

        try:
            # Step 1: Get video duration
            job.current_step = "Analyzing video metadata"
            db.commit()
            duration = get_video_duration(video_path)
            upload.duration_seconds = duration
            db.commit()

            # Step 2: Extract audio and transcribe
            job.current_step = "Extracting audio"
            job.progress = 15
            db.commit()

            audio_analyzer = AudioAnalyzer(model_size="base")
            audio_result = audio_analyzer.analyze_audio(video_path, temp_dir)

            job.current_step = "Transcribing speech"
            job.progress = 25
            db.commit()

            # Step 3: Analyze transcript
            transcript_analyzer = TranscriptAnalyzer()
            segments = audio_result["transcript"].get("segments", [])
            windows = transcript_analyzer.analyze_segments(
                segments, window_size=settings.TRANSCRIPT_WINDOW_SIZE
            )

            # Step 4: Sample frames and analyze visuals
            job.current_step = "Sampling video frames"
            job.progress = 40
            db.commit()

            frame_dir = create_temp_dir(prefix="frames_")
            frame_paths = sample_frames(
                video_path, frame_dir, interval_seconds=settings.VIDEO_SAMPLE_INTERVAL
            )

            visual_analyzer = VisualAnalyzer()
            frame_results = visual_analyzer.analyze_frames(frame_paths)

            # Get timestamps for frames
            frame_timestamps = [
                i * settings.VIDEO_SAMPLE_INTERVAL for i in range(len(frame_paths))
            ]
            visual_metrics = visual_analyzer.compute_visual_metrics(
                frame_results, frame_timestamps
            )

            # Map visual metrics to windows
            visual_per_window = _map_visual_to_windows(
                frame_results, frame_timestamps, windows
            )

            job.current_step = "Analyzing visual content"
            job.progress = 50
            db.commit()

            # Step 5: Run TribeV2 analysis (with fallback)
            job.current_step = "Running neuro-signal analysis"
            job.progress = 60
            db.commit()

            tribe_analyzer = TribeAnalyzer(
                cache_folder=settings.TRIBE_CACHE_FOLDER,
                device=settings.TRIBE_DEVICE,
            )
            tribe_result = tribe_analyzer.analyze_video(video_path)

            tribe_features = tribe_result.get("features", [])
            tribe_available = tribe_result.get("available", False)
            tribe_summary = tribe_analyzer.compute_summary(tribe_features)

            # Align tribe features to windows
            tribe_per_window = tribe_analyzer.align_to_windows(tribe_features, windows)

            job.current_step = "Detecting instructional risks"
            job.progress = 75
            db.commit()

            # Step 6: Detect issues
            issue_detector = IssueDetector()
            candidate_issues = issue_detector.detect_issues(
                windows=windows,
                tribe_metrics=tribe_per_window,
                visual_metrics=visual_per_window,
                context={
                    "course_title": job.course_title,
                    "target_learner": job.target_learner,
                    "lesson_objective": job.lesson_objective,
                    "difficulty": job.difficulty,
                },
            )

            # Step 7: Generate refined issues with LLM
            job.current_step = "Generating report"
            job.progress = 85
            db.commit()

            llm_reporter = LLMReporter(
                api_key=settings.OPENAI_API_KEY,
                model=settings.LLM_MODEL,
                base_url=settings.LLM_BASE_URL,
            )

            global_metrics = {
                **audio_result["metrics"],
                **visual_metrics,
                "tribe_signal_available": tribe_available,
                "tribe_signal_summary": tribe_summary,
            }

            final_issues = llm_reporter.generate_issues(
                course_title=job.course_title or "",
                target_learner=job.target_learner or "",
                lesson_objective=job.lesson_objective or "",
                difficulty=job.difficulty or "intermediate",
                global_metrics=global_metrics,
                timeline_windows=windows,
                quiz_questions=job.quiz_questions or [],
                candidate_issues=candidate_issues,
            )

            # Step 8: Calculate scores
            scorer = Scorer()

            # Enrich windows with scores
            for i, window in enumerate(windows):
                tribe_m = tribe_per_window[i] if i < len(tribe_per_window) else {}
                visual_m = visual_per_window[i] if i < len(visual_per_window) else {}
                scores = scorer.calculate_window_scores(window, tribe_m)
                window.update(scores)
                window["tribe_activation_energy"] = tribe_m.get(
                    "tribe_activation_energy"
                )
                window["tribe_signal_variation"] = tribe_m.get("tribe_signal_variation")
                window["issue_count"] = sum(
                    1
                    for issue in final_issues
                    if issue["start_sec"] <= window["start_sec"]
                    and issue["end_sec"] >= window["end_sec"]
                )

            # Calculate overall score
            quiz_alignment = _compute_quiz_alignment(
                job.quiz_questions or [], windows
            )

            overall_score = scorer.calculate_overall_score(
                timeline=windows,
                issues=final_issues,
                quiz_alignment_score=quiz_alignment["score"],
            )

            summary = scorer.generate_summary(overall_score, final_issues, global_metrics)

            # Step 9: Save report
            job.current_step = "Saving report"
            job.progress = 95
            db.commit()

            disclaimer = (
                "CourseBrain provides instructional-design risk signals. "
                "It does not diagnose learners or measure individual attention, "
                "comprehension, or learning outcomes. "
                "TribeV2 signal is a research prototype under CC-BY-NC-4.0 license."
            )

            report = Report(
                job_id=job.id,
                coursebrain_score=overall_score,
                summary=summary,
                disclaimer=disclaimer,
                video_duration_seconds=duration,
                metrics={
                    "avg_speech_rate_wpm": global_metrics.get("avg_speech_rate_wpm", 0),
                    "pause_frequency_per_min": global_metrics.get(
                        "pause_frequency_per_min", 0
                    ),
                    "avg_slide_text_density": global_metrics.get(
                        "avg_text_density", 0
                    ),
                    "visual_change_rate_per_min": global_metrics.get(
                        "visual_change_rate_per_min", 0
                    ),
                    "tribe_signal_available": tribe_available,
                    "tribe_signal_summary": tribe_summary if tribe_available else None,
                },
                timeline=windows,
                issues=final_issues,
                quiz_alignment=quiz_alignment,
            )
            db.add(report)

            # Mark job as completed
            job.status = "completed"
            job.progress = 100
            job.current_step = "Analysis complete"
            job.completed_at = datetime.utcnow()
            db.commit()

        finally:
            # Cleanup temp directories
            cleanup_temp_dir(temp_dir)

    except Exception as e:
        # Mark job as failed
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if job:
            job.status = "failed"
            job.error_message = str(e)
            job.current_step = f"Failed: {str(e)}"
            db.commit()
        raise

    finally:
        db.close()


def _map_visual_to_windows(
    frame_results: list, frame_timestamps: list, windows: list
) -> list:
    """Map visual metrics to timeline windows."""
    visual_per_window = []

    for window in windows:
        # Find frames in this window
        matching_indices = [
            i
            for i, ts in enumerate(frame_timestamps)
            if window["start_sec"] <= ts < window["end_sec"]
        ]

        if matching_indices:
            # Average metrics for frames in window
            avg_text_density = sum(
                frame_results[i]["text_density"] for i in matching_indices
            ) / len(matching_indices)
            text = " ".join(frame_results[i].get("ocr_text", "") for i in matching_indices)
            visual_per_window.append(
                {
                    "text_density": avg_text_density,
                    "ocr_text": text[:500],  # Limit length
                }
            )
        else:
            visual_per_window.append({"text_density": 0, "ocr_text": ""})

    return visual_per_window


def _compute_quiz_alignment(
    quiz_questions: list, windows: list
) -> dict:
    """Compute alignment between quiz questions and video content."""
    if not quiz_questions:
        return {
            "score": 100,
            "matched_questions": [],
        }

    matched = []
    for question in quiz_questions:
        # Simple keyword matching (in production, use semantic search)
        question_words = set(question.lower().split())
        best_match = None
        best_score = 0
        best_timestamps = []

        for window in windows:
            window_text = window.get("text", "").lower()
            window_words = set(window_text.split())

            # Calculate overlap
            overlap = len(question_words & window_words)
            if overlap > best_score:
                best_score = overlap
                best_match = window
                best_timestamps = [
                    {"start_sec": window["start_sec"], "end_sec": window["end_sec"]}
                ]

        covered = best_score >= 2  # At least 2 matching words
        matched.append(
            {
                "question": question,
                "covered_in_video": covered,
                "evidence_timestamps": best_timestamps if covered else [],
                "comment": (
                    f"Found {best_score} matching terms in video"
                    if covered
                    else "No clear coverage detected in video"
                ),
            }
        )

    # Calculate score
    covered_count = sum(1 for m in matched if m["covered_in_video"])
    score = (covered_count / len(quiz_questions) * 100) if quiz_questions else 100

    return {
        "score": score,
        "matched_questions": matched,
    }
