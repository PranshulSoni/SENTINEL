# Implementation Plan: Fix Green/Red Route Overlap in Multi-Incident Scenarios

## Problem Statement
When multiple incidents are active simultaneously, green alternate routes overlap with red blocked/congested routes from OTHER incidents. Example: Incident 1 blocks 7th Ave and reroutes to Broadway. Incident 2 blocks Broadway and reroutes to 7th Ave — creating a visual AND logical conflict where the "safe" green alternate passes through a blocked red zone.

**Root Cause**: `compute_incident_route_pair()` only avoids the CURRENT incident's location (170m box). It has ZERO knowledge of other active incidents' blocked zones or congestion areas.

## Technical Solution

### Architecture Change
Transform from **per-incident isolated routing** to **multi-incident-aware routing**:

1. Before computing routes for a new incident, query ALL active incidents from DB
2. Build avoidance polygons from ALL active incidents' locations + congestion zones
3. Pass combined avoidance to ORS so alternates never cross other blocked areas
4. After computing a new incident's routes, recompute existing incidents' routes with the updated avoidance set
5. Frontend: build `allBlockedCoords` from ALL incidents (not just focused)

### Task Type
- [x] Backend (routing service + app.py)
- [x] Frontend (TrafficMap conflict detection)

---

## Implementation Steps

### Step 1: Modify `compute_incident_route_pair()` to accept other incidents' avoidance zones

**File**: `backend/services/routing_service.py`

**Change**: Add `extra_avoid_polygons` parameter:

```python
async def compute_incident_route_pair(
    self,
    incident_lng: float,
    incident_lat: float,
    city: str = "nyc",
    on_street: str = "",
    extra_avoid_polygons: list | None = None,  # NEW: polygons from other incidents
) -> dict:
```

Where `congestion_polys` is built (currently empty list on ~line 217), merge in extra_avoid_polygons:

```python
congestion_polys = extra_avoid_polygons or []
# ... existing code continues ...
all_avoid_polys = [incident_corridor] + congestion_polys
```

This is the minimal surgical change — the rest of the routing logic (ORS call, alternative_routes, picker) all already work with `all_avoid_polys`.

---

### Step 2: Modify `_on_incident()` to collect other incidents' avoidance zones

**File**: `backend/app.py`

**Change**: Before calling `compute_incident_route_pair()`, query DB for all OTHER active incidents and build avoidance polygons from their locations:

```python
# In _on_incident(), before the routing call:

# Collect avoidance zones from ALL other active incidents
extra_avoid = []
if db.incidents is not None:
    other_incidents = await db.incidents.find(
        {"status": "active", "_id": {"$ne": ObjectId(incident_id)}}
    ).to_list(50)
    for other in other_incidents:
        olat = other.get("latitude", 0)
        olng = other.get("longitude", 0)
        if olat and olng:
            # Build avoidance box around each other incident (same size as own corridor)
            buf = 0.002  # ~220m buffer
            extra_avoid.append([
                [olng - buf, olat - buf],
                [olng + buf, olat - buf],
                [olng + buf, olat + buf],
                [olng - buf, olat + buf],
                [olng - buf, olat - buf],
            ])

# Also include congestion zones from DB
if db.congestion_zones is not None:
    active_zones = await db.congestion_zones.find(
        {"city": city, "status": {"$in": ["active", "permanent"]}}
    ).to_list(50)
    for zone in active_zones:
        poly = zone.get("polygon")
        if poly and len(poly) >= 4:
            extra_avoid.append(poly if poly[0] == poly[-1] else poly + [poly[0]])

# Pass to routing
route_task = routing_service.compute_incident_route_pair(
    lng, lat, city=city, on_street=incident.get("on_street", ""),
    extra_avoid_polygons=extra_avoid,  # NEW
)
```

---

### Step 3: Recompute existing incidents' routes when a new incident arrives

**File**: `backend/app.py`

**Change**: After the new incident's routes are computed and broadcast, trigger a background recomputation of ALL other active incidents' routes:

```python
# After broadcasting the new incident's routes, recompute others
async def _recompute_other_routes(current_incident_id: str, city: str):
    """Recompute routes for all other active incidents with updated avoidance."""
    if db.incidents is None:
        return
    
    all_active = await db.incidents.find(
        {"status": "active", "city": city}
    ).to_list(50)
    
    for inc in all_active:
        inc_id = str(inc["_id"])
        if inc_id == current_incident_id:
            continue
        
        # Build avoidance from ALL OTHER active incidents (including the new one)
        extra_avoid = []
        for other in all_active:
            other_id = str(other["_id"])
            if other_id == inc_id:
                continue
            olat = other.get("latitude", 0)
            olng = other.get("longitude", 0)
            if olat and olng:
                buf = 0.002
                extra_avoid.append([
                    [olng - buf, olat - buf],
                    [olng + buf, olat - buf],
                    [olng + buf, olat + buf],
                    [olng - buf, olat + buf],
                    [olng - buf, olat - buf],
                ])
        
        # Recompute
        new_routes = await routing_service.compute_incident_route_pair(
            inc.get("longitude", 0), inc.get("latitude", 0),
            city=city, on_street=inc.get("on_street", ""),
            extra_avoid_polygons=extra_avoid,
        )
        
        if new_routes and new_routes.get("alternate"):
            # Update DB
            if db.diversion_routes is not None:
                await db.diversion_routes.update_one(
                    {"incident_id": inc_id},
                    {"$set": {
                        "blocked_route": new_routes["blocked"],
                        "alternate_route": new_routes["alternate"],
                        "origin": new_routes["origin"],
                        "destination": new_routes["destination"],
                        "recomputed_at": datetime.now(timezone.utc).isoformat(),
                    }},
                    upsert=True,
                )
            # Broadcast updated routes
            await ws_manager.broadcast({
                "type": "incident_routes",
                "data": {
                    "incident_id": inc_id,
                    "origin": new_routes["origin"],
                    "destination": new_routes["destination"],
                    "blocked": new_routes["blocked"],
                    "alternate": new_routes["alternate"],
                },
            })

# Fire-and-forget after the main pipeline
asyncio.create_task(_recompute_other_routes(incident_id, city))
```

---

### Step 4: Frontend — Build allBlockedCoords from ALL incidents

**File**: `frontend/src/components/map/TrafficMap.tsx`

**Change**: `allBlockedCoords` currently only includes blocked coords from `focusedRoutes` (current incident). Change to include ALL incident routes' blocked coords:

```typescript
// BEFORE (only focused incident):
const focusedRoutes = currentIncident
  ? incidentRoutes.filter(r => r.incidentId === currentIncident.id)
  : incidentRoutes;
const allBlockedCoords: number[][] = focusedRoutes.flatMap(
  (r) => r.blocked?.geometry?.coordinates || []
);

// AFTER (ALL incidents):
const allBlockedCoords: number[][] = incidentRoutes.flatMap(
  (r) => r.blocked?.geometry?.coordinates || []
);
```

This ensures `isNearBlockedRoute()` checks proximity to ALL blocked routes (not just the focused one), so segment coloring accurately reflects all congestion.

---

### Step 5: Frontend — Visual conflict indicator for overlapping alternates

**File**: `frontend/src/components/map/TrafficMap.tsx`

**Change**: When rendering alternate routes, check if any segment of the alternate overlaps with ANY blocked route. If so, render that segment as amber/warning instead of green:

```typescript
// For each alternate route polyline, check overlap with blocked routes from OTHER incidents
const otherBlockedCoords = incidentRoutes
  .filter(r => r.incidentId !== routePair.incidentId)
  .flatMap(r => r.blocked?.geometry?.coordinates || []);

const hasOverlap = altCoords.some((c: number[]) =>
  otherBlockedCoords.some((bc: number[]) =>
    Math.abs(c[0] - bc[0]) < 0.001 && Math.abs(c[1] - bc[1]) < 0.001
  )
);
```

If overlap detected, the alternate route was computed before knowing about the other incident — the recomputation (Step 3) will fix it, but in the interim show a warning color.

---

## Key Files

| File | Operation | Description |
|------|-----------|-------------|
| `backend/services/routing_service.py` | Modify | Add `extra_avoid_polygons` param to `compute_incident_route_pair()` |
| `backend/app.py` | Modify | Collect other incidents' avoidance zones, pass to routing, trigger recomputation |
| `frontend/src/components/map/TrafficMap.tsx` | Modify | Build `allBlockedCoords` from ALL incidents, add overlap detection |

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| ORS reject too many avoid polygons | Merge nearby polygons into one; limit to 10 polygons max |
| Recomputation cascade (incident A recomputes B, B recomputes A) | Only recompute once per new incident; use `recomputed_at` flag to skip recent |
| ORS latency with large MultiPolygon | Keep buffer at 0.002° (small); parallel recomputation with asyncio.create_task |
| Route may have no valid alternate when many areas blocked | Fallback: if ORS returns no route, keep existing alternate and show warning tooltip |

## SESSION_ID (for /ccg:execute use)
- CODEX_SESSION: N/A (codeagent-wrapper not available)
- GEMINI_SESSION: N/A (codeagent-wrapper not available)
