import asyncio
import unittest

from services.routing_service import RoutingService


class RoutingV2Tests(unittest.TestCase):
    def test_incident_routes_have_blocked_and_alternate_geometry(self):
        svc = RoutingService()
        out = asyncio.run(
            svc.compute_incident_route_pair(
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

    def test_alternate_route_is_local(self):
        svc = RoutingService()
        out = asyncio.run(
            svc.compute_incident_route_pair(
                incident_lng=76.7788,
                incident_lat=30.7412,
                city="chandigarh",
                on_street="Madhya Marg",
                severity="moderate",
            )
        )
        self.assertIn("locality_score", out["alternate"])
        self.assertLessEqual(out["alternate"]["locality_score"], 100.0)


if __name__ == "__main__":
    unittest.main()
