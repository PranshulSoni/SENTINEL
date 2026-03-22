import logging
from collections import deque
from typing import Any, Dict, Optional

from bson import ObjectId

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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _save_assignment(self, incident_id: str, operator: str):
        """Persist assigned_operator to MongoDB, handling ObjectId IDs."""
        if self.db is None or not hasattr(self.db, "incidents"):
            return
        try:
            oid = ObjectId(incident_id)
        except Exception:
            oid = incident_id  # fallback for non-ObjectId string IDs
        try:
            result = await self.db.incidents.update_one(
                {"_id": oid},
                {"$set": {"assigned_operator": operator}}
            )
            if result.modified_count == 0:
                logger.warning(f"DB assignment matched 0 docs for incident {incident_id}")
            else:
                logger.info(f"DB: assigned_operator={operator} on incident {incident_id}")
        except Exception as e:
            logger.error(f"Failed to persist assignment to DB: {e}")

    async def _broadcast_assignment(self, incident_id: str, operator: str, city: str, ws_manager):
        """Broadcast incident_assigned event to the city's WebSocket room."""
        if ws_manager is None:
            return
        msg = {
            "type": "incident_assigned",
            "data": {"incident_id": str(incident_id), "operator": operator, "city": city}
        }
        # Use broadcast_to_city if available (ConnectionManager), else fallback to broadcast
        if hasattr(ws_manager, "broadcast_to_city"):
            await ws_manager.broadcast_to_city(city, msg)
        else:
            await ws_manager.broadcast(msg)

    # ------------------------------------------------------------------
    # Startup reconciliation
    # ------------------------------------------------------------------

    async def reconcile_from_db(self, ws_manager=None):
        """
        Called at startup. Rebuild queue state from existing DB incidents:
        - Incidents with assigned_operator  → put operator in blocked set
        - Incidents with no assigned_operator → try to assign from ready queue
        """
        if self.db is None or not hasattr(self.db, "incidents"):
            return

        try:
            active_incidents = await self.db.incidents.find(
                {"status": "active"}
            ).to_list(500)
        except Exception as e:
            logger.error(f"reconcile_from_db: failed to load incidents: {e}")
            return

        logger.info(f"reconcile_from_db: found {len(active_incidents)} active incidents")

        for inc in active_incidents:
            incident_id = str(inc["_id"])
            city = inc.get("city", "nyc")
            assigned = inc.get("assigned_operator")

            city_state = self.state.get(city)
            if not city_state:
                continue

            if assigned:
                # Operator is busy — move them from ready → blocked if still in ready
                if assigned in city_state["ready"]:
                    city_state["ready"].remove(assigned)
                city_state["blocked"].add(assigned)
                logger.info(f"Reconcile: {incident_id} already assigned to {assigned} [{city}]")
            else:
                # Unassigned — try to assign now
                if len(city_state["ready"]) > 0:
                    operator = city_state["ready"].popleft()
                    city_state["blocked"].add(operator)
                    await self._save_assignment(incident_id, operator)
                    await self._broadcast_assignment(incident_id, operator, city, ws_manager)
                    logger.info(f"Reconcile: assigned {incident_id} → {operator} [{city}]")
                else:
                    # No operator available — put in wait queue
                    city_state["wait"].append(incident_id)
                    logger.info(f"Reconcile: {incident_id} queued to wait [{city}]")

        # Log final queue state
        for city, s in self.state.items():
            logger.info(
                f"Queue state [{city}]: ready={list(s['ready'])}, "
                f"blocked={s['blocked']}, wait={list(s['wait'])}"
            )

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    async def enqueue_incident(self, city: str, incident_id: str, ws_manager=None) -> Optional[str]:
        """Queue an incident; if an operator is ready in that city, assign immediately."""
        city_state = self.state.get(city)
        if not city_state:
            logger.warning(f"No queue state for city: {city}")
            return None

        if len(city_state["ready"]) > 0:
            operator = city_state["ready"].popleft()
            city_state["blocked"].add(operator)
            await self._save_assignment(incident_id, operator)
            await self._broadcast_assignment(incident_id, operator, city, ws_manager)
            logger.info(f"Direct assignment: {incident_id} → {operator} [{city}]")
            return operator
        else:
            city_state["wait"].append(incident_id)
            logger.info(f"No available operator: {incident_id} queued in [{city}] wait list")
            return None

    async def force_assign_incident(
        self,
        city: str,
        incident_id: str,
        operator: str,
        ws_manager=None,
    ) -> Optional[str]:
        """
        Force-assign an incident to a specific operator (used by demo injection).
        This bypasses round-robin queue selection and ensures the injector gets it.
        """
        city_state = self.state.get(city)
        if not city_state:
            logger.warning(f"No queue state for city: {city}")
            return None

        # Remove from ready list if present; keep blocked if already busy.
        if operator in city_state["ready"]:
            city_state["ready"].remove(operator)
        city_state["blocked"].add(operator)

        # If this incident was previously queued, remove it.
        if incident_id in city_state["wait"]:
            try:
                city_state["wait"].remove(incident_id)
            except ValueError:
                pass

        await self._save_assignment(incident_id, operator)
        await self._broadcast_assignment(incident_id, operator, city, ws_manager)
        logger.info(f"Forced assignment: {incident_id} → {operator} [{city}]")
        return operator

    async def free_operator(self, city: str, operator: str, ws_manager=None):
        """Free an operator after incident resolved; assign next from wait queue if any."""
        city_state = self.state.get(city)
        if not city_state:
            return

        city_state["blocked"].discard(operator)

        if len(city_state["wait"]) > 0:
            next_incident_id = city_state["wait"].popleft()
            city_state["blocked"].add(operator)
            await self._save_assignment(next_incident_id, operator)
            await self._broadcast_assignment(next_incident_id, operator, city, ws_manager)
            logger.info(f"Wait-queue assignment: {next_incident_id} → {operator} [{city}]")
        else:
            city_state["ready"].append(operator)
            logger.info(
                f"Operator {operator} returned to ready [{city}]. "
                f"Ready size: {len(city_state['ready'])}"
            )
