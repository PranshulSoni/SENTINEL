import React, { useEffect } from 'react';
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

const NYC_CENTER: [number, number] = [40.7505, -73.9934];
const DEFAULT_ZOOM = 15;

const getSpeedColor = (speed: number): string => {
  if (speed < 5) return '#ef4444';  // red — blocked
  if (speed < 15) return '#eab308'; // yellow — slow
  return '#22c55e';                 // green — free flow
};

const MapController: React.FC<{ center: [number, number]; zoom: number }> = ({ center, zoom }) => {
  const map = useMap();
  useEffect(() => {
    map.setView(center, zoom);
  }, [center, zoom, map]);
  return null;
};

const TrafficMap: React.FC = () => {
  const { segments, cityCenter } = useFeedStore();
  const { currentIncident, diversionRoutes, collisions, setCollisions } = useIncidentStore();

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
        <MapController center={mapCenter} zoom={mapZoom} />

        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png"
          attribution='&copy; CARTO'
        />

        {/* Traffic Speed Segments */}
        {segments.map((seg) => (
          <CircleMarker
            key={seg.link_id}
            center={[seg.lat, seg.lng]}
            radius={seg.speed < 5 ? 8 : 6}
            pathOptions={{
              color: getSpeedColor(seg.speed),
              fillColor: getSpeedColor(seg.speed),
              fillOpacity: 0.85,
              weight: 1,
            }}
          >
            <Tooltip direction="top" offset={[0, -6]} opacity={0.9}>
              <span className="text-[10px] font-mono">
                {seg.link_name} — {seg.speed.toFixed(0)} mph
              </span>
            </Tooltip>
          </CircleMarker>
        ))}

        {/* Incident Marker with pulsing effect */}
        {currentIncident && (
          <>
            <CircleMarker
              center={[currentIncident.location.lat, currentIncident.location.lng]}
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
              center={[currentIncident.location.lat, currentIncident.location.lng]}
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
                  INCIDENT: {currentIncident.on_street}
                </span>
              </Tooltip>
            </CircleMarker>
          </>
        )}

        {/* Diversion Route Polylines */}
        {diversionRoutes.map((route: any, idx: number) => {
          const coords = route.geometry?.coordinates;
          if (!coords || !Array.isArray(coords)) return null;
          const positions = coords.map((c: number[]) => [c[1], c[0]] as [number, number]);
          return (
            <Polyline
              key={`diversion-${idx}`}
              positions={positions}
              pathOptions={{
                color: idx === 0 ? '#3b82f6' : '#60a5fa',
                weight: 4,
                opacity: 0.8,
                dashArray: idx === 0 ? undefined : '10 6',
              }}
            >
              <Tooltip sticky>
                <span className="text-[10px] font-mono">
                  {route.name || `Diversion ${idx + 1}`}
                  {route.distance_km ? ` — ${route.distance_km.toFixed(1)} km` : ''}
                </span>
              </Tooltip>
            </Polyline>
          );
        })}

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

      </MapContainer>
    </div>
  );
};

export default TrafficMap;
