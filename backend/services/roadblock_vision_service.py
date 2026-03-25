import base64
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_MODEL_URL = "https://router.huggingface.co/hf-inference/models/llava-hf/llava-1.5-7b-hf"

VISION_PROMPT = """You are a road condition analysis system.

Analyze the image and determine if there is a roadblock.

Rules:
- Roadblock includes debris, accidents, fallen trees, construction, flooding.
- Ignore normal traffic.

Output JSON:
{
  "roadblock_detected": true/false,
  "obstruction_score": 0-100,
  "explanation": "short reason"
}
"""


def _clamp_score(value: Any, default: int = 0) -> int:
    try:
        parsed = int(round(float(value)))
    except Exception:
        parsed = default
    return max(0, min(100, parsed))


def score_to_severity(score: int) -> str:
    if score <= 24:
        return "minor"
    if score <= 49:
        return "moderate"
    if score <= 74:
        return "major"
    return "critical"


@dataclass
class VisionAnalysis:
    roadblock_detected: bool
    obstruction_score: int
    confidence_score: int
    explanation: str
    parse_valid: bool
    raw_model_output: Any

    @property
    def severity(self) -> str:
        return score_to_severity(self.obstruction_score)

    def to_dict(self) -> dict[str, Any]:
        return {
            "roadblock_detected": bool(self.roadblock_detected),
            "obstruction_score": int(self.obstruction_score),
            "confidence_score": int(self.confidence_score),
            "explanation": str(self.explanation),
            "severity": self.severity,
            "severity_score": int(self.obstruction_score),
            "parse_valid": bool(self.parse_valid),
            "raw_model_output": self.raw_model_output,
        }


class RoadblockVisionService:
    def __init__(
        self,
        provider: str = "ollama",
        api_token: str = "",
        model_url: str = DEFAULT_MODEL_URL,
        timeout_sec: float = 18.0,
        ollama_base_url: str = "http://127.0.0.1:11434",
        ollama_model: str = "llava",
    ) -> None:
        normalized_provider = (provider or "ollama").strip().lower()
        if normalized_provider not in {"ollama", "hf"}:
            normalized_provider = "ollama"
        self.provider = normalized_provider
        self.api_token = (api_token or "").strip()
        self.model_url = self._normalize_model_url((model_url or DEFAULT_MODEL_URL).strip())
        self.timeout_sec = max(5.0, float(timeout_sec or 18.0))
        self.ollama_base_url = (ollama_base_url or "http://127.0.0.1:11434").rstrip("/")
        self.ollama_model = (ollama_model or "llava").strip() or "llava"

    @property
    def is_enabled(self) -> bool:
        if self.provider == "ollama":
            return bool(self.ollama_base_url and self.ollama_model)
        return bool(self.api_token and self.model_url)

    async def analyze_image(self, image_input: str) -> VisionAnalysis:
        if self.provider == "ollama":
            return await self._analyze_image_ollama(image_input)
        return await self._analyze_image_hf(image_input)

    async def _analyze_image_hf(self, image_input: str) -> VisionAnalysis:
        payload_image = self._normalize_image_input_for_hf(image_input)
        if not payload_image:
            return self._not_detected("Missing image input", raw=None, parse_valid=False)
        if not self.is_enabled:
            return self._not_detected("Vision service not configured", raw=None, parse_valid=False)

        payload = {
            "inputs": {
                "image": payload_image,
                "question": VISION_PROMPT,
            }
        }
        headers = {
            "Authorization": self._auth_header(self.api_token),
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                response = await client.post(self.model_url, headers=headers, json=payload)
            try:
                raw = response.json()
            except Exception:
                raw = response.text

            if response.status_code >= 400:
                logger.warning("Roadblock vision HTTP error %s: %s", response.status_code, raw)
                return self._not_detected(
                    f"Vision model HTTP {response.status_code}",
                    raw=raw,
                    parse_valid=False,
                )

            return self._parse_response(raw)
        except Exception as exc:
            logger.warning("Roadblock vision request failed: %s", exc)
            return self._not_detected("Vision analysis failed", raw=str(exc), parse_valid=False)

    async def _analyze_image_ollama(self, image_input: str) -> VisionAnalysis:
        image_b64 = self._normalize_image_input_for_ollama(image_input)
        if not image_b64:
            return self._not_detected("Missing image input", raw=None, parse_valid=False)
        if not self.is_enabled:
            return self._not_detected("Vision service not configured", raw=None, parse_valid=False)

        payload = {
            "model": self.ollama_model,
            "prompt": VISION_PROMPT,
            "images": [image_b64],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        }

        endpoint = f"{self.ollama_base_url}/api/generate"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                response = await client.post(endpoint, json=payload)
            try:
                raw = response.json()
            except Exception:
                raw = response.text

            if response.status_code >= 400:
                logger.warning("Roadblock vision (ollama) HTTP error %s: %s", response.status_code, raw)
                return self._not_detected(
                    f"Ollama vision HTTP {response.status_code}",
                    raw=raw,
                    parse_valid=False,
                )
            return self._parse_response(raw)
        except Exception as exc:
            logger.warning("Roadblock vision (ollama) request failed: %s", exc)
            return self._not_detected("Ollama vision analysis failed", raw=str(exc), parse_valid=False)

    def _parse_response(self, raw: Any) -> VisionAnalysis:
        parsed = self._extract_strict_json(raw)
        if not isinstance(parsed, dict):
            return self._not_detected("Vision output was not valid JSON", raw=raw, parse_valid=False)

        if "roadblock_detected" not in parsed:
            return self._not_detected(
                "Vision JSON missing 'roadblock_detected'",
                raw=raw,
                parse_valid=False,
            )
        detected_value = parsed.get("roadblock_detected")
        if not isinstance(detected_value, bool):
            return self._not_detected(
                "Vision JSON field 'roadblock_detected' was not boolean",
                raw=raw,
                parse_valid=False,
            )

        score = _clamp_score(parsed.get("obstruction_score"), default=0)
        explanation = str(parsed.get("explanation") or "Vision JSON parsed").strip()
        confidence = score if detected_value else max(15, int(score * 0.5))

        return VisionAnalysis(
            roadblock_detected=bool(detected_value),
            obstruction_score=score,
            confidence_score=_clamp_score(confidence, default=0),
            explanation=explanation,
            parse_valid=True,
            raw_model_output=raw,
        )

    def _not_detected(self, explanation: str, raw: Any, parse_valid: bool) -> VisionAnalysis:
        return VisionAnalysis(
            roadblock_detected=False,
            obstruction_score=0,
            confidence_score=0,
            explanation=explanation,
            parse_valid=parse_valid,
            raw_model_output=raw,
        )

    def _normalize_image_input_for_hf(self, image_input: str) -> str:
        value = str(image_input or "").strip()
        if not value:
            return ""
        if value.startswith("data:image/"):
            return value
        if value.startswith("http://") or value.startswith("https://"):
            return value
        if os.path.exists(value):
            try:
                with open(value, "rb") as fh:
                    encoded = base64.b64encode(fh.read()).decode("ascii")
                return f"data:image/jpeg;base64,{encoded}"
            except Exception:
                return ""

        if len(value) > 128 and re.fullmatch(r"[A-Za-z0-9+/=\s]+", value):
            return f"data:image/jpeg;base64,{value}"
        return value

    def _normalize_image_input_for_ollama(self, image_input: str) -> str:
        value = str(image_input or "").strip()
        if not value:
            return ""
        if value.startswith("data:image/"):
            parts = value.split(",", 1)
            return parts[1] if len(parts) == 2 else ""
        if os.path.exists(value):
            try:
                with open(value, "rb") as fh:
                    return base64.b64encode(fh.read()).decode("ascii")
            except Exception:
                return ""
        if len(value) > 128 and re.fullmatch(r"[A-Za-z0-9+/=\s]+", value):
            return re.sub(r"\s+", "", value)
        return ""

    @staticmethod
    def _extract_strict_json(raw: Any) -> dict[str, Any] | None:
        if isinstance(raw, dict):
            if "roadblock_detected" in raw:
                return raw
            for key in ("generated_text", "text", "answer", "output", "response"):
                text_candidate = raw.get(key)
                if isinstance(text_candidate, str):
                    parsed = RoadblockVisionService._parse_json_from_text(text_candidate)
                    if isinstance(parsed, dict):
                        return parsed
            return None

        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    for key in ("generated_text", "text", "answer", "output"):
                        text_candidate = item.get(key)
                        if isinstance(text_candidate, str):
                            parsed = RoadblockVisionService._parse_json_from_text(text_candidate)
                            if isinstance(parsed, dict):
                                return parsed
            return None

        if isinstance(raw, str):
            return RoadblockVisionService._parse_json_from_text(raw)
        return None

    @staticmethod
    def _parse_json_from_text(text: str) -> dict[str, Any] | None:
        cleaned = (text or "").strip()
        if not cleaned:
            return None
        try:
            obj = json.loads(cleaned)
            return obj if isinstance(obj, dict) else None
        except Exception:
            pass

        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return None
        candidate = match.group(0)
        try:
            obj = json.loads(candidate)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

    @staticmethod
    def _auth_header(token: str) -> str:
        value = (token or "").strip()
        if value.lower().startswith("bearer "):
            return value
        return f"Bearer {value}"

    @staticmethod
    def _normalize_model_url(model_url: str) -> str:
        """
        HF migrated from api-inference.huggingface.co to router.huggingface.co.
        Auto-upgrade legacy model URLs so existing env configs do not break.
        """
        url = (model_url or "").strip()
        if not url:
            return DEFAULT_MODEL_URL

        legacy_prefix = "https://api-inference.huggingface.co/models/"
        if url.startswith(legacy_prefix):
            model_id = url[len(legacy_prefix):].strip("/")
            return f"https://router.huggingface.co/hf-inference/models/{model_id}"
        return url
