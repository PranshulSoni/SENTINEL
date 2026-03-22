import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  MapContainer,
  TileLayer,
  Polyline,
  Circle,
  CircleMarker,
  Tooltip,
  useMap,
} from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { api } from '../../services/api';
import { useFeedStore, useIncidentStore } from '../../store';
import { CameraPopup } from './CameraPopup';

const NYC_CENTER: [number, number] = [40.7128, -74.006];
const DEFAULT_ZOOM = 14;

const SEVERITY_RADIUS_M: Record<string, number> = {
  critical: 600,
  major: 450,
  moderate: 330,
  minor: 220,
};

const CAMERA_POINTS = [
  { id: '1', name: 'W 34th St & 7th Ave', lat: 40.7505, lng: -73.9904 },
  { id: '2', name: 'Broadway & 34th St', lat: 40.7484, lng: -73.9878 },
  { id: '3', name: '10th Ave & 42nd St', lat: 40.7579, lng: -73.998 },
  { id: '4', name: 'Tribune Chowk', lat: 30.727, lng: 76.7675 },
  { id: '5', name: 'Piccadily Chowk', lat: 30.7246, lng: 76.7621 },
];

type LatLng = [number, number];

const toLatLng = (coords: number[][] = []): LatLng[] =>
  coords.filter((c) => c.length >= 2).map((c) => [c[1], c[0]]);

const mapMidpoint = (pts: LatLng[]): LatLng | null => {
  if (!pts.length) return null;
  const mid = pts[Math.floor(pts.length / 2)];
  return [mid[0], mid[1]];
};

const MapController: React.FC<{
  center: { lat: number; lng: number; zoom?: number } | null;
  focusIncident?: { id: string; location: { lat: number; lng: number } } | null;
}> = ({ center, focusIncident }) => {
  const map = useMap();
  const lastFocusedIdRef = useRef<string | null>(null);
  useEffect(() => {
    if (!center) return;
    map.flyTo([center.lat, center.lng], center.zoom || DEFAULT_ZOOM, { duration: 1.2 });
  }, [center, map]);

  useEffect(() => {
    if (!focusIncident?.id) return;
    if (lastFocusedIdRef.current === focusIncident.id) return;
    lastFocusedIdRef.current = focusIncident.id;
    map.flyTo([focusIncident.location.lat, focusIncident.location.lng], 16, { duration: 1.0 });
  }, [focusIncident?.id, focusIncident?.location?.lat, focusIncident?.location?.lng, map]);

  return null;
};

const TrafficMap: React.FC = () => {
  const { cityCenter, city } = useFeedStore();
  const { incidents, currentIncident, setCollisions, setIncident, setLLMOutput, incidentRoutes, congestionZones } = useIncidentStore();
  const [selectedCamera, setSelectedCamera] = useState<(typeof CAMERA_POINTS)[number] | null>(null);

  useEffect(() => {
    if (!currentIncident) return;
    api
      .getNearbyCollisions(currentIncident.location.lat, currentIncident.location.lng, 0.01)
      .then((data) => {
        if (Array.isArray(data)) setCollisions(data);
      })
      .catch(() => {});
  }, [currentIncident?.id, setCollisions]);

  const activeIncidents = useMemo(
    () => incidents.filter((inc) => inc.status === 'active' && inc.city === city),
    [incidents, city],
  );

  const routePairs = useMemo(() => {
    return incidentRoutes.filter((rp: any) => {
      if ((rp as any).is_consolidated && (rp as any).incident_ids) {
        return (rp as any).incident_ids.some((id: string) =>
          activeIncidents.some((inc) => inc.id === id),
        );
      }
      return activeIncidents.some((inc) => inc.id === rp.incidentId);
    });
  }, [incidentRoutes, activeIncidents]);

  const center: LatLng = cityCenter
    ? [cityCenter.lat, cityCenter.lng]
    : NYC_CENTER;

  return (
    <div className="w-full h-full relative">
      <MapContainer
        center={center}
        zoom={cityCenter?.zoom || DEFAULT_ZOOM}
        className="w-full h-full"
        zoomControl
      >
        <MapController center={cityCenter} focusIncident={currentIncident} />
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {congestionZones
          .filter((z: any) => z.city === city)
          .flatMap((z: any) => z.segment_geometries || [])
          .filter((seg: any) => Array.isArray(seg.geometry) && seg.geometry.length >= 2)
          .map((seg: any, i: number) => (
            <Polyline
              key={`congestion-${i}`}
              positions={toLatLng(seg.geometry)}
              pathOptions={{
                color: '#f59e0b',
                weight: 10,
                opacity: 0.65,
              }}
            />
          ))}

        {activeIncidents.map((inc) => {
          const radius = SEVERITY_RADIUS_M[inc.severity] || 330;
          const centerPt: LatLng = [inc.location.lat, inc.location.lng];
          const isFocused = currentIncident?.id === inc.id;
          return (
            <React.Fragment key={`inc-${inc.id}`}>
              <Circle center={centerPt} radius={radius} pathOptions={{ color: '#fbbf24', fillColor: '#fbbf24', fillOpacity: 0.12, weight: 0 }} />
              <Circle center={centerPt} radius={radius * 0.5} pathOptions={{ color: '#f59e0b', fillColor: '#f59e0b', fillOpacity: 0.22, weight: 0 }} />
              <Circle center={centerPt} radius={radius * 0.25} pathOptions={{ color: '#ef4444', fillColor: '#ef4444', fillOpacity: 0.34, weight: 0 }} />
              <CircleMarker
                center={centerPt}
                radius={isFocused ? 8 : 6}
                pathOptions={{
                  color: '#fff',
                  weight: isFocused ? 3 : 2,
                  fillColor: '#ef4444',
                  fillOpacity: 0.95,
                }}
                eventHandlers={{
                  click: () => {
                    setIncident(inc);
                    api.getLLMOutput(inc.id)
                      .then((llm) => {
                        if (llm && typeof llm === 'object') {
                          setLLMOutput(llm);
                        }
                      })
                      .catch(() => {});
                  },
                }}
              >
                <Tooltip direction="top" permanent>
                  <span className="font-mono text-[10px]">
                    {`⚠ ${inc.severity.toUpperCase()}: ${inc.on_street}${isFocused ? ' [SELECTED]' : ''}`}
                  </span>
                </Tooltip>
              </CircleMarker>
            </React.Fragment>
          );
        })}

        {routePairs.map((rp: any, i: number) => {
          const blocked = toLatLng(rp.blocked?.geometry?.coordinates || []);
          const alternate = toLatLng(rp.alternate?.geometry?.coordinates || []);
          const blockedMid = mapMidpoint(blocked);
          const alternateMid = mapMidpoint(alternate);
          const blockedLabel = rp.blocked?.label || 'BLOCKED ROAD';
          const routeMeta = rp.meta || {};
          const safeLabel = rp.alternate?.label || 'SAFE ROUTE';
          const modeledEta = Number(rp.alternate?.estimated_minutes || 0);
          const actualEta = Number(rp.alternate?.estimated_actual_minutes || modeledEta || 0);
          const etaLabel = actualEta > 0 ? ` · ETA ${actualEta.toFixed(1)}m` : '';
          const isFallbackEstimate =
            Boolean(routeMeta?.fallback_used) ||
            routeMeta?.routing_engine === 'degraded' ||
            Boolean(routeMeta?.using_last_known_safe_route) ||
            String(safeLabel).toUpperCase().includes('LOCAL ESTIMATE');
          const safeLabelWhenHidden = routeMeta?.using_last_known_safe_route
            ? `${safeLabel}${etaLabel} (RETAINED)`
            : `${safeLabel}${etaLabel} (RECALCULATING)`;
          const alternateStyle = isFallbackEstimate
            ? { color: '#16a34a', weight: 6, opacity: 0.78, dashArray: '8 6' }
            : { color: '#16a34a', weight: 7, opacity: 0.96 };
          const start = blocked[0];
          const end = blocked.length ? blocked[blocked.length - 1] : null;
          const safeAnchor = alternateMid || blockedMid || start || end;
          return (
            <React.Fragment key={`route-${rp.incidentId || i}`}>
              {alternate.length >= 2 && (
                <Polyline positions={alternate} pathOptions={alternateStyle} />
              )}
              {blocked.length >= 2 && (
                <>
                  <Polyline positions={blocked} pathOptions={{ color: '#ffffff', weight: 12, opacity: 0.42 }} />
                  <Polyline positions={blocked} pathOptions={{ color: '#dc2626', weight: 8, opacity: 1, dashArray: '9 6' }} />
                </>
              )}
              {blockedMid && (
                <CircleMarker center={blockedMid} radius={1} opacity={0} fillOpacity={0}>
                  <Tooltip direction="center" permanent>
                    <span className="font-mono text-[10px] font-bold">{blockedLabel}</span>
                  </Tooltip>
                </CircleMarker>
              )}
              {safeAnchor && (
                <CircleMarker center={safeAnchor} radius={1} opacity={0} fillOpacity={0}>
                  <Tooltip direction="center" permanent>
                    <span className="font-mono text-[10px] font-bold">
                      {alternate.length >= 2 ? `${safeLabel}${etaLabel}` : safeLabelWhenHidden}
                    </span>
                  </Tooltip>
                </CircleMarker>
              )}
              {start && (
                <CircleMarker center={start} radius={4} pathOptions={{ color: '#fff', weight: 1, fillColor: '#22c55e', fillOpacity: 1 }} />
              )}
              {end && (
                <CircleMarker center={end} radius={4} pathOptions={{ color: '#fff', weight: 1, fillColor: '#3b82f6', fillOpacity: 1 }} />
              )}
            </React.Fragment>
          );
        })}

        {CAMERA_POINTS.map((cam) => (
          <React.Fragment key={`cam-${cam.id}`}>
            <CircleMarker
              center={[cam.lat, cam.lng]}
              radius={6}
              pathOptions={{ color: '#fff', weight: 2, fillColor: '#3b82f6', fillOpacity: 0.9 }}
              eventHandlers={{
                click: () => setSelectedCamera(cam),
              }}
            />
            {selectedCamera?.id === cam.id && <CameraPopup cam={cam} onClose={() => setSelectedCamera(null)} />}
          </React.Fragment>
        ))}
      </MapContainer>
    </div>
  );
};

export default TrafficMap;
