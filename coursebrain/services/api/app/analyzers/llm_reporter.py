from typing import List, Dict, Any, Optional
import json
import httpx


class LLMReporter:
    """
    Use an LLM to convert raw metrics into human-readable issue cards.
    
    IMPORTANT: The LLM must follow strict rules:
    - Do not invent timestamps
    - Do not overstate TribeV2 (refer to it as 'neuro-signal proxy' only internally)
    - User-facing text should use 'risk', 'may', 'likely', or 'possible'
    - Return only valid JSON
    """

    SYSTEM_PROMPT = """You are CourseBrain QA, an instructional-design reviewer for edtech lesson videos. Your job is to produce timestamped, practical, non-medical feedback.

IMPORTANT RULES:
1. Do NOT claim to measure attention, comprehension, emotions, diagnosis, intelligence, or learning outcomes.
2. Use ONLY the provided metrics and timestamps. Do NOT invent evidence.
3. Prefer specific edits: add example, add pause, split concept, reorder explanation, reduce slide text, add retrieval question, align quiz, define term.
4. User-facing language should say "risk", "may", "likely", or "possible" - never certainty.
5. Do NOT mention "brain", "fMRI", "neural", or "neuroscience" in user-facing text. Refer to TribeV2 signals as "engagement proxy" if needed.
6. Return ONLY valid JSON matching the schema below.

Output JSON schema:
{
  "issues": [
    {
      "id": "string",
      "type": "cognitive_load | passive_stretch | visual_audio_overload | unclear_explanation | pacing_issue | missing_example | jargon_burst | quiz_mismatch | objective_mismatch | accessibility",
      "severity": "low | medium | high",
      "start_sec": number,
      "end_sec": number,
      "title": "string",
      "diagnosis": "string",
      "evidence": ["string"],
      "recommended_fix": "string",
      "rewrite_example": "string",
      "confidence": 0-1
    }
  ]
}

Prioritize the top 10 most impactful issues maximum."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url or "https://api.openai.com/v1"
        self._client = None

    def _get_client(self):
        """Get HTTP client lazily."""
        if self._client is None:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.Client(
                base_url=self.base_url,
                headers=headers,
                timeout=60.0,
            )
        return self._client

    def generate_issues(
        self,
        course_title: str,
        target_learner: str,
        lesson_objective: str,
        difficulty: str,
        global_metrics: Dict[str, Any],
        timeline_windows: List[Dict[str, Any]],
        quiz_questions: List[str],
        candidate_issues: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Generate refined issue cards using an LLM.
        """
        # Prepare input data
        user_prompt = self._build_user_prompt(
            course_title=course_title,
            target_learner=target_learner,
            lesson_objective=lesson_objective,
            difficulty=difficulty,
            global_metrics=global_metrics,
            timeline_windows=timeline_windows,
            quiz_questions=quiz_questions,
            candidate_issues=candidate_issues,
        )

        try:
            client = self._get_client()
            response = client.post(
                "/chat/completions",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"]

            # Parse JSON response
            parsed = json.loads(content)
            issues = parsed.get("issues", [])

            # Validate and enrich issues
            validated_issues = self._validate_issues(issues, candidate_issues)

            return validated_issues[:10]  # Limit to top 10

        except Exception as e:
            # Fallback: return candidate issues with basic enrichment
            return self._fallback_enrich(candidate_issues)

    def _build_user_prompt(
        self,
        course_title: str,
        target_learner: str,
        lesson_objective: str,
        difficulty: str,
        global_metrics: Dict[str, Any],
        timeline_windows: List[Dict[str, Any]],
        quiz_questions: List[str],
        candidate_issues: List[Dict[str, Any]],
    ) -> str:
        """Build the user prompt for the LLM."""
        # Summarize windows to avoid token overflow
        window_summaries = []
        for w in timeline_windows[:20]:  # Limit windows
            window_summaries.append(
                {
                    "start_sec": w["start_sec"],
                    "end_sec": w["end_sec"],
                    "wpm": w.get("wpm", 0),
                    "concepts": w.get("detected_concepts", []),
                    "has_examples": w.get("has_examples", False),
                    "has_actions": w.get("has_actions", False),
                    "text_density": w.get("text_density", 0),
                    "tribe_variation": w.get("tribe_signal_variation"),
                }
            )

        prompt = f"""Analyze the following lesson windows and detected metrics. Produce issue cards only for meaningful problems.

Course title: {course_title}
Target learner: {target_learner}
Lesson objective: {lesson_objective}
Difficulty: {difficulty}

Global metrics:
{json.dumps(global_metrics, indent=2)}

Timeline windows (sample):
{json.dumps(window_summaries, indent=2)}

Quiz questions:
{json.dumps(quiz_questions)}

Detected risk candidates (use these as starting points):
{json.dumps(candidate_issues[:15], indent=2)}

Rules:
- Do not invent timestamps. Use only timestamps from the windows or candidates above.
- Do not overstate any signals. Use "risk", "may", "likely", or "possible".
- Prioritize top 10 issues maximum.
- Use practical instructional-design language.
- For each issue, provide a specific recommended_fix and a concrete rewrite_example.
- Return JSON only."""

        return prompt

    def _validate_issues(
        self, issues: List[Dict[str, Any]], candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Validate and enrich LLM-generated issues."""
        validated = []
        valid_types = {
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
        }
        valid_severities = {"low", "medium", "high"}

        for issue in issues:
            # Validate required fields
            if not all(
                k in issue
                for k in [
                    "type",
                    "severity",
                    "start_sec",
                    "end_sec",
                    "title",
                    "diagnosis",
                    "evidence",
                    "recommended_fix",
                    "rewrite_example",
                    "confidence",
                ]
            ):
                continue

            # Validate type
            if issue["type"] not in valid_types:
                continue

            # Validate severity
            if issue["severity"] not in valid_severities:
                continue

            # Validate confidence
            if not isinstance(issue["confidence"], (int, float)) or not (
                0 <= issue["confidence"] <= 1
            ):
                issue["confidence"] = 0.5

            # Add ID if missing
            if "id" not in issue:
                import uuid

                issue["id"] = str(uuid.uuid4())

            validated.append(issue)

        return validated

    def _fallback_enrich(
        self, candidate_issues: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Enrich candidate issues without LLM (fallback mode).
        Provides basic recommended fixes based on issue type.
        """
        fix_templates = {
            "cognitive_load": {
                "fix": "Add a worked example before introducing the next concept. Consider splitting this into two shorter segments.",
                "rewrite": "Let's work through an example first: [specific example]. Now that we've seen this in action, the formula makes more sense.",
            },
            "passive_stretch": {
                "fix": "Insert a pause-and-reflect question or quick practice exercise.",
                "rewrite": "Pause here and try this: [quick question]. Think about your answer for 10 seconds before continuing.",
            },
            "visual_audio_overload": {
                "fix": "Simplify the slide. Move detailed text to speaker notes or a handout.",
                "rewrite": "Show only the key diagram. Say: 'I'll walk through each part' instead of displaying all explanations.",
            },
            "pacing_issue": {
                "fix": "Slow down speech rate. Add strategic pauses after key points.",
                "rewrite": "After stating each key concept, pause for 2-3 seconds to let it sink in.",
            },
            "jargon_burst": {
                "fix": "Define technical terms before using them. Add a glossary reference.",
                "rewrite": "Before we continue, let me clarify: [term] means [simple definition]. You'll see this throughout the course.",
            },
            "missing_example": {
                "fix": "Add a concrete, relatable example immediately after the abstract concept.",
                "rewrite": "For instance, imagine [relatable scenario]. Here, [concept] works like [analogy].",
            },
        }

        enriched = []
        for issue in candidate_issues:
            issue_type = issue.get("type", "unclear_explanation")
            templates = fix_templates.get(
                issue_type,
                {
                    "fix": "Review this segment for clarity and engagement.",
                    "rewrite": "Consider adding an example or checkpoint question here.",
                },
            )

            enriched_issue = {
                **issue,
                "recommended_fix": issue.get("recommended_fix", templates["fix"]),
                "rewrite_example": issue.get("rewrite_example", templates["rewrite"]),
            }
            enriched.append(enriched_issue)

        # Sort by confidence and limit
        enriched.sort(key=lambda x: x.get("confidence", 0.5), reverse=True)
        return enriched[:10]
