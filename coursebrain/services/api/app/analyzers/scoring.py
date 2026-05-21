from typing import List, Dict, Any


class Scorer:
    """
    Calculate CourseBrain scores based on analysis metrics and issues.
    
    Overall CourseBrain Score = weighted score:
    - clarity: 25
    - pacing: 20
    - cognitive load: 20
    - engagement design: 15
    - assessment alignment: 10
    - accessibility/production: 10
    """

    # Weights for each category
    WEIGHTS = {
        "clarity": 25,
        "pacing": 20,
        "cognitive_load": 20,
        "engagement": 15,
        "assessment": 10,
        "accessibility": 10,
    }

    # Issue severity deductions
    SEVERITY_DEDUCTIONS = {
        "high": (8, 12),
        "medium": (4, 7),
        "low": (1, 3),
    }

    # Issue type to category mapping
    ISSUE_CATEGORIES = {
        "unclear_explanation": "clarity",
        "jargon_burst": "clarity",
        "pacing_issue": "pacing",
        "cognitive_load": "cognitive_load",
        "missing_example": "cognitive_load",
        "visual_audio_overload": "cognitive_load",
        "passive_stretch": "engagement",
        "quiz_mismatch": "assessment",
        "objective_mismatch": "assessment",
        "accessibility": "accessibility",
    }

    def __init__(self):
        pass

    def calculate_overall_score(
        self,
        timeline: List[Dict[str, Any]],
        issues: List[Dict[str, Any]],
        quiz_alignment_score: float = 100,
    ) -> float:
        """
        Calculate overall CourseBrain score (0-100).
        """
        # Start with perfect score
        score = 100.0

        # Deduct based on issues
        for issue in issues:
            severity = issue.get("severity", "low")
            min_deduct, max_deduct = self.SEVERITY_DEDUCTIONS.get(
                severity, (1, 3)
            )

            # Use confidence to scale deduction
            confidence = issue.get("confidence", 0.5)
            deduction = min_deduct + (max_deduct - min_deduct) * confidence

            score -= deduction

        # Bonus for good quiz alignment
        if quiz_alignment_score < 80:
            # Penalize poor quiz alignment
            score -= (80 - quiz_alignment_score) * 0.1

        # Clamp to 0-100
        return max(0, min(100, score))

    def calculate_subscores(
        self,
        timeline: List[Dict[str, Any]],
        issues: List[Dict[str, Any]],
    ) -> Dict[str, float]:
        """
        Calculate sub-scores for each category.
        """
        subscores = {category: 100.0 for category in self.WEIGHTS}

        # Deduct from relevant categories based on issues
        for issue in issues:
            issue_type = issue.get("type")
            category = self.ISSUE_CATEGORIES.get(issue_type)

            if category and category in subscores:
                severity = issue.get("severity", "low")
                min_deduct, max_deduct = self.SEVERITY_DEDUCTIONS.get(
                    severity, (1, 3)
                )
                confidence = issue.get("confidence", 0.5)
                deduction = (min_deduct + (max_deduct - min_deduct) * confidence) / 2

                subscores[category] = max(0, subscores[category] - deduction)

        # Calculate scores from timeline metrics if available
        if timeline:
            # Clarity from clarity scores
            clarity_scores = [w.get("clarity_score", 50) for w in timeline]
            if clarity_scores:
                subscores["clarity"] = max(
                    0, min(100, sum(clarity_scores) / len(clarity_scores))
                )

            # Pacing from pacing scores
            pacing_scores = [w.get("pacing_score", 50) for w in timeline]
            if pacing_scores:
                subscores["pacing"] = max(
                    0, min(100, sum(pacing_scores) / len(pacing_scores))
                )

            # Cognitive load from cognitive load scores
            cl_scores = [w.get("cognitive_load_score", 50) for w in timeline]
            if cl_scores:
                subscores["cognitive_load"] = max(
                    0, min(100, sum(cl_scores) / len(cl_scores))
                )

            # Engagement from engagement scores
            eng_scores = [w.get("engagement_score", 50) for w in timeline]
            if eng_scores:
                subscores["engagement"] = max(
                    0, min(100, sum(eng_scores) / len(eng_scores))
                )

        return subscores

    def calculate_weighted_score(self, subscores: Dict[str, float]) -> float:
        """
        Calculate weighted overall score from sub-scores.
        """
        total_weight = sum(self.WEIGHTS.values())
        weighted_sum = sum(
            subscores.get(category, 50) * weight
            for category, weight in self.WEIGHTS.items()
        )
        return weighted_sum / total_weight

    def calculate_window_scores(
        self, window: Dict[str, Any], tribe_metrics: Dict[str, Any] = None
    ) -> Dict[str, float]:
        """
        Calculate scores for a single timeline window.
        """
        # Clarity score (based on transcript analysis)
        clarity_score = 100.0
        if window.get("confusion_marker_count", 0) > 2:
            clarity_score -= 15
        if window.get("jargon_density", 0) > 0.2:
            clarity_score -= 20
        if not window.get("has_examples", False) and window.get("detected_concepts"):
            clarity_score -= 10

        # Pacing score (based on speech rate)
        pacing_score = 100.0
        wpm = window.get("wpm", 140)
        if wpm > 180:
            pacing_score -= min(30, (wpm - 180) * 0.5)
        elif wpm < 100:
            pacing_score -= min(20, (100 - wpm) * 0.3)

        # Cognitive load score
        cognitive_load_score = 100.0
        concept_count = len(window.get("detected_concepts", []))
        if concept_count > 3:
            cognitive_load_score -= min(30, concept_count * 5)
        if not window.get("has_examples", False) and concept_count > 2:
            cognitive_load_score -= 15
        if window.get("avg_sentence_length", 0) > 25:
            cognitive_load_score -= 10

        # Engagement score
        engagement_score = 100.0
        if not window.get("has_actions", False):
            engagement_score -= 15
        if tribe_metrics:
            # Use tribe signal variation as engagement proxy
            tribe_var = tribe_metrics.get("tribe_signal_variation")
            if tribe_var is not None and tribe_var < 0.1:
                engagement_score -= 10

        # Visual/audio alignment score
        visual_audio_alignment_score = 100.0
        text_density = window.get("text_density", 0)
        if text_density > 0.3 and wpm > 160:
            visual_audio_alignment_score -= 20

        return {
            "clarity_score": max(0, min(100, clarity_score)),
            "pacing_score": max(0, min(100, pacing_score)),
            "cognitive_load_score": max(0, min(100, cognitive_load_score)),
            "engagement_score": max(0, min(100, engagement_score)),
            "visual_audio_alignment_score": max(
                0, min(100, visual_audio_alignment_score)
            ),
        }

    def generate_summary(
        self,
        score: float,
        issues: List[Dict[str, Any]],
        metrics: Dict[str, Any],
    ) -> str:
        """
        Generate a human-readable summary of the analysis.
        """
        if score >= 80:
            quality = "excellent"
        elif score >= 60:
            quality = "good"
        elif score >= 40:
            quality = "moderate"
        else:
            quality = "needs improvement"

        high_severity = sum(1 for i in issues if i.get("severity") == "high")
        medium_severity = sum(1 for i in issues if i.get("severity") == "medium")

        summary_parts = [
            f"This lesson video has {quality} instructional design quality "
            f"(CourseBrain Score: {score:.0f}/100)."
        ]

        if high_severity > 0:
            summary_parts.append(
                f"There are {high_severity} high-priority issues that should be addressed."
            )

        if medium_severity > 0:
            summary_parts.append(
                f"There are {medium_severity} medium-priority issues to consider."
            )

        # Add specific insights
        if metrics.get("avg_speech_rate_wpm", 0) > 180:
            summary_parts.append(
                "The speech rate is quite fast, which may overwhelm learners."
            )

        if metrics.get("avg_slide_text_density", 0) > 0.3:
            summary_parts.append(
                "Slides contain dense text; consider simplifying visual content."
            )

        return " ".join(summary_parts)
