import logging
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class PromptBuilder:
    """Assembles structured prompts for the traffic incident co-pilot LLM."""
    
    SYSTEM_TEMPLATE = """You are a traffic incident co-pilot for {city_display}.
Current incident: {severity} on {street} at {cross_street}.
Active for: {duration_minutes} minutes.

LIVE FEED STATE (last 5s tick):
{segments_table}

AVAILABLE DIVERSION ROUTES (computed):
{diversions_text}

NEARBY INTERSECTIONS:
{intersections_text}

SIGNAL BASELINES:
{baselines_table}

{collision_history}

{cctv_context}

Generate a response with exactly five sections:
[SIGNAL_RETIMING] — name intersections, give exact phase durations; if ambulance detected, include green-corridor suggestions
[DIVERSIONS] — activation sequence with load estimates; if ambulance, include fastest hospital route
[ALERTS] — VMS | RADIO | SOCIAL subsections; if injury confirmed, flag for hospital alert
[NARRATIVE_UPDATE] — plain English incident status incorporating visual confirmation
[CCTV_SUMMARY] — one paragraph summarising what the camera confirms, any injuries, any ambulance routing, anomalies

Use ONLY the intersection names provided above. Do not generate street names.
Professional emergency operations tone."""

    CHAT_SYSTEM_TEMPLATE = """You are a traffic incident co-pilot assistant for {city_display}.
You help traffic control officers understand and manage active incidents.
Answer questions using the provided feed data, CCTV intelligence, and collision history.
Be concise, factual, and use a professional emergency operations tone.

CURRENT SITUATION:
{incident_summary}

LIVE FEED STATE:
{segments_table}

{cctv_context}

{collision_history}"""

    def build_incident_prompt(
        self,
        city: str,
        incident: dict,
        segments: list[dict],
        diversions: list[dict],
        baselines: dict,
        collision_context: str = "",
        cctv_context: str = "",
    ) -> tuple[str, str]:
        """
        Build system prompt and user content for incident LLM call.
        Returns (system_prompt, user_content).
        """
        city_display = "New York City" if city == "nyc" else "Chandigarh"
        
        # Duration
        detected_at = incident.get("detected_at", "")
        if detected_at:
            try:
                if isinstance(detected_at, str):
                    dt = datetime.fromisoformat(detected_at.replace("Z", "+00:00"))
                else:
                    dt = detected_at
                duration = (datetime.now(timezone.utc) - dt).total_seconds() / 60
            except Exception:
                duration = 0
        else:
            duration = 0
        
        # Segments table
        segments_table = self._format_segments_table(segments)
        
        # Diversions text
        diversions_text = self._format_diversions(diversions)
        
        # Intersections from baselines
        intersections_text = "\n".join(
            f"  - {name}" for name in baselines.keys()
        ) if baselines else "  No intersection data available"
        
        # Baselines table
        baselines_table = self._format_baselines_table(baselines)
        
        # CCTV context
        cctv_section = f"CCTV VISUAL INTELLIGENCE:\n{cctv_context}" if cctv_context else "CCTV: No camera data available"
        
        # Collision history
        collision_section = collision_context if collision_context else ""
        
        system_prompt = self.SYSTEM_TEMPLATE.format(
            city_display=city_display,
            severity=incident.get("severity", "unknown"),
            street=incident.get("on_street", "Unknown Street"),
            cross_street=incident.get("cross_street", ""),
            duration_minutes=round(duration, 1),
            segments_table=segments_table,
            diversions_text=diversions_text,
            intersections_text=intersections_text,
            baselines_table=baselines_table,
            collision_history=collision_section,
            cctv_context=cctv_section,
        )
        
        user_content = (
            f"An incident has been detected. Analyze the current traffic state and "
            f"generate your five-section response with specific, actionable recommendations."
        )
        
        return system_prompt, user_content
    
    def build_chat_prompt(
        self,
        city: str,
        incident: Optional[dict],
        segments: list[dict],
        collision_context: str = "",
        cctv_context: str = "",
    ) -> str:
        """Build system prompt for chat/conversational mode."""
        city_display = "New York City" if city == "nyc" else "Chandigarh"
        
        if incident:
            incident_summary = (
                f"Active {incident.get('severity', 'unknown')} incident on "
                f"{incident.get('on_street', 'Unknown')}. "
                f"Status: {incident.get('status', 'unknown')}. "
                f"Affected segments: {len(incident.get('affected_segment_ids', []))}."
            )
        else:
            incident_summary = "No active incidents."
        
        segments_table = self._format_segments_table(segments[:10])  # Limit for chat context
        
        cctv_section = f"CCTV INTELLIGENCE:\n{cctv_context}" if cctv_context else ""
        collision_section = collision_context if collision_context else ""
        
        return self.CHAT_SYSTEM_TEMPLATE.format(
            city_display=city_display,
            incident_summary=incident_summary,
            segments_table=segments_table,
            cctv_context=cctv_section,
            collision_history=collision_section,
        )
    
    def _format_segments_table(self, segments: list[dict]) -> str:
        """Format segment data as a readable table."""
        if not segments:
            return "  No segment data available"
        
        lines = ["  SEGMENT                          | SPEED | STATUS"]
        lines.append("  " + "-" * 55)
        for seg in segments:
            name = seg.get("link_name", seg.get("link_id", "?"))[:35].ljust(35)
            speed = f"{seg.get('speed', 0):.1f} mph".rjust(10)
            status = seg.get("status", "?").ljust(8)
            lines.append(f"  {name}| {speed} | {status}")
        return "\n".join(lines)
    
    def _format_diversions(self, diversions: list[dict]) -> str:
        """Format diversion routes for the prompt."""
        if not diversions:
            return "  No diversion routes computed"
        
        lines = []
        for d in diversions:
            streets = " → ".join(d.get("segment_names", d.get("path", ["?"])))
            lines.append(
                f"  {d.get('name', 'Route')}: {streets}\n"
                f"    Distance: {d.get('total_length_km', '?')} km, "
                f"Est. time: {d.get('estimated_extra_minutes', '?')} min"
            )
        return "\n".join(lines)
    
    def _format_baselines_table(self, baselines: dict) -> str:
        """Format signal baselines as a readable table."""
        if not baselines:
            return "  No signal baseline data available"
        
        lines = ["  INTERSECTION                     | NS GREEN | EW GREEN | CYCLE"]
        lines.append("  " + "-" * 65)
        for name, data in baselines.items():
            iname = name[:35].ljust(35)
            ns = f"{data.get('ns_green', '?')}s".rjust(8)
            ew = f"{data.get('ew_green', '?')}s".rjust(8)
            cycle = f"{data.get('cycle_length', '?')}s".rjust(5)
            lines.append(f"  {iname}| {ns} | {ew} | {cycle}")
        return "\n".join(lines)
