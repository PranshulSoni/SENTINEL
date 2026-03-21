import logging
from collections import deque

from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class OperatorQueueManager:
    def __init__(self):
        self.cities_operators = {
            "nyc": [
                'Tariq Rahimi', 'Nasrin Ahmadzai', 'Bilal Chaudhry',
                'Zara Siddiqui', 'Farrukh Yusupov', 'Layla Karimi'
            ],
            "chandigarh": [
                'Arjun Mehta', 'Priya Sharma', 'Rohit Bhatia',
                'Ananya Kapoor', 'Vikram Sandhu', 'Neha Grewal'
            ]
        }
        
        self.state: Dict[str, Dict[str, Any]] = {
            city: {
                "ready": deque(ops), 
                "blocked": set(), 
                "wait": deque()
            } for city, ops in self.cities_operators.items()
        }
        self.db: Any = None

    async def enqueue_incident(self, city: str, incident_id: str, ws_manager=None) -> Optional[str]:
        """Queue an incident and if an operator is ready, assign it immediately."""
        city_state = self.state.get(city)
        if not city_state:
            return None
        
        if len(city_state["ready"]) > 0:
            operator = city_state["ready"].popleft()
            city_state["blocked"].add(operator)
            
            # Update DB
            if self.db is not None and hasattr(self.db, "incidents"):
                await self.db.incidents.update_one(
                    {"_id": incident_id},
                    {"$set": {"assigned_operator": operator}}
                )
            
            logger.info(f"Direct assignment: {incident_id} -> {operator} in {city}")
            
            if ws_manager:
                await ws_manager.broadcast({
                    "type": "incident_assigned",
                    "data": {"incident_id": str(incident_id), "operator": operator, "city": city}
                })
            return operator
        else:
            city_state["wait"].append(incident_id)
            logger.info(f"Queued incident: {incident_id} in {city} (Waiting...)")
            return None

    async def free_operator(self, city: str, operator: str, ws_manager=None):
        """Free an operator, and if wait queue has incidents, assign immediately."""
        city_state = self.state.get(city)
        if not city_state:
            return
            
        if operator in city_state["blocked"]:
            city_state["blocked"].remove(operator)
        
        if len(city_state["wait"]) > 0:
            next_incident_id = city_state["wait"].popleft()
            city_state["blocked"].add(operator)
            
            if self.db is not None and hasattr(self.db, "incidents"):
                await self.db.incidents.update_one(
                    {"_id": next_incident_id},
                    {"$set": {"assigned_operator": operator}}
                )
            
            logger.info(f"Wait queue assignment: {next_incident_id} -> {operator} in {city}")
            
            if ws_manager:
                await ws_manager.broadcast({
                    "type": "incident_assigned",
                    "data": {"incident_id": str(next_incident_id), "operator": operator, "city": city}
                })
        else:
            city_state["ready"].append(operator)
            logger.info(f"Freed operator: {operator} in {city}. Ready queue size: {len(city_state['ready'])}")
