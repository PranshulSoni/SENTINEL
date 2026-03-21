"""
SENTINEL — Seed Data
Realistic multi-vehicle highway incident with HazMat spill.
Provides a fully populated IncidentNarrative for demo / development purposes.
"""

from datetime import datetime, timedelta
from .models import IncidentEvent, IncidentNarrative


def create_demo_narrative() -> IncidentNarrative:
    """
    Build a realistic traffic incident narrative with 10 chronological events.
    Scenario: Multi-vehicle collision on I-85 Southbound with overturned tanker
    and diesel fuel spill — cleanup in progress.
    """
    base = datetime(2026, 3, 21, 13, 0, 0)

    events = [
        IncidentEvent(
            id=1,
            timestamp=(base).strftime("%Y-%m-%d %H:%M:%S"),
            category="dispatch",
            description=(
                "Multi-vehicle collision reported on I-85 South near Mile Marker 42. "
                "Caller reports at least 3 vehicles involved, one overturned tanker truck."
            ),
            severity="critical",
            reported_by="911 Dispatch",
        ),
        IncidentEvent(
            id=2,
            timestamp=(base + timedelta(minutes=3)).strftime("%Y-%m-%d %H:%M:%S"),
            category="traffic",
            description=(
                "All southbound lanes CLOSED between Exit 43 and Exit 41. "
                "Northbound lanes reduced to one lane due to debris field."
            ),
            severity="critical",
            reported_by="Traffic Control",
        ),
        IncidentEvent(
            id=3,
            timestamp=(base + timedelta(minutes=7)).strftime("%Y-%m-%d %H:%M:%S"),
            category="medical",
            description=(
                "EMS on scene. 2 patients with minor injuries being treated. "
                "Tanker driver extracted, conscious, transported Code 2 to Memorial Hospital."
            ),
            severity="high",
            reported_by="EMS Unit 14",
        ),
        IncidentEvent(
            id=4,
            timestamp=(base + timedelta(minutes=12)).strftime("%Y-%m-%d %H:%M:%S"),
            category="hazard",
            description=(
                "HAZMAT ALERT: Diesel fuel leak confirmed from overturned tanker. "
                "Approximately 200 gallons spilled across southbound lanes 2 and 3. "
                "Fire department deploying containment booms."
            ),
            severity="critical",
            reported_by="HazMat Team Alpha",
        ),
        IncidentEvent(
            id=5,
            timestamp=(base + timedelta(minutes=18)).strftime("%Y-%m-%d %H:%M:%S"),
            category="resource",
            description=(
                "Heavy-duty tow truck dispatched from Johnson's Towing (ETA 25 min). "
                "Additional patrol units redirecting traffic at Exit 44."
            ),
            severity="medium",
            reported_by="Dispatch",
        ),
        IncidentEvent(
            id=6,
            timestamp=(base + timedelta(minutes=25)).strftime("%Y-%m-%d %H:%M:%S"),
            category="update",
            description=(
                "Fuel spill containment 60% complete. Absorbent material being applied. "
                "Environmental Services notified. No fuel has reached storm drains."
            ),
            severity="high",
            reported_by="HazMat Team Alpha",
        ),
        IncidentEvent(
            id=7,
            timestamp=(base + timedelta(minutes=32)).strftime("%Y-%m-%d %H:%M:%S"),
            category="traffic",
            description=(
                "Northbound lane restriction LIFTED — all northbound lanes now open. "
                "Debris cleared from northbound shoulder."
            ),
            severity="info",
            reported_by="Traffic Control",
        ),
        IncidentEvent(
            id=8,
            timestamp=(base + timedelta(minutes=40)).strftime("%Y-%m-%d %H:%M:%S"),
            category="update",
            description=(
                "Tanker righted by crane unit. Remaining fuel transferred to containment vehicle. "
                "Spill cleanup 85% complete. Southbound Lane 1 (leftmost) clear of contamination."
            ),
            severity="medium",
            reported_by="HazMat Team Alpha",
        ),
        IncidentEvent(
            id=9,
            timestamp=(base + timedelta(minutes=48)).strftime("%Y-%m-%d %H:%M:%S"),
            category="update",
            description=(
                "Vehicle wreckage removal in progress. 2 of 3 damaged vehicles loaded onto flatbeds. "
                "Overturned tanker being prepped for tow."
            ),
            severity="medium",
            reported_by="Tow Crew Lead",
        ),
        IncidentEvent(
            id=10,
            timestamp=(base + timedelta(minutes=55)).strftime("%Y-%m-%d %H:%M:%S"),
            category="update",
            description=(
                "Fuel spill cleanup COMPLETE on Lane 1. Lanes 2 and 3 still have residual "
                "contamination — surface treatment ongoing. Estimated 20 more minutes for full clearance."
            ),
            severity="medium",
            reported_by="HazMat Team Alpha",
        ),
    ]

    return IncidentNarrative(
        incident_id="INC-2026-03-21-0847",
        incident_type="Multi-Vehicle Collision with HazMat Spill",
        location="I-85 Southbound, Mile Marker 42, near Exit 42 (Industrial Blvd)",
        started_at=base.strftime("%Y-%m-%d %H:%M:%S"),
        commander="Sgt. Rachel Torres",
        status="active",
        hazmat_involved=True,
        lanes_affected={
            "southbound_lane_1": "clear — pending inspection",
            "southbound_lane_2": "closed — fuel contamination cleanup",
            "southbound_lane_3": "closed — fuel contamination cleanup",
            "southbound_shoulder": "closed — staging area",
            "northbound_all": "open",
        },
        weather="Partly cloudy, 72°F, light wind SW 8mph",
        events=events,
    )
