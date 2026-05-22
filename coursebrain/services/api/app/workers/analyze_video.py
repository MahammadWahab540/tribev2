from celery import Task
from app.celery_app import celery_app
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
import os


@celery_app.task(bind=True, max_retries=0)
def analyze_video_task(self, job_id: str):
    """
    Celery task to analyze a video and generate a CourseBrain report.
    Supports MOCK_ANALYSIS mode for fast demos without heavy models.
    """
    db = SessionLocal()
    frame_dir = None  # Track frame directory for cleanup

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
            # MOCK ANALYSIS MODE - Fast demo without heavy models
            if settings.MOCK_ANALYSIS:
                _run_mock_analysis(job, upload, video_path, db, temp_dir)
                return

            # REAL ANALYSIS MODE

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
            job.current_step = "Running multimodal signal analysis"
            job.progress = 60
            db.commit()

            tribe_available = False
            tribe_features = []
            tribe_summary = {
                "avg_activation_energy": 0.0,
                "low_variation_windows": 0,
                "high_variation_windows": 0,
            }
            tribe_per_window = [{} for _ in windows]

            if settings.ENABLE_TRIBE:
                try:
                    tribe_analyzer = TribeAnalyzer(
                        cache_folder=settings.TRIBE_CACHE_FOLDER,
                        device=settings.TRIBE_DEVICE,
                    )
                    tribe_result = tribe_analyzer.analyze_video(video_path)

                    tribe_features = tribe_result.get("features", [])
                    tribe_available = tribe_result.get("available", False)
                    if tribe_available:
                        tribe_summary = tribe_analyzer.compute_summary(tribe_features)
                        tribe_per_window = tribe_analyzer.align_to_windows(
                            tribe_features, windows
                        )
                except Exception as e:
                    # TribeV2 failure should not fail the whole job
                    job.current_step = f"TribeV2 unavailable: {str(e)}"
                    db.commit()

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
                window["tribe_signal_variation"] = tribe_m.get(
                    "tribe_signal_variation"
                )
                # Fix: Use overlap detection instead of strict containment
                window["issue_count"] = sum(
                    1
                    for issue in final_issues
                    if _overlaps(issue, window)
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
            if frame_dir:
                cleanup_temp_dir(frame_dir)

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


def _overlaps(issue: dict, window: dict) -> bool:
    """Check if an issue overlaps with a window."""
    return (
        issue["start_sec"] < window["end_sec"]
        and issue["end_sec"] > window["start_sec"]
    )


def _run_mock_analysis(
    job: AnalysisJob, upload: Upload, video_path: str, db, temp_dir: str
):
    """
    Run mock analysis for fast demos without heavy models.
    Generates deterministic fake transcript/timeline/issues based on video duration.
    """
    job.current_step = "Running mock analysis (MOCK_ANALYSIS enabled)"
    db.commit()

    # Get video duration
    duration = get_video_duration(video_path)
    upload.duration_seconds = duration
    db.commit()

    # Generate mock windows (30-second intervals)
    window_size = settings.TRANSCRIPT_WINDOW_SIZE
    windows = []
    current_time = 0.0
    while current_time < duration:
        end_time = min(current_time + window_size, duration)
        windows.append(
            {
                "start_sec": current_time,
                "end_sec": end_time,
                "text": f"Mock transcript segment from {current_time:.0f}s to {end_time:.0f}s. This is placeholder content for demonstration purposes.",
                "detected_concepts": ["concept_a", "concept_b"] if current_time < duration / 2 else ["concept_c"],
            }
        )
        current_time = end_time

    # Generate mock issues scaled to video duration
    # Scale timestamps proportionally to fit within video duration
    mock_issue_templates = [
        {
            "type": "cognitive_load",
            "title": "High cognitive-load risk",
            "diagnosis": "Three new concepts introduced within 60 seconds without examples.",
            "severity": "high",
            "relative_start": 0.15,  # 15% into video
            "relative_end": 0.25,  # 25% into video
            "evidence": [
                "Multiple technical terms introduced rapidly",
                "No pause for learner reflection",
                "Complex explanation without visual aid",
            ],
            "recommended_fix": "Add a 20-second worked example before introducing the next concept. Consider splitting this into two shorter segments.",
            "rewrite_example": "Let's work through a concrete example first. Imagine we have... [pause] Now let's apply this to our main problem.",
        },
        {
            "type": "passive_stretch",
            "title": "Passive stretch detected",
            "diagnosis": "No learner action or checkpoint for over 45 seconds.",
            "severity": "medium",
            "relative_start": 0.40,
            "relative_end": 0.55,
            "evidence": [
                "Continuous narration without pauses",
                "No questions or prompts for learner engagement",
                "Static visual content",
            ],
            "recommended_fix": "Insert a prediction question or quick pause exercise. Ask learners to summarize what they've learned so far.",
            "rewrite_example": "Pause here and ask yourself: What would happen if we changed X? Take 10 seconds to think about it before continuing.",
        },
        {
            "type": "visual_audio_overload",
            "title": "Visual/audio overload risk",
            "diagnosis": "Dense slide text combined with rapid narration introduces competing demands.",
            "severity": "medium",
            "relative_start": 0.70,
            "relative_end": 0.80,
            "evidence": [
                "Slide contains 150+ words of text",
                "Speech rate exceeds 180 WPM",
                "New terminology introduced while explaining existing content",
            ],
            "recommended_fix": "Simplify the slide to show only key terms. Move detailed explanations to speaker notes or separate slides.",
            "rewrite_example": "Show only the formula on slide. Say: 'This formula has three components. First... [click] Second... [click]'",
        },
    ]

    final_issues = []
    for i, template in enumerate(mock_issue_templates):
        start_sec = template["relative_start"] * duration
        end_sec = template["relative_end"] * duration

        # Only include issues that fit within video duration
        if end_sec > 10:  # Minimum 10 seconds to be meaningful
            final_issues.append(
                {
                    "id": f"mock_issue_{i}",
                    "type": template["type"],
                    "severity": template["severity"],
                    "start_sec": start_sec,
                    "end_sec": end_sec,
                    "title": template["title"],
                    "diagnosis": template["diagnosis"],
                    "evidence": template["evidence"],
                    "recommended_fix": template["recommended_fix"],
                    "rewrite_example": template["rewrite_example"],
                    "confidence": 0.7,
                }
            )

    # Calculate issue_count for each window using overlap
    for window in windows:
        window["clarity_score"] = 75.0
        window["pacing_score"] = 70.0
        window["cognitive_load_score"] = 65.0
        window["engagement_score"] = 60.0
        window["visual_audio_alignment_score"] = 70.0
        window["tribe_activation_energy"] = None
        window["tribe_signal_variation"] = None
        window["transcript_excerpt"] = window.get("text", "")[:500]
        window["issue_count"] = sum(1 for issue in final_issues if _overlaps(issue, window))

    # Mock metrics
    global_metrics = {
        "avg_speech_rate_wpm": 150.0,
        "pause_frequency_per_min": 3.5,
        "avg_text_density": 0.15,
        "visual_change_rate_per_min": 8.0,
        "tribe_signal_available": False,
        "tribe_signal_summary": {
            "avg_activation_energy": 0.0,
            "low_variation_windows": 0,
            "high_variation_windows": 0,
        },
    }

    # Calculate overall score
    quiz_alignment = _compute_quiz_alignment(job.quiz_questions or [], windows)

    scorer = Scorer()
    overall_score = scorer.calculate_overall_score(
        timeline=windows,
        issues=final_issues,
        quiz_alignment_score=quiz_alignment["score"],
    )

    summary = scorer.generate_summary(overall_score, final_issues, global_metrics)

    # Save report
    disclaimer = (
        "CourseBrain provides instructional-design risk signals. "
        "It does not diagnose learners or measure individual attention, "
        "comprehension, or learning outcomes. "
        "This is a mock analysis for demonstration purposes."
    )

    report = Report(
        job_id=job.id,
        coursebrain_score=overall_score,
        summary=summary,
        disclaimer=disclaimer,
        video_duration_seconds=duration,
        metrics={
            "avg_speech_rate_wpm": global_metrics.get("avg_speech_rate_wpm", 0),
            "pause_frequency_per_min": global_metrics.get("pause_frequency_per_min", 0),
            "avg_slide_text_density": global_metrics.get("avg_text_density", 0),
            "visual_change_rate_per_min": global_metrics.get(
                "visual_change_rate_per_min", 0
            ),
            "tribe_signal_available": False,
            "tribe_signal_summary": None,
        },
        timeline=windows,
        issues=final_issues,
        quiz_alignment=quiz_alignment,
    )
    db.add(report)

    # Mark job as completed
    job.status = "completed"
    job.progress = 100
    job.current_step = "Mock analysis complete"
    job.completed_at = datetime.utcnow()
    db.commit()


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
