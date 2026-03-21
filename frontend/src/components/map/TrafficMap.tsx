import React from 'react';
import { MapContainer, TileLayer, Polyline, CircleMarker } from 'react-leaflet';
import L from 'leaflet';

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

/* ═══ MOCK TRAFFIC SEGMENTS ═══ */
const SEGMENTS: { id: string; coords: [number, number][]; speed: number; name: string }[] = [
  {
    id: 'S-1001', name: 'Broadway SB', speed: 3,
    coords: [[40.7541, -73.9870], [40.7527, -73.9876], [40.7512, -73.9883], [40.7500, -73.9888], [40.7490, -73.9893]],
  },
  {
    id: 'S-1002', name: '7th Ave SB', speed: 8,
    coords: [[40.7535, -73.9907], [40.7520, -73.9912], [40.7505, -73.9917], [40.7490, -73.9922]],
  },
  {
    id: 'S-1003', name: '6th Ave NB', speed: 22,
    coords: [[40.7480, -73.9880], [40.7495, -73.9875], [40.7510, -73.9870], [40.7530, -73.9862]],
  },
  {
    id: 'S-1004', name: '8th Ave SB', speed: 18,
    coords: [[40.7560, -73.9930], [40.7545, -73.9935], [40.7530, -73.9940], [40.7505, -73.9950]],
  },
  {
    id: 'S-1005', name: 'W 34th St EB', speed: 5,
    coords: [[40.7505, -73.9952], [40.7507, -73.9930], [40.7510, -73.9910], [40.7512, -73.9888], [40.7514, -73.9865]],
  },
  {
    id: 'S-1006', name: 'W 42nd St EB', speed: 25,
    coords: [[40.7575, -74.0005], [40.7573, -73.9980], [40.7571, -73.9955], [40.7569, -73.9935]],
  },
  {
    id: 'S-1007', name: '10th Ave SB', speed: 28,
    coords: [[40.7582, -74.0010], [40.7560, -74.0005], [40.7540, -74.0000], [40.7520, -73.9995], [40.7500, -73.9990]],
  },
];

/* ═══ DIVERSION ROUTE ═══ */
const DIVERSION_PATH: [number, number][] = [
  [40.7500, -73.9990], [40.7540, -74.0000], [40.7575, -74.0005],
  [40.7575, -73.9935], [40.7569, -73.9935], [40.7545, -73.9935], [40.7505, -73.9950],
];

const INCIDENT_LOCATION: [number, number] = [40.7500, -73.9888];

const getSpeedColorAndWeight = (speed: number) => {
  if (speed < 10) return { color: '#ef4444', weight: 4 }; // Red for stopped/critical
  if (speed < 20) return { color: '#a1a1aa', weight: 3 }; // Light gray for slow
  return { color: '#3f3f46', weight: 2 }; // Dark gray for normal
};

const TrafficMap: React.FC = () => {
  return (
    <div className="w-full h-full relative">
      <MapContainer
        center={NYC_CENTER}
        zoom={15}
        className="w-full h-full"
        zoomControl={false}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png"
          attribution='&copy; CARTO'
        />

        {/* Traffic Speed Segments */}
        {SEGMENTS.map((segment) => {
          const style = getSpeedColorAndWeight(segment.speed);
          return (
            <Polyline
              key={segment.id}
              positions={segment.coords}
              pathOptions={{
                color: style.color,
                weight: style.weight,
                opacity: 1,
              }}
            />
          );
        })}

        {/* Diversion Route */}
        <Polyline
          positions={DIVERSION_PATH}
          pathOptions={{
            color: '#ffffff',
            weight: 3,
            opacity: 0.8,
            dashArray: '5, 5',
          }}
        />

        {/* Incident Marker Minimal */}
        <CircleMarker
          center={INCIDENT_LOCATION}
          radius={6}
          pathOptions={{
            color: '#ef4444',
            fillColor: '#ef4444',
            fillOpacity: 1,
            weight: 2,
          }}
        />

      </MapContainer>
    </div>
  );
};

export default TrafficMap;
