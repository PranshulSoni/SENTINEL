"""
Sentinel Incident Rules Engine.
Centralizes severity radii and other domain-specific rules.
"""
from typing import Dict, Any
from domain.priority import PriorityLevel, calculate_priority

# Radius in degrees for congestion zones based on severity
SEVERITY_RADIUS_DEG = {
    "critical": 0.005,
    "major": 0.004,
    "moderate": 0.003,
    "minor": 0.002,
    "unknown": 0.002,
}

class IncidentRules:
    @staticmethod
    def get_radius(severity: str) -> float:
        """Get the congestion radius in degrees for a given severity."""
        return SEVERITY_RADIUS_DEG.get(severity.lower(), 0.003)

    @staticmethod
    def evaluate(incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate an incident and return metadata for UI/Processing.
        Returns: {priority, radius, is_active, ...}
        """
        severity = str(incident_data.get("severity", "moderate")).lower()
        priority = calculate_priority(incident_data)
        radius = IncidentRules.get_radius(severity)
        
        return {
            "priority": priority,
            "radius": radius,
            "severity_label": severity.upper(),
            "is_emergency": priority in (PriorityLevel.P0, PriorityLevel.P1),
        }
