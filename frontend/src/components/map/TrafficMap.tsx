import React, { useEffect, useRef } from 'react';
import { MapContainer, TileLayer, CircleMarker, Tooltip, Polyline, Polygon, useMap } from 'react-leaflet';
import L from 'leaflet';
import { useFeedStore, useIncidentStore } from '../../store';
import { CameraPopup } from './CameraPopup';
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

const NYC_CENTER: [number, number] = [40.7128, -74.0060]; // NYC fallback center
const DEFAULT_ZOOM = 15;



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
  const { cityCenter, city } = useFeedStore();
  const { incidents, currentIncident, setCollisions, incidentRoutes, congestionZones } = useIncidentStore();

  const BIG_INTERSECTIONS = [
    { id: '1', name: "W 34th St & 7th Ave", lat: 40.7505, lng: -73.9904 },
    { id: '2', name: "Broadway & 34th St", lat: 40.7484, lng: -73.9878 },
    { id: '3', name: "10th Ave & 42nd St", lat: 40.7579, lng: -73.9980 },
    { id: '4', name: "Tribune Chowk", lat: 30.7270, lng: 76.7675 },
    { id: '5', name: "Piccadily Chowk", lat: 30.7246, lng: 76.7621 }
  ];



  // Debug: log incidentRoutes state changes
  useEffect(() => {
    console.log('[TrafficMap] incidentRoutes updated:', incidentRoutes.length, 'pairs',
      incidentRoutes.map(r => ({
        id: r.incidentId,
        blockedPts: r.blocked?.geometry?.coordinates?.length || 0,
        altPts: r.alternate?.geometry?.coordinates?.length || 0,
      }))
    );
  }, [incidentRoutes]);

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
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; CARTO'
        />

        {/* Traffic Speed Segments — DISABLED: too noisy, only show actual incident markers */}
        {/* Segment heat-map can be re-enabled here if needed for analytics view */}



        {/* Incident Markers — ALL active incidents with pulsing effect */}
        {incidents.filter((inc) => inc.status === 'active' && inc.city === city).map((inc) => (
          <React.Fragment key={`incident-${inc.id}`}>
            <CircleMarker
              center={[inc.location.lat, inc.location.lng]}
              radius={18}
              stroke={false}
              pathOptions={{
                color: '#ef4444',
                fillColor: '#ef4444',
                fillOpacity: 0.15,
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

        {/* ═══ INCIDENT ROUTES — only for active incidents in current city ═══ */}
        {/* ═══ LAYER 1: ALL alternate routes (GREEN) — bottom layer ═══ */}
        {/* Only render routes with valid geometry (>=5 points = real road route) */}
        {incidentRoutes
          .filter(rp => incidents.some(i => i.id === rp.incidentId && i.city === city && i.status === 'active'))
          .map((routePair) =>
            routePair.alternate?.geometry?.coordinates && routePair.alternate.geometry.coordinates.length >= 5 && (
              <Polyline
                key={`alt-${routePair.incidentId}`}
                positions={routePair.alternate.geometry.coordinates.map((c: number[]) => [c[1], c[0]] as [number, number])}
                pathOptions={{ color: '#10b981', weight: 6, opacity: 0.9 }}
              >
                <Tooltip sticky>
                  <span className="text-[10px] font-mono">
                    🟢 Alternate Route
                    {routePair.alternate?.estimated_extra_minutes != null && ` • +${routePair.alternate.estimated_extra_minutes} min`}
                    {routePair.alternate?.avg_speed_kmh && ` • ${routePair.alternate.avg_speed_kmh} km/h avg`}
                  </span>
                </Tooltip>
              </Polyline>
            )
          )}

        {/* ═══ LAYER 2: ALL blocked routes (RED) — top layer, always covers green ═══ */}
        {incidentRoutes
          .filter(rp => incidents.some(i => i.id === rp.incidentId && i.city === city && i.status === 'active'))
          .map((routePair) =>
            routePair.blocked?.geometry?.coordinates && routePair.blocked.geometry.coordinates.length >= 5 && (
              <Polyline
                key={`blk-${routePair.incidentId}`}
                positions={routePair.blocked.geometry.coordinates.map((c: number[]) => [c[1], c[0]] as [number, number])}
                pathOptions={{ color: '#ef4444', weight: 7, opacity: 0.85, dashArray: '10,10' }}
              >
                <Tooltip sticky>
                  <span className="text-[10px] font-mono">
                    🔴 Congested Route — {routePair.blocked?.street_names?.join(' → ') || 'Blocked road'}
                    {routePair.blocked?.total_length_km && ` • ${routePair.blocked.total_length_km} km`}
                  </span>
                </Tooltip>
              </Polyline>
            )
          )}

        {/* ═══ LAYER 3: ALL route markers — topmost, only show if alternate route has valid geometry ═══ */}
        {incidentRoutes
          .filter(rp => 
            incidents.some(i => i.id === rp.incidentId && i.city === city && i.status === 'active') &&
            rp.alternate?.geometry?.coordinates?.length >= 5
          )
          .map((routePair) => (
            <React.Fragment key={`markers-${routePair.incidentId}`}>
              {routePair.origin && (
                <CircleMarker
                  center={[routePair.origin[1], routePair.origin[0]]}
                  radius={8}
                  pathOptions={{ color: '#10b981', fillColor: '#10b981', fillOpacity: 1, weight: 2 }}
                >
                  <Tooltip direction="top" offset={[0, -8]} permanent>
                    <span className="text-[9px] font-mono font-bold">↗ DIVERT HERE</span>
                  </Tooltip>
                </CircleMarker>
              )}
              {routePair.destination && (
                <CircleMarker
                  center={[routePair.destination[1], routePair.destination[0]]}
                  radius={8}
                  pathOptions={{ color: '#10b981', fillColor: '#10b981', fillOpacity: 1, weight: 2 }}
                >
                  <Tooltip direction="top" offset={[0, -8]} permanent>
                    <span className="text-[9px] font-mono font-bold">✓ REJOIN</span>
                  </Tooltip>
                </CircleMarker>
              )}
            </React.Fragment>
          ))}

        {/* ═══ CONGESTION ZONES — permanent avoidance areas ═══ */}
        {congestionZones
          .filter((z: any) => z.city === city)
          .map((zone: any) => (
            zone.polygon && zone.polygon.length >= 4 && (
              <Polygon
                key={`czone-${zone.zone_id}`}
                positions={zone.polygon.map((c: number[]) => [c[1], c[0]] as [number, number])}
                pathOptions={{
                  color: zone.severity === 'severe' ? '#f59e0b' : '#fbbf24',
                  fillColor: zone.severity === 'severe' ? '#f59e0b' : '#fbbf24',
                  fillOpacity: 0.15,
                  weight: 2,
                  dashArray: '6,4',
                }}
              >
                <Tooltip sticky>
                  <span className="text-[10px] font-mono">
                    ⚠️ {zone.name} — {zone.severity} congestion zone
                  </span>
                </Tooltip>
              </Polygon>
            )
          ))}

        {/* Collision markers removed — data used by LLM only, visual noise on map */}



        {/* Surveillance Cameras */}
        {BIG_INTERSECTIONS.map((cam) => (
          <CircleMarker
            key={`cam-${cam.id}`}
            center={[cam.lat, cam.lng]}
            radius={8}
            pathOptions={{ color: '#0ea5e9', fillColor: '#0ea5e9', fillOpacity: 0.9, weight: 2 }}
          >
            <CameraPopup cam={cam} />
            <Tooltip direction="top" offset={[0, -8]} opacity={0.95}>
              <span className="text-[11px] font-mono font-bold text-[#0ea5e9]">
                📹 Camera: {cam.name}
              </span>
            </Tooltip>
          </CircleMarker>
        ))}

      </MapContainer>
    </div>
  );
};

export default TrafficMap;
