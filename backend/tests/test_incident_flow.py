import unittest
import sys
import time
from unittest.mock import AsyncMock, patch, MagicMock

# ─── 1. PRE-IMPORT MODULE INJECTION ──────────────────────────────────────────
# Prevent hardware-specific YOLO/OpenVINO loads from crashing the test process.
class MockMainGpu:
    YOLO = MagicMock
    process_accident_video = AsyncMock()
    AdvancedVehicleTracker = MagicMock()
    create_advanced_visualization = MagicMock()
    class config:
        YOLO_MODEL = "mock.pt"
        YOLO_DEVICE = "cpu"

sys.modules["main_gpu"] = MockMainGpu

class MockFeed:
    class FeedSimulator:
        active_city = "nyc"
        def __init__(self, *args, **kwargs): pass
        def on_frame(self, cb): pass
        def on_loop_end(self, cb): pass
        def get_current_segments(self): return []
        def set_city(self, city): pass
        async def load_city(self, city): pass
        async def start(self, **kwargs): pass
        async def stop(self): pass
        async def run(self): pass

sys.modules["services.feed_simulator"] = MockFeed


# ─── 2. HELPER: Build a fully async-compatible collection mock ───────────────
# Any method called on it (count_documents, insert_one, find_one, …) returns a
# coroutine automatically, so 'await collection.whatever()' always works.
def _make_async_collection(**extra_return_values):
    """Return an AsyncMock that behaves like a Motor collection."""
    coll = AsyncMock()
    coll.count_documents.return_value = 0
    coll.insert_one.return_value = MagicMock(inserted_id="test_id")
    coll.insert_many.return_value = MagicMock()
    coll.find_one.return_value = None
    coll.update_one.return_value = MagicMock(upserted_id=None)
    for k, v in extra_return_values.items():
        getattr(coll, k).return_value = v
    return coll


# ─── 3. Safe async no-op ─────────────────────────────────────────────────────
async def _noop(*args, **kwargs):
    pass


# ─── 4. Import app with all lifecycle calls neutralised ──────────────────────
with patch("db.connect_db", side_effect=_noop), \
     patch("db.close_db",   side_effect=_noop), \
     patch("db.congestion_zones", _make_async_collection()), \
     patch("db.intersections",    _make_async_collection()), \
     patch("db.road_segments",    _make_async_collection()), \
     patch("db.user_profiles",    _make_async_collection()), \
     patch("routers.surveillance._load_yolo_singleton", return_value=MagicMock()):
    from app import app
    from fastapi.testclient import TestClient

import db


# ─── 5. Test class ──────────────────────────────────────────────────────────
class TestIncidentFlow(unittest.TestCase):

    def setUp(self):
        # Build fresh async collection mocks for every test
        self._incidents   = _make_async_collection()
        self._llm_outputs = _make_async_collection()
        self._div_routes  = _make_async_collection()
        self._cong_zones  = _make_async_collection()
        self._intersect   = _make_async_collection()
        self._segments    = _make_async_collection()
        self._user_prof   = _make_async_collection()

        self.patchers = [
            patch("app.connect_db",  side_effect=_noop),
            patch("app.close_db",    side_effect=_noop),
            patch("services.operator_queue.OperatorQueueManager.reconcile_from_db",
                  side_effect=_noop),
            patch("core.task_queue.TaskQueue.start", side_effect=_noop),
            patch("core.task_queue.TaskQueue.stop",  side_effect=_noop),
            # DB collections — fully async so every 'await coll.method()' works
            patch("db.incidents",       self._incidents),
            patch("db.llm_outputs",     self._llm_outputs),
            patch("db.diversion_routes",self._div_routes),
            patch("db.congestion_zones",self._cong_zones),
            patch("db.intersections",   self._intersect),
            patch("db.road_segments",   self._segments),
            patch("db.user_profiles",   self._user_prof),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()

    # ── Test 1 ───────────────────────────────────────────────────────────────
    @patch("services.llm_service.LLMService.generate")
    @patch("services.routing_service.RoutingService.compute_incident_route_pair")
    def test_incident_injection_flow(self, mock_routing, mock_llm):
        """Injecting an incident must produce a 200 + trace-id + DB write."""
        mock_llm.return_value = {
            "narrative_update": "Test narrative",
            "signal_retiming": {"intersections": []},
            "diversions": {"routes": []},
            "alerts": {"vms": "Test VMS"},
        }
        mock_routing.return_value = {
            "version": "v2",
            "blocked":  {"geometry": {"type": "LineString", "coordinates": []}},
            "alternate": {"geometry": {"type": "LineString", "coordinates": []}},
            "meta": {"routing_engine": "mock"},
        }

        with TestClient(app) as client:
            response = client.post("/api/demo/inject-incident", json={
                "city": "nyc",
                "on_street": "W 34th St",
                "severity": "major",
                "lat": 40.7505,
                "lng": -73.9904,
            })

            # ── Sync assertions ──────────────────────────────────────────────
            self.assertEqual(response.status_code, 200,
                             f"Unexpected status: {response.text}")
            self.assertEqual(response.json().get("status"), "injected")
            self.assertIsNotNone(response.headers.get("X-Trace-Id"),
                                 "Missing X-Trace-Id header")

            # ── Async worker assertion ────────────────────────────────────────
            # Give the TaskQueue worker a moment to process the incident
            time.sleep(1.0)
            self._incidents.insert_one.assert_called()

    # ── Test 2 ───────────────────────────────────────────────────────────────
    def test_health_check(self):
        """App must boot and respond (not 5xx) even with all heavy deps mocked."""
        with TestClient(app) as client:
            r = client.get("/")
            self.assertNotIn(r.status_code, [500, 503],
                             f"App startup/request failed: {r.text}")


if __name__ == "__main__":
    unittest.main()
