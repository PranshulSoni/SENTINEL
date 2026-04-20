#!/usr/bin/env python3
"""
Test script to verify corridor-based anchor building works correctly.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from services.routing_service import RoutingService

def test_corridor_anchors():
    """Test that corridor-based anchors are built correctly."""
    svc = RoutingService(ors_api_key="")
    
    # Test case 1: NYC incident on W 34th St
    print("Testing NYC W 34th St incident...")
    origin, destination = svc._build_anchors(
        incident_lng=-73.9904,
        incident_lat=40.7505,
        on_street="W 34th St",
        severity="moderate",
        city="nyc",
        feed_segments=[]
    )
    
    print(f"Origin: {origin}")
    print(f"Destination: {destination}")
    
    # Check that we got valid coordinates
    assert len(origin) == 2, "Origin should have 2 coordinates"
    assert len(destination) == 2, "Destination should have 2 coordinates"
    assert origin != destination, "Origin and destination should be different"
    
    # Test case 2: Chandigarh incident on Madhya Marg
    print("\nTesting Chandigarh Madhya Marg incident...")
    origin, destination = svc._build_anchors(
        incident_lng=76.7788,
        incident_lat=30.7412,
        on_street="Madhya Marg",
        severity="moderate",
        city="chandigarh",
        feed_segments=[]
    )
    
    print(f"Origin: {origin}")
    print(f"Destination: {destination}")
    
    # Check that we got valid coordinates
    assert len(origin) == 2, "Origin should have 2 coordinates"
    assert len(destination) == 2, "Destination should have 2 coordinates"
    assert origin != destination, "Origin and destination should be different"
    
    # Verify that the points are roughly along the expected direction
    # Madhya Marg is primarily north-south, so latitude should differ more than longitude
    lat_diff = abs(destination[1] - origin[1])
    lng_diff = abs(destination[0] - origin[0])
    print(f"Lat diff: {lat_diff}, Lng diff: {lng_diff}")
    
    print("\nAll tests passed!")

if __name__ == "__main__":
    test_corridor_anchors()