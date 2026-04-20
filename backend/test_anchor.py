#!/usr/bin/env python3
"""
Test script to verify corridor-based anchor building works correctly.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from services.routing_service import RoutingService

def test_corridor_anchors():
    """Test that corridor-based anchors are built correctly."""
    print("Testing corridor-based anchor building...")
    
    svc = RoutingService(ors_api_key="")
    
    # Test case 1: NYC incident on W 34th St (should work with corridor method)
    print("\n1. Testing NYC W 34th St incident...")
    origin, destination = svc._build_anchors(
        incident_lng=-73.9904,
        incident_lat=40.7505,
        on_street="W 34th St",
        severity="moderate",
        city="nyc",
        feed_segments=[]
    )
    
    print(f"   Origin: {origin}")
    print(f"   Destination: {destination}")
    
    # Basic validation
    assert len(origin) == 2, f"Origin should have 2 coordinates, got {origin}"
    assert len(destination) == 2, f"Destination should have 2 coordinates, got {destination}"
    assert origin != destination, f"Origin and destination should be different, got {origin} and {destination}"
    
    # Test case 2: Chandigarh incident on Madhya Marg (should work with corridor method)
    print("\n2. Testing Chandigarh Madhya Marg incident...")
    origin, destination = svc._build_anchors(
        incident_lng=76.7788,
        incident_lat=30.7412,
        on_street="Madhya Marg",
        severity="moderate",
        city="chandigarh",
        feed_segments=[]
    )
    
    print(f"   Origin: {origin}")
    print(f"   Destination: {destination}")
    
    # Basic validation
    assert len(origin) == 2, f"Origin should have 2 coordinates, got {origin}"
    assert len(destination) == 2, f"Destination should have 2 coordinates, got {destination}"
    assert origin != destination, f"Origin and destination should be different, got {origin} and {destination}"
    
    # Verify that the points are roughly along the expected direction
    # Madhya Marg is primarily north-south, so latitude should differ more than longitude
    lat_diff = abs(destination[1] - origin[1])
    lng_diff = abs(destination[0] - origin[0])
    print(f"   Lat diff: {lat_diff:.6f}, Lng diff: {lng_diff:.6f}")
    
    # For Madhya Marg (NS street), we expect lat_diff > lng_diff
    # Since it's a perfect NS street in the data, lng_diff should be 0
    assert lng_diff == 0, f"For NS street Madhya Marg, longitude diff should be 0, got {lng_diff}"
    assert lat_diff > 0, f"For NS street Madhya Marg, latitude diff should be > 0, got {lat_diff}"
    
    # Test case 3: Invalid street (should fall back to original method)
    print("\n3. Testing invalid street (should fall back)...")
    origin, destination = svc._build_anchors(
        incident_lng=-73.9904,
        incident_lat=40.7505,
        on_street="Nonexistent Street Xyz",
        severity="moderate",
        city="nyc",
        feed_segments=[]
    )
    
    print(f"   Origin: {origin}")
    print(f"   Destination: {destination}")
    
    # Should still return valid coordinates (fallback method)
    assert len(origin) == 2, f"Origin should have 2 coordinates, got {origin}"
    assert len(destination) == 2, f"Destination should have 2 coordinates, got {destination}"
    assert origin != destination, f"Origin and destination should be different, got {origin} and {destination}"
    
    print("\n✅ All tests passed! Corridor-based anchor building is working correctly.")

if __name__ == "__main__":
    test_corridor_anchors()