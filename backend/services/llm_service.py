import re
import asyncio
import logging
import time
from typing import Optional

try:
    import httpx
except Exception:  # pragma: no cover - optional for parser-only test runs.
    httpx = None

logger = logging.getLogger(__name__)


class LLMService:
    """Multi-provider LLM service with Groq → Gemini → OpenRouter fallback."""

    def __init__(self, provider: str = "groq", model: str = "openai/gpt-oss-120b",
                 groq_model: str = "llama-3.1-8b-instant",
                 groq_key: str = "", gemini_key: str = "", openrouter_key: str = ""):
        self.provider = provider
        self.model = model
        self.groq_model = groq_model
        self.groq_key = groq_key
        self.gemini_key = gemini_key
        self.openrouter_key = openrouter_key
        self.providers = self._build_provider_list()
        logger.info(f"LLM providers: {self.providers}")

    def _build_provider_list(self) -> list[str]:
        """Build ordered provider list: preferred provider first, then others."""
        all_available = []
        if self.groq_key:
            all_available.append("groq")
        if self.gemini_key:
            all_available.append("gemini")
        if self.openrouter_key:
            all_available.append("openrouter")
        # Put preferred provider first
        if self.provider in all_available:
            all_available.remove(self.provider)
            all_available.insert(0, self.provider)
        return all_available

    async def generate(self, system_prompt: str, user_content: str,
                       max_tokens: int = 1000) -> Optional[str]:
        """Try each provider in order until one succeeds."""
        t0 = time.time()
        last_error = None

        for provider in self.providers:
            try:
                if provider == "groq":
                    result = await self._call_groq(system_prompt, user_content, max_tokens)
                elif provider == "gemini":
                    result = await self._call_gemini(system_prompt, user_content, max_tokens)
                elif provider == "openrouter":
                    result = await self._call_openrouter(system_prompt, user_content, max_tokens)
                else:
                    continue

                if result:
                    logger.info(f"LLM generated {len(result)} chars via {provider} in {time.time() - t0:.1f}s")
                    return result
            except Exception as e:
                last_error = e
                logger.warning(f"LLM provider {provider} failed: {type(e).__name__}: {e}")
                continue

        logger.error(f"All LLM providers failed. Last error: {last_error}")
        return None

    # ── Groq (official SDK, thread-wrapped for async) ──────────────────

    async def _call_groq(self, system_prompt: str, user_content: str,
                         max_tokens: int = 1000) -> str:
        """Call Groq via their official SDK (wrapped in thread for async)."""
        def _sync_call():
            from groq import Groq
            client = Groq(api_key=self.groq_key)
            response = client.chat.completions.create(
                model=self.groq_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=max_tokens,
                temperature=0.3,
            )
            return response.choices[0].message.content

        return await asyncio.to_thread(_sync_call)

    async def _call_groq_chat(self, messages: list[dict], max_tokens: int) -> str:
        """Call Groq chat API via SDK (thread-wrapped)."""
        def _sync_call():
            from groq import Groq
            client = Groq(api_key=self.groq_key)
            response = client.chat.completions.create(
                model=self.groq_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.3,
            )
            return response.choices[0].message.content

        return await asyncio.to_thread(_sync_call)

    # ── Gemini (official SDK, thread-wrapped for async) ────────────────

    async def _call_gemini(self, system_prompt: str, user_content: str,
                           max_tokens: int = 1000) -> str:
        """Call Gemini via Google's official SDK (wrapped in thread for async)."""
        def _sync_call():
            import google.generativeai as genai
            genai.configure(api_key=self.gemini_key)
            model = genai.GenerativeModel("gemini-2.0-flash")
            combined = f"{system_prompt}\n\n{user_content}"
            response = model.generate_content(
                combined,
                generation_config=genai.GenerationConfig(
                    max_output_tokens=max_tokens,
                    temperature=0.3,
                ),
            )
            return response.text

        return await asyncio.to_thread(_sync_call)

    # ── OpenRouter (httpx async, no blocking SDK) ─────────────────────

    async def _call_openrouter(self, system_prompt: str, user_content: str,
                               max_tokens: int = 1000) -> str:
        """Call OpenRouter via httpx async (proper async, no blocking)."""
        return await self._call_openrouter_raw([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ], max_tokens)

    async def _call_openrouter_chat(self, messages: list[dict], max_tokens: int) -> str:
        """Call OpenRouter chat via httpx async."""
        return await self._call_openrouter_raw(messages, max_tokens)

    async def _call_openrouter_raw(self, messages: list[dict], max_tokens: int) -> str:
        """Shared OpenRouter call with retry logic."""
        if httpx is None:
            raise RuntimeError("httpx is required for OpenRouter calls")
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=45.0) as client:
                    resp = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.openrouter_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://sentinel-copilot.app",
                        },
                        json={
                            "model": self.model,
                            "messages": messages,
                            "max_tokens": max_tokens,
                            "temperature": 0.3,
                        },
                    )
                    if not resp.is_success:
                        logger.error(f"OpenRouter HTTP {resp.status_code}: {resp.text[:500]}")
                        resp.raise_for_status()
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
            except Exception as e:
                logger.warning(f"OpenRouter attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    await asyncio.sleep(2 * (attempt + 1))
                else:
                    raise

    # ── Chat (multi-turn) ─────────────────────────────────────────────

    async def generate_chat_response(self, messages: list[dict],
                                     max_tokens: int = 1000) -> Optional[str]:
        """Generate chat response from a multi-turn conversation."""
        last_error = None
        for provider in self.providers:
            try:
                if provider == "groq":
                    return await self._call_groq_chat(messages, max_tokens)
                elif provider == "gemini":
                    full_text = "\n".join(f"[{m['role']}]: {m['content']}" for m in messages)
                    return await self._call_gemini("", full_text, max_tokens)
                elif provider == "openrouter":
                    return await self._call_openrouter_chat(messages, max_tokens)
            except Exception as e:
                last_error = e
                logger.warning(f"Chat LLM provider {provider} failed: {type(e).__name__}: {e}")
                continue

        logger.error(f"All LLM providers failed for chat. Last error: {last_error}")
        return None

    async def chat(self, system_prompt: str, user_content: str,
                   max_tokens: int = 1000) -> Optional[str]:
        """Alias for generate() used by chat endpoints."""
        return await self.generate(system_prompt, user_content, max_tokens)
    
    @staticmethod
    def _parse_signal_retiming(text: str) -> dict:
        """Parse [SIGNAL_RETIMING] content into structured intersection objects."""
        intersections = []
        if not text:
            return {"intersections": [], "raw_text": ""}

        # Group sentences by intersection: accumulate until the next intersection mention
        intersection_pattern = re.compile(
            r"(?:on|at|for|near)\s+"
            r"((?:[NSEW]\.?\s+)?"
            r"(?:\d+\s*(?:st|nd|rd|th)\s+)?"
            r"[A-Za-z0-9][A-Za-z0-9\s.\']+?"
            r"(?:\s*(?:&|and|/|near|at)\s*"
            r"(?:[NSEW]\.?\s+)?"
            r"(?:\d+\s*(?:st|nd|rd|th)\s+)?"
            r"[A-Za-z0-9][A-Za-z0-9\s.\']+?)?)"
            r"(?=\s+(?:from|to|at|green|phase|cycle|current)|\s*[,.])",
            re.IGNORECASE,
        )
        timing_from_to = re.compile(r"from\s+(\d+)\s*s?\s+to\s+(\d+)\s*s?", re.IGNORECASE)
        timing_to = re.compile(r"(?:extend|reduce|increase|decrease|set|change)\s+.*?to\s+(\d+)\s*s?", re.IGNORECASE)

        timing_from_to = re.compile(r'from\s+(\d+)\s*s?\s+to\s+(\d+)\s*s?', re.IGNORECASE)
        timing_to = re.compile(r'(?:extend|reduce|increase|decrease|set|change)\s+.*?to\s+(\d+)\s*s?', re.IGNORECASE)

        # Broader sentence grouping: split on period-separated chunks that mention intersections
        chunks = re.split(r'(?<=\.)\s+', text.strip())
        processed_names = set()

        for chunk in chunks:
            name_match = intersection_pattern.search(chunk)
            if not name_match:
                continue

            name = name_match.group(1).strip().rstrip(".,;")
            if name.lower() in {"current", "phase", "green", "cycle", "signal", "the"}:
                continue
            if name in seen:
                continue
            seen.add(name)

            entry = {
                "name": name,
                "current_ns_green": 0,
                "recommended_ns_green": 0,
                "current_ew_green": 0,
                "recommended_ew_green": 0,
                # aliases for backend model compatibility
                "current_green_ns": 0,
                "recommended_green_ns": 0,
                "current_green_ew": 0,
                "recommended_green_ew": 0,
                "reasoning": chunk.strip(),
            }

            chunk_lower = chunk.lower()
            is_reduce = bool(re.search(r'reduce|decrease|shorten|cut', chunk_lower))
            is_ew = bool(re.search(r'east|west|ew|e/w|eastbound|westbound', chunk_lower))

            ft = timing_from_to.search(chunk)
            if ft:
                from_val, to_val = int(ft.group(1)), int(ft.group(2))
                if is_ew or is_reduce:
                    entry["current_ew_green"] = from_val
                    entry["recommended_ew_green"] = to_val
                    entry["current_green_ew"] = from_val
                    entry["recommended_green_ew"] = to_val
                else:
                    entry["current_ns_green"] = from_val
                    entry["recommended_ns_green"] = to_val
                    entry["current_green_ns"] = from_val
                    entry["recommended_green_ns"] = to_val
            else:
                to_match = timing_to.search(chunk)
                if to_match:
                    to_val = int(to_match.group(1))
                    if is_ew or is_reduce:
                        entry["recommended_ew_green"] = to_val
                        entry["recommended_green_ew"] = to_val
                    else:
                        entry["recommended_ns_green"] = to_val
                        entry["recommended_green_ns"] = to_val

            intersections.append(entry)

        if not intersections:
            intersections.append(
                {
                    "name": "Parsed from LLM",
                    "current_ns_green": 0,
                    "recommended_ns_green": 0,
                    "current_ew_green": 0,
                    "recommended_ew_green": 0,
                    "current_green_ns": 0,
                    "recommended_green_ns": 0,
                    "current_green_ew": 0,
                    "recommended_green_ew": 0,
                    "reasoning": text.strip(),
                }
            )

        return {"intersections": intersections, "raw_text": text}

    @staticmethod
    def _parse_diversions(text: str) -> dict:
        """Parse diversions text into structured route objects."""
        routes = []
        if not text:
            return {"routes": [], "raw_text": ""}

        route_name_pattern = re.compile(
            r'((?:Diversion|Route|Alt(?:ernate)?(?:\s*Route)?)\s*[A-Z0-9]?(?:\s*\d*)?)',
            re.IGNORECASE
        )
        path_pattern = re.compile(
            r':\s*(.*?)(?:\.\s|$)',
            re.DOTALL
        )
        path_segment_split = re.compile(r'\s*(?:→|->|then|to)\s*')
        pct_pattern = re.compile(r'~?(\d+)\s*%')
        condition_pattern = re.compile(
            r'(?:activate|trigger|when|if)\s+(.*?)(?:\.|,|$)',
            re.IGNORECASE
        )

        # Split text into chunks per diversion route
        # Try splitting on route name boundaries
        parts = re.split(r'(?=(?:Diversion|Route|Alt(?:ernate)?\s*Route)\s*[A-Z0-9])', text, flags=re.IGNORECASE)

        priority = 0
        for part in parts:
            part = part.strip()
            if not part:
                continue

            name_match = route_name_pattern.search(part)
            if not name_match:
                continue

            priority += 1
            name = name_match.group(1).strip()

            # Extract path: text after colon or after the route name
            path_strs = []
            path_match = path_pattern.search(part[name_match.end():])
            if path_match:
                raw_path = path_match.group(1).strip()
                # Remove trailing clauses like "Expected to absorb..."
                raw_path = re.split(r'(?:Expected|Absorb|If\s+)', raw_path, flags=re.IGNORECASE)[0].strip()
                path_strs = [
                    re.sub(r'\s*\(.*?\)\s*', '', s).strip().rstrip('.,;')
                    for s in path_segment_split.split(raw_path) if s.strip()
                ]

            pct_match = pct_pattern.search(part)
            absorption = int(pct_match.group(1)) if pct_match else 0

            cond_match = condition_pattern.search(part)
            if cond_match:
                condition = cond_match.group(1).strip().rstrip('.,;')
            elif priority == 1:
                condition = "immediate"
            else:
                condition = "conditional"

            routes.append({
                "priority": priority,
                "name": name,
                "path": path_strs if path_strs else [part.strip()],
                "estimated_absorption_pct": absorption,
                "activate_condition": condition,
            })

        if not routes:
            routes.append({
                "priority": 1,
                "name": "Diversion (parsed from LLM)",
                "path": [],
                "estimated_absorption_pct": 0,
                "activate_condition": text.strip(),
            })

        return {"routes": routes, "raw_text": text}

    @staticmethod
    def parse_structured_output(raw_text: str) -> dict:
        """Backward-compatible parser alias."""
        return LLMService.parse_structured_output_v2(raw_text)

    @staticmethod
    def parse_structured_output_v2(raw_text: str) -> dict:
        """Parse the 5-section structured LLM output into a v2 dict."""
        sections = {
            "version": "v2",
            "signal_retiming": {"intersections": [], "raw_text": ""},
            "diversions": {"routes": [], "raw_text": ""},
            "alerts": {"vms": "", "radio": "", "social_media": ""},
            "narrative_update": "",
            "cctv_summary": "",
            "sections_present": [],
        }
        
        if not raw_text:
            return sections
        
        # Extract sections using markers
        section_patterns = {
            "signal_retiming": r"\[SIGNAL_RETIMING\](.*?)(?=\[DIVERSIONS\]|\[ALERTS\]|\[NARRATIVE_UPDATE\]|\[CCTV_SUMMARY\]|$)",
            "diversions": r"\[DIVERSIONS\](.*?)(?=\[ALERTS\]|\[NARRATIVE_UPDATE\]|\[CCTV_SUMMARY\]|$)",
            "alerts": r"\[ALERTS\](.*?)(?=\[NARRATIVE_UPDATE\]|\[CCTV_SUMMARY\]|$)",
            "narrative_update": r"\[NARRATIVE_UPDATE\](.*?)(?=\[CCTV_SUMMARY\]|$)",
            "cctv_summary": r"\[CCTV_SUMMARY\](.*?)$",
        }
        
        for key, pattern in section_patterns.items():
            match = re.search(pattern, raw_text, re.DOTALL)
            if match:
                sections["sections_present"].append(key)
                content = match.group(1).strip()
                if key == "signal_retiming":
                    sections["signal_retiming"] = LLMService._parse_signal_retiming(content)
                elif key == "diversions":
                    sections["diversions"] = LLMService._parse_diversions(content)
                elif key == "alerts":
                    vms_match = re.search(
                        r"(?:VMS|VARIABLE MESSAGE SIGN)[:\s]*(.*?)(?=RADIO|SOCIAL|$)",
                        content,
                        re.DOTALL | re.IGNORECASE,
                    )
                    radio_match = re.search(r"RADIO[:\s]*(.*?)(?=SOCIAL|$)", content, re.DOTALL | re.IGNORECASE)
                    social_match = re.search(r"SOCIAL(?:_MEDIA)?[:\s]*(.*?)$", content, re.DOTALL | re.IGNORECASE)
                    
                    sections["alerts"] = {
                        "vms": vms_match.group(1).strip() if vms_match else content,
                        "radio": radio_match.group(1).strip() if radio_match else "",
                        "social_media": social_match.group(1).strip() if social_match else "",
                    }
                else:
                    sections[key] = content

        # ── Fallbacks: if the LLM didn't use section markers, degrade gracefully ──
        # Always put raw LLM text in narrative so the operator can read the analysis
        if not sections["narrative_update"]:
            sections["narrative_update"] = raw_text.strip()

        # Attempt to extract signal/diversion data from the full text if markers missing
        if not sections["signal_retiming"]["intersections"]:
            sections["signal_retiming"] = LLMService._parse_signal_retiming(raw_text)
        if not sections["diversions"]["routes"]:
            sections["diversions"] = LLMService._parse_diversions(raw_text)

        # Ensure alerts always has at least a VMS message
        if not sections["alerts"]["vms"] and not sections["alerts"]["radio"]:
            sections["alerts"]["vms"] = raw_text.strip()[:500]  # First 500 chars as fallback alert

        # Ensure strict shape and trimmed fields.
        sections["narrative_update"] = (sections.get("narrative_update") or "").strip()
        sections["cctv_summary"] = (sections.get("cctv_summary") or "").strip()
        if not sections["cctv_summary"]:
            sections["cctv_summary"] = "No CCTV visual intelligence available."

        return sections
