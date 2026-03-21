import React, { useEffect, useRef } from 'react';
import { MapContainer, TileLayer, CircleMarker, Tooltip, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import { useFeedStore, useIncidentStore } from '../../store';
import { api } from '../../services/api';

import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

const DefaultIcon = L.icon({
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});
L.Marker.prototype.options.icon = DefaultIcon;

const NYC_CENTER: [number, number] = [30.7333, 76.7794]; // Updated to Chandigarh
const DEFAULT_ZOOM = 15;

const getSpeedColor = (speed: number): string => {
  if (speed < 5) return '#ef4444';  // red — blocked
  if (speed < 15) return '#eab308'; // yellow — slow
  return '#22c55e';                 // green — free flow
};

const isNearBlockedRoute = (lat: number, lng: number, blockedCoords: number[][]): boolean => {
  if (!blockedCoords || blockedCoords.length === 0) return false;
  const threshold = 0.003; // ~330m proximity
  for (const coord of blockedCoords) {
    if (Math.abs(lat - coord[1]) < threshold && Math.abs(lng - coord[0]) < threshold) {
      return true;
    }
  }
  return false;
};

const MapController: React.FC<{ center: [number, number]; zoom: number; city: string }> = ({ center, zoom, city }) => {
  const map = useMap();
  const prevCityRef = useRef<string>('');
  const mountedRef = useRef<boolean>(false);

  useEffect(() => {
    // Only call setView on initial mount OR when the city actually changes
    // Do NOT re-zoom on incident detection, feed updates, or segment changes
    if (!mountedRef.current || prevCityRef.current !== city) {
      map.setView(center, zoom);
      prevCityRef.current = city;
      mountedRef.current = true;
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [city]); // Intentionally only city in deps — center/zoom changes must NOT trigger setView
  return null;
};

const TrafficMap: React.FC = () => {
  const { segments, cityCenter, city } = useFeedStore();
  const { incidents, currentIncident, diversionRoutes, collisions, setCollisions, congestionZones, congestionRoutes, incidentRoutes } = useIncidentStore();
  // AND gate: collect ALL blocked route coordinates from ALL incidents
  const allBlockedCoords: number[][] = incidentRoutes.flatMap(
    (r) => r.blocked?.geometry?.coordinates || []
  );

  useEffect(() => {
    if (currentIncident) {
      api.getNearbyCollisions(currentIncident.location.lat, currentIncident.location.lng, 0.01)
        .then(data => {
          if (Array.isArray(data)) setCollisions(data);
        })
        .catch(() => {});
    }
  }, [currentIncident?.id]);

  const mapCenter: [number, number] = cityCenter
    ? [cityCenter.lat, cityCenter.lng]
    : NYC_CENTER;
  const mapZoom = cityCenter?.zoom ?? DEFAULT_ZOOM;

  return (
    <div className="w-full h-full relative">
      <MapContainer
        center={mapCenter}
        zoom={mapZoom}
        className="w-full h-full"
        zoomControl={false}
      >
        <MapController center={mapCenter} zoom={mapZoom} city={city} />

        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png"
          attribution='&copy; CARTO'
        />

        {/* Traffic Speed Segments */}
        {segments.map((seg) => {
          const isBlocked = allBlockedCoords.length > 0 && isNearBlockedRoute(seg.lat, seg.lng, allBlockedCoords);
          const color = isBlocked ? '#ef4444' : getSpeedColor(seg.speed);
          const radius = isBlocked ? 9 : (seg.speed < 5 ? 8 : 6);
          return (
            <CircleMarker
              key={seg.link_id}
              center={[seg.lat, seg.lng]}
              radius={radius}
              pathOptions={{
                color,
                fillColor: color,
                fillOpacity: 0.85,
                weight: isBlocked ? 2 : 1,
              }}
            >
              <Tooltip direction="top" offset={[0, -6]} opacity={0.9}>
                <span className="text-[10px] font-mono">
                  {isBlocked ? '🔴 ' : ''}{seg.link_name} — {seg.speed.toFixed(0)} mph{isBlocked ? ' [BLOCKED]' : ''}
                </span>
              </Tooltip>
            </CircleMarker>
          );
        })}

        {/* Incident Markers — ALL active incidents with pulsing effect */}
        {incidents.filter((inc) => inc.status === 'active').map((inc) => (
          <React.Fragment key={`incident-${inc.id}`}>
            <CircleMarker
              center={[inc.location.lat, inc.location.lng]}
              radius={14}
              pathOptions={{
                color: '#ef4444',
                fillColor: '#ef4444',
                fillOpacity: 0.2,
                weight: 1,
                className: 'animate-pulse',
              }}
            />
            <CircleMarker
              center={[inc.location.lat, inc.location.lng]}
              radius={6}
              pathOptions={{
                color: '#ef4444',
                fillColor: '#ef4444',
                fillOpacity: 1,
                weight: 2,
              }}
            >
              <Tooltip direction="top" offset={[0, -8]} opacity={0.95} permanent>
                <span className="text-[10px] font-mono font-bold">
                  INCIDENT: {inc.on_street}
                </span>
              </Tooltip>
            </CircleMarker>
          </React.Fragment>
        ))}

        {/* ═══ INCIDENT ROUTES — ALL active incident route pairs ═══ */}
        {incidentRoutes.map((routePair) => (
          <React.Fragment key={`routes-${routePair.incidentId}`}>
            {/* Blocked Road (RED) */}
            {routePair.blocked?.geometry?.coordinates && routePair.blocked.geometry.coordinates.length >= 2 && (
              <Polyline
                positions={routePair.blocked.geometry.coordinates.map((c: number[]) => [c[1], c[0]] as [number, number])}
                pathOptions={{ color: '#ef4444', weight: 7, opacity: 0.85 }}
              >
                <Tooltip sticky>
                  <span className="text-[10px] font-mono font-bold">
                    🔴 BLOCKED: {(routePair.blocked.street_names || []).slice(0, 2).join(' → ') || 'Incident Road'}
                    {routePair.blocked.total_length_km ? ` — ${routePair.blocked.total_length_km} km` : ''}
                  </span>
                </Tooltip>
              </Polyline>
            )}

            {/* Alternate Route (GREEN) */}
            {routePair.alternate?.geometry?.coordinates && routePair.alternate.geometry.coordinates.length >= 2 && (
              <Polyline
                positions={routePair.alternate.geometry.coordinates.map((c: number[]) => [c[1], c[0]] as [number, number])}
                pathOptions={{ color: '#22c55e', weight: 6, opacity: 0.9 }}
              >
                <Tooltip sticky>
                  <span className="text-[10px] font-mono font-bold">
                    🟢 ALTERNATE: {(routePair.alternate.street_names || []).slice(0, 2).join(' → ') || 'Detour Route'}
                    {routePair.alternate.total_length_km ? ` — ${routePair.alternate.total_length_km} km` : ''}
                    {routePair.alternate.estimated_extra_minutes ? ` (+${routePair.alternate.estimated_extra_minutes} min)` : ''}
                  </span>
                </Tooltip>
              </Polyline>
            )}

            {/* Origin marker — DIVERT HERE */}
            {routePair.origin && (
              <CircleMarker
                center={[routePair.origin[1], routePair.origin[0]]}
                radius={8}
                pathOptions={{ color: '#22c55e', fillColor: '#22c55e', fillOpacity: 1, weight: 2 }}
              >
                <Tooltip direction="top" offset={[0, -8]} permanent>
                  <span className="text-[9px] font-mono font-bold">↗ DIVERT HERE</span>
                </Tooltip>
              </CircleMarker>
            )}

            {/* Destination marker — REJOIN */}
            {routePair.destination && (
              <CircleMarker
                center={[routePair.destination[1], routePair.destination[0]]}
                radius={8}
                pathOptions={{ color: '#22c55e', fillColor: '#22c55e', fillOpacity: 1, weight: 2 }}
              >
                <Tooltip direction="top" offset={[0, -8]} permanent>
                  <span className="text-[9px] font-mono font-bold">✓ REJOIN</span>
                </Tooltip>
              </CircleMarker>
            )}
          </React.Fragment>
        ))}

        {/* Collision markers */}
        {collisions.map((c: any, idx: number) => {
          if (!c.latitude || !c.longitude) return null;
          return (
            <CircleMarker
              key={`collision-${idx}`}
              center={[parseFloat(c.latitude), parseFloat(c.longitude)]}
              radius={4}
              pathOptions={{
                color: '#f97316',
                fillColor: '#f97316',
                fillOpacity: 0.7,
                weight: 1,
              }}
            >
              <Tooltip direction="top" offset={[0, -4]}>
                <span className="text-[10px] font-mono">
                  Crash: {c.on_street_name || 'Unknown'} ({c.number_of_persons_injured || 0} injured)
                </span>
              </Tooltip>
            </CircleMarker>
          );
        })}

        {/* Congestion Zone Markers — amber pulsing */}
        {congestionZones.map((zone: any) => {
          const lat = zone.location?.coordinates?.[1];
          const lng = zone.location?.coordinates?.[0];
          if (!lat || !lng) return null;
          return (
            <React.Fragment key={`congestion-zone-${zone.zone_id}`}>
              <CircleMarker
                center={[lat, lng]}
                radius={16}
                pathOptions={{
                  color: zone.severity === 'severe' ? '#ef4444' : '#f59e0b',
                  fillColor: zone.severity === 'severe' ? '#ef4444' : '#f59e0b',
                  fillOpacity: 0.15,
                  weight: 2,
                  className: 'animate-pulse',
                }}
              />
              <CircleMarker
                center={[lat, lng]}
                radius={7}
                pathOptions={{
                  color: zone.severity === 'severe' ? '#ef4444' : '#f59e0b',
                  fillColor: zone.severity === 'severe' ? '#ef4444' : '#f59e0b',
                  fillOpacity: 0.9,
                  weight: 2,
                }}
              >
                <Tooltip direction="top" offset={[0, -8]} opacity={0.95} permanent>
                  <span className="text-[9px] font-mono font-bold">
                    🚧 CONGESTION: {zone.primary_street}
                  </span>
                </Tooltip>
              </CircleMarker>
            </React.Fragment>
          );
        })}

        {/* Congestion Blocked Roads (YELLOW) */}
        {congestionZones.map((zone: any) => {
          const coords = zone.blocked_geometry?.coordinates;
          if (!coords || coords.length < 2) return null;
          return (
            <Polyline
              key={`cong-blocked-${zone.zone_id}`}
              positions={coords.map((c: number[]) => [c[1], c[0]] as [number, number])}
              pathOptions={{ color: '#f59e0b', weight: 6, opacity: 0.85 }}
            >
              <Tooltip sticky>
                <span className="text-[10px] font-mono font-bold">
                  🚧 CONGESTED: {zone.primary_street}
                </span>
              </Tooltip>
            </Polyline>
          );
        })}

        {/* Congestion Alternate Route Polylines — amber/orange */}
        {congestionRoutes.map((route: any, idx: number) => {
          const coords = route.geometry?.coordinates;
          if (!coords || !Array.isArray(coords) || coords.length < 2) return null;
          const positions = coords.map((c: number[]) => [c[1], c[0]] as [number, number]);
          return (
            <Polyline
              key={`congestion-route-${idx}`}
              positions={positions}
              pathOptions={{
                color: '#f59e0b',
                weight: 5,
                opacity: 0.85,
                dashArray: '10 6',
              }}
            >
              <Tooltip sticky>
                <span className="text-[10px] font-mono font-bold">
                  🚧 ALT ROUTE: {route.name || `Route ${idx + 1}`}
                  {route.total_length_km ? ` — ${route.total_length_km} km` : ''}
                </span>
              </Tooltip>
            </Polyline>
          );
        })}

      </MapContainer>
    </div>
  );
};

export default TrafficMap;
