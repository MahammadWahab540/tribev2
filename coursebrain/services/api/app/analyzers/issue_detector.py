from typing import List, Dict, Any
import uuid


class IssueDetector:
    """
    Detect instructional design issues using heuristic rules.
    Combines signals from transcript, visual, audio, and TribeV2 analyzers.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        # Thresholds
        self.min_passive_stretch = self.config.get("min_passive_stretch", 45)
        self.high_speech_rate_wpm = self.config.get("high_speech_rate_wpm", 180)
        self.low_speech_rate_wpm = self.config.get("low_speech_rate_wpm", 100)
        self.high_jargon_density = self.config.get("high_jargon_density", 0.15)
        self.high_text_density = self.config.get("high_text_density", 0.3)

    def detect_issues(
        self,
        windows: List[Dict[str, Any]],
        tribe_metrics: List[Dict[str, Any]] = None,
        visual_metrics: List[Dict[str, Any]] = None,
        context: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        Detect issues across all windows.
        Returns list of issue candidates (before LLM refinement).
        """
        issues = []

        for i, window in enumerate(windows):
            tribe_m = tribe_metrics[i] if tribe_metrics and i < len(tribe_metrics) else {}
            visual_m = visual_metrics[i] if visual_metrics and i < len(visual_metrics) else {}

            # Merge all metrics into window for easier access
            enriched_window = {**window, **tribe_m, **visual_m}

            # Detect cognitive load risk
            cl_issue = self._detect_cognitive_load(enriched_window)
            if cl_issue:
                issues.append(cl_issue)

            # Detect passive stretch
            ps_issue = self._detect_passive_stretch(enriched_window, windows, i)
            if ps_issue:
                issues.append(ps_issue)

            # Detect visual/audio overload
            va_issue = self._detect_visual_audio_overload(enriched_window)
            if va_issue:
                issues.append(va_issue)

            # Detect pacing issue
            pacing_issue = self._detect_pacing_issue(enriched_window)
            if pacing_issue:
                issues.append(pacing_issue)

            # Detect jargon burst
            jargon_issue = self._detect_jargon_burst(enriched_window)
            if jargon_issue:
                issues.append(jargon_issue)

            # Detect missing example
            example_issue = self._detect_missing_example(enriched_window)
            if example_issue:
                issues.append(example_issue)

        # Merge overlapping issues of same type
        issues = self._merge_similar_issues(issues)

        return issues

    def _detect_cognitive_load(self, window: Dict[str, Any]) -> Dict[str, Any]:
        """Detect high cognitive load risk."""
        concepts = window.get("detected_concepts", [])
        has_examples = window.get("has_examples", False)
        wpm = window.get("wpm", 140)
        confusion_markers = window.get("confusion_marker_count", 0)
        text_density = window.get("text_density", 0)

        # High cognitive load when:
        # - 3+ new concepts without examples
        # - AND high speech rate or low pause frequency
        # - OR high text density while introducing concepts

        risk_score = 0
        evidence = []

        if len(concepts) >= 3:
            risk_score += 30
            evidence.append(f"{len(concepts)} concepts introduced")

        if not has_examples and len(concepts) > 0:
            risk_score += 20
            evidence.append("No examples provided")

        if wpm > self.high_speech_rate_wpm:
            risk_score += 20
            evidence.append(f"High speech rate ({wpm:.0f} WPM)")

        if confusion_markers > 1:
            risk_score += 15
            evidence.append(f"{confusion_markers} confusion markers detected")

        if text_density > self.high_text_density and len(concepts) > 0:
            risk_score += 15
            evidence.append(f"High slide text density ({text_density:.1%})")

        if risk_score >= 40:
            severity = "high" if risk_score >= 70 else "medium" if risk_score >= 50 else "low"
            confidence = min(0.95, risk_score / 100)

            return {
                "id": str(uuid.uuid4()),
                "type": "cognitive_load",
                "severity": severity,
                "start_sec": window["start_sec"],
                "end_sec": window["end_sec"],
                "title": "High cognitive-load risk",
                "diagnosis": "Multiple concepts introduced without sufficient scaffolding.",
                "evidence": evidence,
                "risk_score": risk_score,
                "confidence": confidence,
            }

        return None

    def _detect_passive_stretch(
        self, window: Dict[str, Any], windows: List[Dict[str, Any]], index: int
    ) -> Dict[str, Any]:
        """Detect passive learner stretches."""
        has_actions = window.get("has_actions", False)

        if has_actions:
            return None

        # Check how long since last action
        time_since_action = 0
        for i in range(index - 1, -1, -1):
            if windows[i].get("has_actions", False):
                break
            time_since_action += windows[i]["end_sec"] - windows[i]["start_sec"]

        # Check forward too
        time_ahead_without_action = 0
        for i in range(index, len(windows)):
            if windows[i].get("has_actions", False):
                break
            time_ahead_without_action += windows[i]["end_sec"] - windows[i]["start_sec"]

        total_passive_duration = time_since_action + time_ahead_without_action

        # Check tribe signal if available
        tribe_variation = window.get("tribe_signal_variation")
        low_tribe_variation = tribe_variation is not None and tribe_variation < 0.15

        if total_passive_duration >= self.min_passive_stretch:
            severity = (
                "high"
                if total_passive_duration >= 90
                else "medium"
                if total_passive_duration >= 60
                else "low"
            )
            confidence = min(0.9, 0.5 + (total_passive_duration - self.min_passive_stretch) / 100)

            evidence = [f"No learner action for {total_passive_duration:.0f} seconds"]
            if low_tribe_variation:
                evidence.append("Low neuro-signal variation suggests passive viewing")
                confidence = min(0.95, confidence + 0.1)

            return {
                "id": str(uuid.uuid4()),
                "type": "passive_stretch",
                "severity": severity,
                "start_sec": window["start_sec"] - time_since_action,
                "end_sec": window["end_sec"] + time_ahead_without_action,
                "title": "Passive stretch detected",
                "diagnosis": "Extended period without learner engagement or interaction.",
                "evidence": evidence,
                "risk_score": total_passive_duration,
                "confidence": confidence,
            }

        return None

    def _detect_visual_audio_overload(self, window: Dict[str, Any]) -> Dict[str, Any]:
        """Detect visual/audio overload."""
        text_density = window.get("text_density", 0)
        wpm = window.get("wpm", 140)
        concepts = window.get("detected_concepts", [])
        tribe_variation = window.get("tribe_signal_variation")

        risk_score = 0
        evidence = []

        # High text density with fast speech
        if text_density > self.high_text_density and wpm > 160:
            risk_score += 40
            evidence.append(f"Dense slide text ({text_density:.1%}) with fast narration ({wpm:.0f} WPM)")

        # Many concepts while text density is high
        if len(concepts) > 2 and text_density > 0.2:
            risk_score += 30
            evidence.append(f"{len(concepts)} new concepts with dense visuals")

        # High tribe variation suggesting overload
        if tribe_variation is not None and tribe_variation > 0.5:
            risk_score += 20
            evidence.append("High neuro-signal variation may indicate cognitive overload")

        if risk_score >= 50:
            severity = "high" if risk_score >= 70 else "medium" if risk_score >= 50 else "low"
            confidence = min(0.9, risk_score / 100)

            return {
                "id": str(uuid.uuid4()),
                "type": "visual_audio_overload",
                "severity": severity,
                "start_sec": window["start_sec"],
                "end_sec": window["end_sec"],
                "title": "Visual/audio overload risk",
                "diagnosis": "Too much information presented simultaneously through visuals and narration.",
                "evidence": evidence,
                "risk_score": risk_score,
                "confidence": confidence,
            }

        return None

    def _detect_pacing_issue(self, window: Dict[str, Any]) -> Dict[str, Any]:
        """Detect pacing issues (too fast or too slow)."""
        wpm = window.get("wpm", 140)

        if wpm > self.high_speech_rate_wpm:
            severity = "high" if wpm > 220 else "medium" if wpm > 200 else "low"
            confidence = min(0.9, (wpm - self.high_speech_rate_wpm) / 100)

            return {
                "id": str(uuid.uuid4()),
                "type": "pacing_issue",
                "severity": severity,
                "start_sec": window["start_sec"],
                "end_sec": window["end_sec"],
                "title": "Pacing too fast",
                "diagnosis": f"Speech rate of {wpm:.0f} WPM may overwhelm learners.",
                "evidence": [f"Speech rate: {wpm:.0f} WPM (recommended: 120-160 WPM)"],
                "risk_score": wpm,
                "confidence": confidence,
            }

        elif wpm < self.low_speech_rate_wpm:
            severity = "medium" if wpm < 80 else "low"
            confidence = min(0.8, (self.low_speech_rate_wpm - wpm) / 50)

            return {
                "id": str(uuid.uuid4()),
                "type": "pacing_issue",
                "severity": severity,
                "start_sec": window["start_sec"],
                "end_sec": window["end_sec"],
                "title": "Pacing too slow",
                "diagnosis": f"Speech rate of {wpm:.0f} WPM may cause learner disengagement.",
                "evidence": [f"Speech rate: {wpm:.0f} WPM (recommended: 120-160 WPM)"],
                "risk_score": self.low_speech_rate_wpm - wpm,
                "confidence": confidence,
            }

        return None

    def _detect_jargon_burst(self, window: Dict[str, Any]) -> Dict[str, Any]:
        """Detect jargon bursts."""
        jargon_density = window.get("jargon_density", 0)
        jargon_words = window.get("jargon_words", [])

        if jargon_density > self.high_jargon_density and len(jargon_words) >= 3:
            severity = (
                "high"
                if jargon_density > 0.3
                else "medium"
                if jargon_density > 0.2
                else "low"
            )
            confidence = min(0.9, jargon_density * 2)

            return {
                "id": str(uuid.uuid4()),
                "type": "jargon_burst",
                "severity": severity,
                "start_sec": window["start_sec"],
                "end_sec": window["end_sec"],
                "title": "Jargon density spike",
                "diagnosis": "High concentration of technical terms may confuse learners.",
                "evidence": [f"{len(jargon_words)} technical terms: {', '.join(jargon_words[:5])}"],
                "risk_score": jargon_density * 100,
                "confidence": confidence,
            }

        return None

    def _detect_missing_example(self, window: Dict[str, Any]) -> Dict[str, Any]:
        """Detect missing examples for abstract concepts."""
        concepts = window.get("detected_concepts", [])
        has_examples = window.get("has_examples", False)
        definition_count = window.get("definition_count", 0)

        # Flag when concepts/definitions appear without examples
        if (len(concepts) >= 2 or definition_count >= 1) and not has_examples:
            confidence = min(0.85, 0.4 + len(concepts) * 0.15 + definition_count * 0.2)

            return {
                "id": str(uuid.uuid4()),
                "type": "missing_example",
                "severity": "medium" if len(concepts) >= 3 else "low",
                "start_sec": window["start_sec"],
                "end_sec": window["end_sec"],
                "title": "Missing worked example",
                "diagnosis": "Abstract concepts introduced without concrete examples.",
                "evidence": [
                    f"Concepts: {', '.join(concepts[:3])}" if concepts else "Definition provided",
                    "No example phrases detected",
                ],
                "risk_score": len(concepts) * 20 + definition_count * 25,
                "confidence": confidence,
            }

        return None

    def _merge_similar_issues(self, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Merge overlapping issues of the same type."""
        if not issues:
            return []

        # Group by type
        by_type = {}
        for issue in issues:
            issue_type = issue["type"]
            if issue_type not in by_type:
                by_type[issue_type] = []
            by_type[issue_type].append(issue)

        merged = []
        for issue_type, type_issues in by_type.items():
            # Sort by start time
            type_issues.sort(key=lambda x: x["start_sec"])

            current_group = [type_issues[0]]
            for issue in type_issues[1:]:
                # Check if this issue overlaps with current group
                last_in_group = current_group[-1]
                if issue["start_sec"] <= last_in_group["end_sec"] + 10:
                    # Merge
                    current_group.append(issue)
                else:
                    # Finalize current group and start new one
                    merged.append(self._merge_issue_group(current_group))
                    current_group = [issue]

            # Don't forget the last group
            merged.append(self._merge_issue_group(current_group))

        return merged

    def _merge_issue_group(self, issues: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge a group of similar issues."""
        if len(issues) == 1:
            return issues[0]

        # Combine evidence
        all_evidence = []
        for issue in issues:
            all_evidence.extend(issue.get("evidence", []))

        # Use max severity
        severity_order = {"low": 0, "medium": 1, "high": 2}
        max_severity = max(issues, key=lambda x: severity_order.get(x["severity"], 0))["severity"]

        # Average confidence
        avg_confidence = sum(i["confidence"] for i in issues) / len(issues)

        return {
            "id": str(uuid.uuid4()),
            "type": issues[0]["type"],
            "severity": max_severity,
            "start_sec": min(i["start_sec"] for i in issues),
            "end_sec": max(i["end_sec"] for i in issues),
            "title": issues[0]["title"],
            "diagnosis": issues[0]["diagnosis"],
            "evidence": list(set(all_evidence)),
            "risk_score": max(i.get("risk_score", 0) for i in issues),
            "confidence": avg_confidence,
        }
