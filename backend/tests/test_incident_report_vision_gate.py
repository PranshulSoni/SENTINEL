import asyncio
import unittest
from types import SimpleNamespace

from routers.incidents import IncidentReport, report_incident


class _FakeAnalysis:
    def __init__(self, payload: dict):
        self._payload = payload

    def to_dict(self):
        return dict(self._payload)


class _FakeVisionService:
    def __init__(self, payload: dict):
        self.payload = payload
        self.called = False

    async def analyze_image(self, _media_url: str):
        self.called = True
        return _FakeAnalysis(self.payload)


class IncidentReportVisionGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_report_returns_not_detected_when_model_false(self):
        called = False

        async def _on_incident(_incident: dict):
            nonlocal called
            called = True

        vision = _FakeVisionService(
            {
                "roadblock_detected": False,
                "obstruction_score": 12,
                "confidence_score": 10,
                "explanation": "No roadblock found",
                "severity": "minor",
            }
        )
        request = SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(
                    roadblock_vision_service=vision,
                    on_incident=_on_incident,
                )
            )
        )

        res = await report_incident(
            IncidentReport(
                title="Collision",
                city="nyc",
                location_str="W 34th St",
                description="test",
                media_url="data:image/jpeg;base64,abcd",
            ),
            request,
        )

        self.assertEqual(res.get("status"), "not_detected")
        self.assertTrue(vision.called)
        await asyncio.sleep(0)
        self.assertFalse(called)

    async def test_report_creates_incident_when_model_true(self):
        event = asyncio.Event()

        async def _on_incident(_incident: dict):
            event.set()

        vision = _FakeVisionService(
            {
                "roadblock_detected": True,
                "obstruction_score": 76,
                "confidence_score": 82,
                "explanation": "Crash blocking lanes",
                "severity": "critical",
                "severity_score": 76,
            }
        )
        request = SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(
                    roadblock_vision_service=vision,
                    on_incident=_on_incident,
                )
            )
        )

        res = await report_incident(
            IncidentReport(
                title="Collision",
                city="nyc",
                location_str="W 34th St",
                description="test",
                media_url="data:image/jpeg;base64,abcd",
            ),
            request,
        )

        self.assertEqual(res.get("status"), "reported")
        self.assertIsNotNone(res.get("incident_id"))
        self.assertTrue(vision.called)
        await asyncio.wait_for(event.wait(), timeout=1.0)


if __name__ == "__main__":
    unittest.main()
