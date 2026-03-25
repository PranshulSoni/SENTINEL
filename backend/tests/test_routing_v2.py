import asyncio
import time
import unittest

import services.routing_service as routing_service_module
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
        self.assertIn("estimated_actual_minutes", out["alternate"])
        self.assertIn("estimated_actual_extra_minutes", out["alternate"])
        alt_len = len(out["alternate"]["geometry"]["coordinates"])
        if alt_len < 2:
            self.assertEqual(out["meta"].get("routing_engine"), "degraded")
        else:
            self.assertGreaterEqual(alt_len, 2)
            self.assertGreaterEqual(
                float(out["alternate"]["estimated_actual_minutes"]),
                float(out["alternate"]["estimated_minutes"]),
            )
        self.assertIn("meta", out)
        self.assertIn("fallback_used", out["meta"])

    def test_anchor_builder_changes_with_orientation(self):
        origin_ns, dest_ns = self.svc._build_anchors(-73.99, 40.75, "7th Ave", "moderate", "nyc", [])
        origin_ew, dest_ew = self.svc._build_anchors(-73.99, 40.75, "W 34th St", "moderate", "nyc", [])
        ns_dx = abs(dest_ns[0] - origin_ns[0])
        ns_dy = abs(dest_ns[1] - origin_ns[1])
        ew_dx = abs(dest_ew[0] - origin_ew[0])
        ew_dy = abs(dest_ew[1] - origin_ew[1])
        self.assertGreater(ns_dy, ns_dx)
        self.assertGreater(ew_dx, ew_dy)

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

    def test_detour_guard_rejects_excessive_alternate(self):
        self.assertTrue(self.svc._passes_detour_guard(alt_km=1.2, blocked_km=1.0, city="nyc", severity="moderate"))
        self.assertFalse(self.svc._passes_detour_guard(alt_km=1.9, blocked_km=1.0, city="nyc", severity="moderate"))

    def test_candidate_vias_stay_outside_incident_avoid_polygon(self):
        incident_lng = 76.7788
        incident_lat = 30.7412
        severity = "major"
        vias = self.svc._build_candidate_vias(
            incident_lng=incident_lng,
            incident_lat=incident_lat,
            on_street="Madhya Marg",
            severity=severity,
            city="chandigarh",
            feed_segments=[],
        )
        incident_poly = self.svc._incident_avoid_polygon(
            incident_lng=incident_lng,
            incident_lat=incident_lat,
            severity=severity,
        )
        for via in vias:
            self.assertFalse(self.svc._point_in_polygon((via[0], via[1]), incident_poly))

    def test_fallback_alternate_does_not_emit_synthetic_line(self):
        route, score = self.svc._fallback_alternate_route(
            graph={"nodes": {}, "edges": {}},
            origin=[76.7788, 30.7357],
            destination=[76.7788, 30.7466],
            incident=(76.7788, 30.7412),
            severity="major",
            on_street="Madhya Marg",
            avoid_polygons=[],
            feed_segments=[],
            expected_minutes=8.0,
            city="chandigarh",
            blocked_km=1.0,
        )
        self.assertEqual(route["geometry"]["coordinates"], [])
        self.assertGreaterEqual(score, 9999.0)

    def test_fallback_blocked_does_not_emit_synthetic_line(self):
        route, source = self.svc._fallback_blocked_route(
            graph={"nodes": {}, "edges": {}},
            origin=[76.7788, 30.7357],
            destination=[76.7788, 30.7466],
            incident=(76.7788, 30.7412),
            on_street="Unknown Street",
            city="unknown_city",
            feed_segments=[],
            severity="major",
        )
        self.assertEqual(source, "unavailable")
        self.assertEqual(route["geometry"]["coordinates"], [])

    def test_geometry_quality_rejects_tiny_line(self):
        tiny = [[-73.99, 40.75], [-73.989999, 40.750001]]
        self.assertFalse(self.svc._passes_geometry_quality(tiny))

    def test_select_incident_waypoint_prefers_street_matched_feed_point(self):
        waypoint = self.svc._select_incident_waypoint(
            incident_lng=76.7788,
            incident_lat=30.7412,
            city="chandigarh",
            on_street="Madhya Marg",
            feed_segments=[
                {"link_name": "Madhya Marg", "lng": 76.7782, "lat": 30.7413},
                {"link_name": "Jan Marg", "lng": 76.7710, "lat": 30.7380},
            ],
        )
        self.assertAlmostEqual(waypoint[0], 76.7782, places=4)
        self.assertAlmostEqual(waypoint[1], 30.7413, places=4)

    def test_blocked_guard_rejects_city_spanning_path(self):
        coords = [
            [-74.0100, 40.7200],
            [-74.0300, 40.7600],
            [-73.9800, 40.7900],
        ]
        ok = self.svc._passes_blocked_guard(
            coords=coords,
            origin=[-73.9904, 40.7505],
            destination=[-73.9912, 40.7572],
            incident_lng=-73.9904,
            incident_lat=40.7505,
            city="nyc",
            severity="major",
        )
        self.assertFalse(ok)

    def test_metadata_marks_transport_unavailable_when_httpx_missing(self):
        original_httpx = routing_service_module.httpx
        routing_service_module.httpx = None
        try:
            svc = RoutingService(ors_api_key="fake-ors-key")
            out = asyncio.run(
                svc.compute_incident_route_pair(
                    incident_lng=-73.9904,
                    incident_lat=40.7505,
                    city="nyc",
                    on_street="W 34th St",
                    severity="major",
                )
            )
        finally:
            routing_service_module.httpx = original_httpx
        self.assertIn("meta", out)
        self.assertTrue(out["meta"].get("fallback_used"))
        self.assertEqual(out["meta"].get("ors_requests"), 0)
        self.assertEqual(out["meta"].get("ors_success"), 0)
        self.assertEqual(out["meta"].get("degradation_reason"), "ors_transport_unavailable")
        self.assertEqual(out["meta"].get("route_quality"), "unavailable")
        self.assertEqual(out["meta"].get("alternate_source"), "unavailable")

    def test_ors_rate_limit_cooldown_marker_sets_future_timestamp(self):
        svc = RoutingService(ors_api_key="fake")
        before = time.time()
        svc._mark_ors_rate_limited("10")
        self.assertGreaterEqual(svc._ors_rate_limited_until, before + 9.5)

    def test_ors_retry_backoff_increases_per_attempt(self):
        svc = RoutingService(ors_api_key="fake")
        d0 = svc._ors_retry_backoff_delay(0)
        d1 = svc._ors_retry_backoff_delay(1)
        d2 = svc._ors_retry_backoff_delay(2)
        self.assertGreaterEqual(d1, d0)
        self.assertGreaterEqual(d2, d1)

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
        alt_len = len(out["alternate"]["geometry"]["coordinates"])
        if alt_len < 2:
            self.assertEqual(out["meta"].get("routing_engine"), "degraded")
        else:
            self.assertGreaterEqual(alt_len, 2)

    def test_degraded_metadata_when_no_local_alternate_exists(self):
        out = asyncio.run(
            self.svc.compute_incident_route_pair(
                incident_lng=76.7788,
                incident_lat=30.7412,
                city="unknown_city",
                on_street="Madhya Marg",
                severity="major",
            )
        )
        self.assertEqual(out["meta"]["routing_engine"], "degraded")
        self.assertEqual(out["alternate"]["geometry"]["coordinates"], [])


if __name__ == "__main__":
    unittest.main()
