"""
SENTINEL — Gemini Query Service
Handles conversational queries by officers against the incident narrative
using Google Gemini LLM (gemini-2.0-flash).
"""

import os
import json
from datetime import datetime

from google import genai

from .models import QueryResponse, IncidentNarrative
from .narrative_engine import NarrativeEngine


# ──────────────────────────────────────────────
# System Prompt Template
# ──────────────────────────────────────────────

SYSTEM_PROMPT_TEMPLATE = """You are SENTINEL, an AI copilot for traffic incident command. You assist law enforcement \
officers by analyzing a running incident narrative and answering their questions accurately and concisely.

{narrative_context}

INSTRUCTIONS:
1. Answer the officer's question based ONLY on the incident narrative above.
2. Always prioritize SAFETY — if there is ANY doubt, recommend caution.
3. Provide a clear safety assessment: SAFE, CAUTION, or UNSAFE.
4. Be concise but thorough — officers need quick, actionable answers.
5. Reference specific timeline events when relevant.
6. If information is not available in the narrative, say so explicitly.
7. Format your response as plain text, no markdown.

Your response MUST follow this exact JSON format:
{{
  "answer": "Your detailed answer here",
  "safety_assessment": "safe|caution|unsafe",
  "confidence": "high|medium|low"
}}
"""


# ──────────────────────────────────────────────
# Query Service
# ──────────────────────────────────────────────

class GeminiQueryService:
    """
    Sends officer questions + full narrative context to Google Gemini
    and returns a structured QueryResponse.
    """

    def __init__(self, engine: NarrativeEngine):
        self._engine = engine

    async def query(self, question: str) -> QueryResponse:
        """
        Process an officer's conversational query.

        Args:
            question: The officer's natural-language question.

        Returns:
            QueryResponse with answer, safety assessment, and confidence.

        Raises:
            RuntimeError: If GEMINI_API_KEY is not set or the API call fails.
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY environment variable is not set. "
                "Please set it to a valid Google Gemini API key."
            )

        # Build the full prompt
        narrative_context = self._engine.to_prompt_context()
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            narrative_context=narrative_context
        )
        user_message = f"Officer's question: {question}"

        # Call Gemini
        client = genai.Client(api_key=api_key)

        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    {
                        "role": "user",
                        "parts": [{"text": system_prompt + "\n\n" + user_message}],
                    },
                ],
            )

            raw_text = response.text.strip()
            return self._parse_response(raw_text)

        except Exception as e:
            raise RuntimeError(f"Gemini API error: {str(e)}")

    # ── Response Parsing ──────────────────────

    def _parse_response(self, raw_text: str) -> QueryResponse:
        """
        Parse the LLM response into a structured QueryResponse.
        Handles both clean JSON and markdown-fenced JSON output.
        """
        try:
            cleaned = raw_text

            # Strip markdown code fences if present
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()

            parsed = json.loads(cleaned)

            return QueryResponse(
                answer=parsed.get("answer", raw_text),
                safety_assessment=parsed.get("safety_assessment", "unknown"),
                confidence=parsed.get("confidence", "medium"),
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                sources_referenced=self._engine.event_count,
            )

        except (json.JSONDecodeError, KeyError):
            # Fallback: wrap raw text if JSON parsing fails
            return QueryResponse(
                answer=raw_text,
                safety_assessment="unknown",
                confidence="medium",
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                sources_referenced=self._engine.event_count,
            )
