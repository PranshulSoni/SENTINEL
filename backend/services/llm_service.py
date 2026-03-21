import os
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class LLMService:
    """Manages LLM calls with Groq (primary), Gemini (fallback), OpenRouter (backup)."""
    
    def __init__(self, provider: str = "groq", model: str = "llama-3.3-70b-versatile",
                 groq_key: str = "", gemini_key: str = "", openrouter_key: str = ""):
        self.provider = provider
        self.model = model
        self.groq_key = groq_key
        self.gemini_key = gemini_key
        self.openrouter_key = openrouter_key
    
    async def generate(self, system_prompt: str, user_content: str, 
                       max_tokens: int = 1500) -> Optional[str]:
        """Generate LLM response using configured provider."""
        providers = [self.provider] + [p for p in ["groq", "gemini", "openrouter"] if p != self.provider]
        
        for provider in providers:
            try:
                if provider == "groq" and self.groq_key:
                    return await self._call_groq(system_prompt, user_content, max_tokens)
                elif provider == "gemini" and self.gemini_key:
                    return await self._call_gemini(system_prompt, user_content, max_tokens)
                elif provider == "openrouter" and self.openrouter_key:
                    return await self._call_openrouter(system_prompt, user_content, max_tokens)
            except Exception as e:
                logger.warning(f"LLM provider {provider} failed: {e}")
                continue
        
        logger.error("All LLM providers failed")
        return None
    
    async def _call_groq(self, system_prompt: str, user_content: str, 
                         max_tokens: int) -> str:
        from groq import Groq
        
        client = Groq(api_key=self.groq_key)
        response = client.chat.completions.create(
            model=self.model if "llama" in self.model or "mixtral" in self.model else "llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            max_tokens=max_tokens
        )
        
        result = response.choices[0].message.content
        logger.info(f"Groq response: {len(result)} chars, "
                    f"tokens: {response.usage.prompt_tokens}+{response.usage.completion_tokens}")
        return result
    
    async def _call_gemini(self, system_prompt: str, user_content: str, 
                           max_tokens: int) -> str:
        import google.generativeai as genai
        
        genai.configure(api_key=self.gemini_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        
        response = model.generate_content(
            system_prompt + "\n\n" + user_content,
            generation_config=genai.GenerationConfig(max_output_tokens=max_tokens)
        )
        
        result = response.text
        logger.info(f"Gemini response: {len(result)} chars")
        return result
    
    async def _call_openrouter(self, system_prompt: str, user_content: str,
                               max_tokens: int) -> str:
        from openai import OpenAI
        
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.openrouter_key
        )
        
        response = client.chat.completions.create(
            model="meta-llama/llama-3.3-70b-instruct:free",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            max_tokens=max_tokens
        )
        
        result = response.choices[0].message.content
        logger.info(f"OpenRouter response: {len(result)} chars")
        return result
    
    async def generate_chat_response(self, messages: list[dict], 
                                     max_tokens: int = 1000) -> Optional[str]:
        """Generate chat response from a multi-turn conversation."""
        providers = [self.provider] + [p for p in ["groq", "gemini", "openrouter"] if p != self.provider]
        
        for provider in providers:
            try:
                if provider == "groq" and self.groq_key:
                    return await self._call_groq_chat(messages, max_tokens)
                elif provider == "gemini" and self.gemini_key:
                    # Gemini: concatenate messages
                    full_text = "\n".join(f"[{m['role']}]: {m['content']}" for m in messages)
                    return await self._call_gemini("", full_text, max_tokens)
                elif provider == "openrouter" and self.openrouter_key:
                    return await self._call_openrouter_chat(messages, max_tokens)
            except Exception as e:
                logger.warning(f"Chat LLM provider {provider} failed: {e}")
                continue
        
        logger.error("All LLM providers failed for chat")
        return None
    
    async def _call_groq_chat(self, messages: list[dict], max_tokens: int) -> str:
        from groq import Groq
        
        client = Groq(api_key=self.groq_key)
        response = client.chat.completions.create(
            model=self.model if "llama" in self.model or "mixtral" in self.model else "llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    
    async def _call_openrouter_chat(self, messages: list[dict], max_tokens: int) -> str:
        from openai import OpenAI
        
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.openrouter_key
        )
        response = client.chat.completions.create(
            model="meta-llama/llama-3.3-70b-instruct:free",
            messages=messages,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    
    @staticmethod
    def _parse_signal_retiming(text: str) -> dict:
        """Parse signal retiming text into structured intersection objects."""
        intersections = []
        if not text:
            return {"intersections": [], "raw_text": ""}

        # Split into sentences for per-intersection parsing
        sentences = re.split(r'(?<=[.])\s+', text.strip())

        # Group sentences by intersection: accumulate until the next intersection mention
        intersection_pattern = re.compile(
            r'(?:on|at|for|near)\s+'
            r'((?:[NSEW]\.?\s+)?'
            r'(?:\d+\s*(?:st|nd|rd|th)\s+)?'                  # optional ordinal prefix
            r'[A-Za-z0-9][A-Za-z0-9\s.\']+?'                  # street name
            r'(?:\s*(?:&|and|/|near|at)\s*'                    # connector
            r'(?:[NSEW]\.?\s+)?'
            r'(?:\d+\s*(?:st|nd|rd|th)\s+)?'
            r'[A-Za-z0-9][A-Za-z0-9\s.\']+?)?)'               # second street name
            r'(?=\s+(?:from|to|at|green|phase|cycle|current)|\s*[,.])',
            re.IGNORECASE
        )

        timing_from_to = re.compile(r'from\s+(\d+)\s*s?\s+to\s+(\d+)\s*s?', re.IGNORECASE)
        timing_to = re.compile(r'(?:extend|reduce|increase|decrease|set|change)\s+.*?to\s+(\d+)\s*s?', re.IGNORECASE)
        timing_single = re.compile(r'(\d+)\s*s(?:ec(?:ond)?s?)?', re.IGNORECASE)

        # Broader sentence grouping: split on period-separated chunks that mention intersections
        chunks = re.split(r'(?<=\.)\s+', text.strip())
        processed_names = set()

        for chunk in chunks:
            name_match = intersection_pattern.search(chunk)
            if not name_match:
                continue

            name = name_match.group(1).strip().rstrip('.,;')
            # Skip false-positive matches (common words, not intersection names)
            if name.lower() in ('current', 'phase', 'green', 'cycle', 'signal', 'the'):
                continue
            if name in processed_names:
                continue
            processed_names.add(name)

            entry = {
                "name": name,
                "current_ns_green": 0,
                "recommended_ns_green": 0,
                "current_ew_green": 0,
                "recommended_ew_green": 0,
                "reasoning": chunk.strip(),
            }

            chunk_lower = chunk.lower()
            is_extend = bool(re.search(r'extend|increase|lengthen', chunk_lower))
            is_reduce = bool(re.search(r'reduce|decrease|shorten|cut', chunk_lower))
            is_ns = bool(re.search(r'north|south|ns|n/s|northbound|southbound', chunk_lower))
            is_ew = bool(re.search(r'east|west|ew|e/w|eastbound|westbound', chunk_lower))

            ft = timing_from_to.search(chunk)
            if ft:
                from_val, to_val = int(ft.group(1)), int(ft.group(2))
                if is_ew or is_reduce:
                    entry["current_ew_green"] = from_val
                    entry["recommended_ew_green"] = to_val
                else:
                    entry["current_ns_green"] = from_val
                    entry["recommended_ns_green"] = to_val
            else:
                to_match = timing_to.search(chunk)
                if to_match:
                    to_val = int(to_match.group(1))
                    if is_ew or is_reduce:
                        entry["recommended_ew_green"] = to_val
                    else:
                        entry["recommended_ns_green"] = to_val

            intersections.append(entry)

        if not intersections:
            intersections.append({
                "name": "Parsed from LLM",
                "current_ns_green": 0,
                "recommended_ns_green": 0,
                "current_ew_green": 0,
                "recommended_ew_green": 0,
                "reasoning": text.strip(),
            })

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
        """Parse the 5-section structured LLM output into a dict."""
        sections = {
            "signal_retiming": {"intersections": [], "raw_text": ""},
            "diversions": {"routes": [], "raw_text": ""},
            "alerts": {"vms": "", "radio": "", "social_media": ""},
            "narrative_update": "",
            "cctv_summary": "",
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
                content = match.group(1).strip()
                if key == "signal_retiming":
                    sections["signal_retiming"] = LLMService._parse_signal_retiming(content)
                elif key == "diversions":
                    sections["diversions"] = LLMService._parse_diversions(content)
                elif key == "alerts":
                    vms_match = re.search(r"(?:VMS|VARIABLE MESSAGE SIGN)[:\s]*(.*?)(?=RADIO|SOCIAL|$)", content, re.DOTALL | re.IGNORECASE)
                    radio_match = re.search(r"RADIO[:\s]*(.*?)(?=SOCIAL|$)", content, re.DOTALL | re.IGNORECASE)
                    social_match = re.search(r"SOCIAL[:\s]*(.*?)$", content, re.DOTALL | re.IGNORECASE)
                    
                    sections["alerts"] = {
                        "vms": vms_match.group(1).strip() if vms_match else content,
                        "radio": radio_match.group(1).strip() if radio_match else "",
                        "social_media": social_match.group(1).strip() if social_match else "",
                    }
                else:
                    sections[key] = content
        
        return sections
