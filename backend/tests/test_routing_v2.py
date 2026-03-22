import asyncio
import unittest

from services.routing_service import RoutingService


class RoutingV2Tests(unittest.TestCase):
    def setUp(self):
        self.svc = RoutingService(ors_api_key="")

    def test_incident_routes_have_blocked_and_alternate_geometry(self):
        out = asyncio.run(
            self.svc.compute_incident_route_pair(
                incident_lng=-73.9904,
                incident_lat=40.7505,
                city="nyc",
                on_street="W 34th St",
                severity="major",
            )
        )

        self.assertEqual(out.get("version"), "v2")
        self.assertGreaterEqual(len(out["blocked"]["geometry"]["coordinates"]), 2)
        self.assertGreaterEqual(len(out["alternate"]["geometry"]["coordinates"]), 2)
        self.assertIn("meta", out)
        self.assertIn("fallback_used", out["meta"])

    def test_anchor_builder_changes_with_orientation(self):
        origin_ns, dest_ns = self.svc._build_anchors(-73.99, 40.75, "7th Ave", "moderate")
        origin_ew, dest_ew = self.svc._build_anchors(-73.99, 40.75, "W 34th St", "moderate")
        self.assertAlmostEqual(origin_ns[0], dest_ns[0], places=5)
        self.assertAlmostEqual(origin_ew[1], dest_ew[1], places=5)

    def test_parse_ors_response_extracts_geometry_and_steps(self):
        sample = {
            "features": [
                {
                    "geometry": {"type": "LineString", "coordinates": [[-73.99, 40.75], [-73.98, 40.75]]},
                    "properties": {
                        "summary": {"distance": 1400, "duration": 240},
                        "segments": [{"steps": [{"name": "W 34th St"}, {"name": "7th Ave"}]}],
                    },
                }
            ]
        }
        parsed = self.svc._parse_ors_response(sample)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["geometry"]["type"], "LineString")
        self.assertGreaterEqual(len(parsed["street_names"]), 2)
        self.assertGreater(parsed["estimated_minutes"], 0)

    def test_locality_guard_rejects_far_route(self):
        far_coords = [[-73.99, 40.75], [-74.20, 40.95]]
        ok = self.svc._passes_locality_guard(
            coords=far_coords,
            incident_lng=-73.99,
            incident_lat=40.75,
            city="nyc",
            severity="moderate",
        )
        self.assertFalse(ok)

    def test_congestion_route_returns_blocked_and_alternate(self):
        out = asyncio.run(
            self.svc.compute_congestion_route_pair(
                congested_segments=[
                    {"link_name": "W 34th St", "lat": 40.7505, "lng": -73.9904, "speed": 3, "status": "BLOCKED"},
                    {"link_name": "W 34th St", "lat": 40.7510, "lng": -73.9920, "speed": 5, "status": "SLOW"},
                    {"link_name": "W 34th St", "lat": 40.7515, "lng": -73.9930, "speed": 6, "status": "SLOW"},
                ],
                city="nyc",
            )
        )
        self.assertGreaterEqual(len(out["blocked"]["geometry"]["coordinates"]), 2)
        self.assertGreaterEqual(len(out["alternate"]["geometry"]["coordinates"]), 2)


if __name__ == "__main__":
    unittest.main()
