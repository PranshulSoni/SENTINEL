"""
Sentinel Incident Priority Engine.
Defines P0-P3 priority logic based on incident metadata.
"""
from enum import Enum
from typing import Dict, Any

class PriorityLevel(str, Enum):
    P0 = "P0"  # CRITICAL: Locks UI, top banner
    P1 = "P1"  # HIGH: Sticky, pulsing
    P2 = "P2"  # MEDIUM: Normal card
    P3 = "P3"  # LOW: Log only

def calculate_priority(incident_data: Dict[str, Any]) -> PriorityLevel:
    """Determine urgency level based on incident severity and type."""
    severity = str(incident_data.get("severity", "moderate")).lower()
    incident_type = str(incident_data.get("type", "unknown")).lower()
    
    # P0: Extreme danger or life-safety
    if severity == "critical" or "fire" in incident_type or "major_accident" in incident_type:
        return PriorityLevel.P0
        
    # P1: High impact, major congestion
    if severity == "major" or "accident" in incident_type or "blocked_road" in incident_type:
        return PriorityLevel.P1
        
    # P2: Normal traffic incident
    if severity == "moderate" or "congestion" in incident_type or "stalled_vehicle" in incident_type:
        return PriorityLevel.P2
        
    # P3: Minor or informational
    return PriorityLevel.P3
