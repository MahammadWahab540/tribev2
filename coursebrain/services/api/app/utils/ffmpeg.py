import subprocess
import os
from typing import Optional, Dict, Any
import json


def get_video_duration(video_path: str) -> float:
    """Get video duration in seconds using FFmpeg."""
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFprobe failed: {result.stderr}")

    data = json.loads(result.stdout)
    duration = float(data["format"]["duration"])
    return duration


def extract_audio(video_path: str, output_path: str) -> str:
    """Extract audio from video using FFmpeg."""
    cmd = [
        "ffmpeg",
        "-i",
        video_path,
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-y",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def sample_frames(
    video_path: str, output_dir: str, interval_seconds: float = 2.0
) -> list:
    """Sample frames from video at regular intervals."""
    os.makedirs(output_dir, exist_ok=True)

    duration = get_video_duration(video_path)
    frame_paths = []

    t = 0.0
    frame_num = 0
    while t < duration:
        output_path = os.path.join(output_dir, f"frame_{frame_num:06d}.jpg")
        cmd = [
            "ffmpeg",
            "-ss",
            str(t),
            "-i",
            video_path,
            "-vframes",
            "1",
            "-q:v",
            "2",
            "-y",
            output_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        frame_paths.append(output_path)
        t += interval_seconds
        frame_num += 1

    return frame_paths


def detect_scene_changes(
    video_path: str, threshold: float = 0.3
) -> list:
    """Detect scene changes using FFmpeg."""
    cmd = [
        "ffmpeg",
        "-i",
        video_path,
        "-filter_complex",
        f"select='gt(scene,{threshold})',metadata=print",
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Parse output for timestamps
    changes = []
    for line in result.stderr.split("\n"):
        if "pts_time:" in line:
            try:
                pts = float(line.split("pts_time:")[1].strip())
                changes.append(pts)
            except ValueError:
                continue

    return changes
