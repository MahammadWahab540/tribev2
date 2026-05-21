from typing import List, Dict, Any, Set
import re
from collections import Counter


class TranscriptAnalyzer:
    """Analyze transcript text for instructional design issues."""

    # Common jargon markers (can be customized per domain)
    JARGON_PATTERNS = [
        r"\b[A-Z]{2,}\b",  # Acronyms
        r"\b\w+(?:ification|ization|ability|ibility)\b",  # Technical suffixes
    ]

    # Confusion markers
    CONFUSION_MARKERS = [
        "obviously",
        "clearly",
        "simply",
        "just",
        "easy",
        "basic",
        "trivial",
    ]

    # Example markers
    EXAMPLE_MARKERS = [
        "for example",
        "for instance",
        "such as",
        "like when",
        "imagine",
        "let's apply",
        "consider",
    ]

    # Action markers (learner activities)
    ACTION_MARKERS = [
        "pause",
        "try this",
        "practice",
        "exercise",
        "question",
        "quiz",
        "test yourself",
        "reflect",
        "write down",
        "discuss",
    ]

    # Definition markers
    DEFINITION_MARKERS = [
        "is defined as",
        "means",
        "refers to",
        "called",
        "known as",
        "we call this",
    ]

    def __init__(self):
        pass

    def analyze_segments(
        self, segments: List[Dict[str, Any]], window_size: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Analyze transcript segments and create timeline windows with metrics.
        """
        if not segments:
            return []

        # Get total duration
        total_duration = max(seg.get("end", 0) for seg in segments)

        # Create windows
        windows = []
        current_start = 0.0

        while current_start < total_duration:
            current_end = min(current_start + window_size, total_duration)

            # Find segments in this window
            window_segments = [
                seg
                for seg in segments
                if seg.get("start", 0) < current_end
                and seg.get("end", 0) > current_start
            ]

            # Analyze window
            window_analysis = self._analyze_window(
                window_segments, current_start, current_end
            )
            windows.append(window_analysis)

            current_start = current_end

        return windows

    def _analyze_window(
        self, segments: List[Dict[str, Any]], start: float, end: float
    ) -> Dict[str, Any]:
        """Analyze a single time window."""
        # Combine text
        text = " ".join(seg.get("text", "") for seg in segments).strip()
        words = text.split()
        word_count = len(words)

        # Calculate WPM for this window
        duration = end - start
        wpm = (word_count / duration * 60) if duration > 0 else 0

        # Count markers
        text_lower = text.lower()
        example_count = sum(1 for m in self.EXAMPLE_MARKERS if m in text_lower)
        action_count = sum(1 for m in self.ACTION_MARKERS if m in text_lower)
        definition_count = sum(1 for m in self.DEFINITION_MARKERS if m in text_lower)
        confusion_count = sum(1 for m in self.CONFUSION_MARKERS if m in text_lower)

        # Detect jargon (acronyms and technical terms)
        jargon_words = set()
        for pattern in self.JARGON_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            jargon_words.update(matches)
        jargon_density = len(jargon_words) / word_count if word_count > 0 else 0

        # Detect concepts (capitalized terms, often proper nouns or key terms)
        concept_pattern = r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b"
        concepts = list(set(re.findall(concept_pattern, text)))
        # Filter out common words
        common_starts = {"The", "This", "That", "These", "Those", "What", "When", "Where", "Why", "How"}
        concepts = [c for c in concepts if c.split()[0] not in common_starts]

        # Sentence analysis
        sentences = re.split(r"[.!?]+", text)
        sentences = [s.strip() for s in sentences if s.strip()]
        avg_sentence_length = (
            sum(len(s.split()) for s in sentences) / len(sentences)
            if sentences
            else 0
        )

        return {
            "start_sec": start,
            "end_sec": end,
            "text": text,
            "word_count": word_count,
            "wpm": wpm,
            "sentence_count": len(sentences),
            "avg_sentence_length": avg_sentence_length,
            "example_count": example_count,
            "action_count": action_count,
            "definition_count": definition_count,
            "confusion_marker_count": confusion_count,
            "jargon_density": jargon_density,
            "jargon_words": list(jargon_words),
            "detected_concepts": concepts[:10],  # Limit to top 10
            "has_examples": example_count > 0,
            "has_actions": action_count > 0,
        }

    def compute_global_metrics(self, windows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute global metrics across all windows."""
        if not windows:
            return {}

        total_words = sum(w["word_count"] for w in windows)
        total_duration = sum(w["end_sec"] - w["start_sec"] for w in windows)

        avg_wpm = total_words / (total_duration / 60) if total_duration > 0 else 0
        avg_jargon_density = (
            sum(w["jargon_density"] for w in windows) / len(windows)
        )

        # Count concept introductions (first appearance)
        all_concepts = []
        for w in windows:
            all_concepts.extend(w.get("detected_concepts", []))
        concept_counts = Counter(all_concepts)
        unique_concepts = len(concept_counts)

        # Calculate concept introduction rate (concepts per minute)
        concept_rate = unique_concepts / (total_duration / 60) if total_duration > 0 else 0

        return {
            "total_words": total_words,
            "total_duration": total_duration,
            "avg_speech_rate_wpm": avg_wpm,
            "avg_jargon_density": avg_jargon_density,
            "unique_concepts": unique_concepts,
            "concept_introduction_rate": concept_rate,
        }

    def detect_learner_action_gaps(
        self, windows: List[Dict[str, Any]], min_gap_seconds: int = 45
    ) -> List[Dict[str, Any]]:
        """Detect periods without learner actions."""
        gaps = []
        last_action_end = None

        for window in windows:
            if window.get("has_actions"):
                if last_action_end is not None:
                    gap_duration = window["start_sec"] - last_action_end
                    if gap_duration >= min_gap_seconds:
                        gaps.append(
                            {
                                "start_sec": last_action_end,
                                "end_sec": window["start_sec"],
                                "duration": gap_duration,
                            }
                        )
                last_action_end = window["end_sec"]

        # Check final gap
        if last_action_end is not None and windows:
            final_gap = windows[-1]["end_sec"] - last_action_end
            if final_gap >= min_gap_seconds:
                gaps.append(
                    {
                        "start_sec": last_action_end,
                        "end_sec": windows[-1]["end_sec"],
                        "duration": final_gap,
                    }
                )

        return gaps
