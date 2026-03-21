"""
SENTINEL — Native Audio Gemini Service
Handles conversational queries by officers (voice or text) 
using Google Gemini 2.5 Flash.
"""

import os
import json
import base64
from datetime import datetime

from google import genai
from google.genai import types

from .models import QueryResponse, IncidentNarrative
from .narrative_engine import NarrativeEngine

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
7. Format your response as plain text, no markdown block.

Your response MUST follow this exact JSON format:
{{
  "answer": "Your detailed answer here",
  "safety_assessment": "safe|caution|unsafe",
  "confidence": "high|medium|low"
}}
"""

class GeminiQueryService:
    def __init__(self, engine: NarrativeEngine):
        self._engine = engine

    async def query(self, request_data: dict) -> QueryResponse:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY environment variable is not set."
            )

        narrative_context = self._engine.to_prompt_context()
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            narrative_context=narrative_context
        )

        client = genai.Client(api_key=api_key)

        parts = [types.Part.from_text(system_prompt + "\n\nOfficer's query:")]

        question = request_data.get("question")
        if question:
            parts.append(types.Part.from_text(question))

        audio_base64 = request_data.get("audio_base64")
        audio_mime_type = request_data.get("audio_mime_type")

        if audio_base64 and audio_mime_type:
            audio_bytes = base64.b64decode(audio_base64)
            parts.append(
                types.Part.from_bytes(
                    data=audio_bytes,
                    mime_type=audio_mime_type
                )
            )

        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=parts,
            )

            raw_text = response.text.strip()
            return self._parse_response(raw_text)

        except Exception as e:
            raise RuntimeError(f"Gemini API error: {str(e)}")

    def _parse_response(self, raw_text: str) -> QueryResponse:
        try:
            cleaned = raw_text
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
            return QueryResponse(
                answer=raw_text,
                safety_assessment="unknown",
                confidence="medium",
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                sources_referenced=self._engine.event_count,
            )
