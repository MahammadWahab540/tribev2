import whisper
from typing import List, Dict, Any
import os
from app.utils.ffmpeg import extract_audio


class AudioAnalyzer:
    """Analyze audio from video files."""

    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self.model = None

    def load_model(self):
        """Load Whisper model lazily."""
        if self.model is None:
            self.model = whisper.load_model(self.model_size)

    def transcribe(
        self, audio_path: str, word_timestamps: bool = True
    ) -> Dict[str, Any]:
        """
        Transcribe audio file using Whisper.
        Returns transcript with segment-level and word-level timestamps.
        """
        self.load_model()

        result = self.model.transcribe(
            audio_path,
            word_timestamps=word_timestamps,
            task="transcribe",
            language=None,  # Auto-detect
        )

        return result

    def analyze_audio(self, video_path: str, temp_dir: str) -> Dict[str, Any]:
        """
        Extract audio from video and transcribe.
        Returns transcription result and audio metrics.
        """
        # Extract audio
        audio_path = os.path.join(temp_dir, "audio.wav")
        extract_audio(video_path, audio_path)

        # Transcribe
        transcript = self.transcribe(audio_path)

        # Compute basic metrics
        segments = transcript.get("segments", [])
        total_duration = transcript.get("duration", 0)

        # Calculate speech rate (words per minute)
        total_words = sum(len(seg.get("text", "").split()) for seg in segments)
        speaking_time = sum(
            seg["end"] - seg["start"] for seg in segments if "start" in seg and "end" in seg
        )
        avg_speech_rate = (total_words / speaking_time * 60) if speaking_time > 0 else 0

        # Calculate pause frequency
        pauses = []
        for i in range(len(segments) - 1):
            gap = segments[i + 1]["start"] - segments[i]["end"]
            if gap > 0.5:  # Consider gaps > 0.5s as pauses
                pauses.append(gap)

        pause_frequency = len(pauses) / (total_duration / 60) if total_duration > 0 else 0
        avg_pause_length = sum(pauses) / len(pauses) if pauses else 0

        return {
            "transcript": transcript,
            "audio_path": audio_path,
            "metrics": {
                "total_duration": total_duration,
                "total_words": total_words,
                "avg_speech_rate_wpm": avg_speech_rate,
                "pause_frequency_per_min": pause_frequency,
                "avg_pause_length": avg_pause_length,
                "num_segments": len(segments),
            },
        }
