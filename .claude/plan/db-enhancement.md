# Implementation Plan: Database Enhancement for Accuracy & Routing

## Problem
The database has minimal fields — incidents store basic location/severity, congestion zones have just polygon/severity, and there's no structured road/intersection data. This limits routing accuracy, LLM prompt quality, and operator decision-making.

## Solution: Enrich all collections + add new seed data

### Task Type
- [x] Backend

### Implementation Steps

1. **Enhance default_congestion_zones.py** — Add peak_hours, recurring_pattern, avg_speed, vehicle_volume, root_cause, transit_impact, truck_restriction to all 8 zones
2. **Enhance signal_baselines.py** — Add pedestrian_phase, left_turn_phase, camera_monitored, avg_daily_vehicles, accident_prone, school/hospital_nearby
3. **Create intersections.py** — 10 NYC + 10 Chandigarh intersections with lanes, speed_limit, direction, connects_to, congestion_delay, incident_frequency
4. **Create road_segments.py** — 10-15 segments per city with length, lanes, speed_limit, road_class, peak/offpeak speeds, bus_routes, accident_history
5. **Register new collections in db.py** — intersections, road_segments with indexes
6. **Seed on startup in app.py** — Insert defaults if empty

### Key Files
| File | Operation | Description |
|------|-----------|-------------|
| backend/data/default_congestion_zones.py | Modify | Add 8 new fields per zone |
| backend/data/signal_baselines.py | Modify | Add 8 new fields per baseline |
| backend/data/intersections.py | Create | 20 intersections (10/city) |
| backend/data/road_segments.py | Create | 25 road segments (12-13/city) |
| backend/db.py | Modify | Register 2 new collections + indexes |
| backend/app.py | Modify | Seed new collections on startup |

### Also Fixed (from previous multi-backend task)
- LLM service reverted to SDK calls (was broken from httpx conversion)
- Incident-triggered congestion zones (severity-based radius)
- Congestion zone cleanup on resolve/dismiss
- Segment speed penalty near active incidents
