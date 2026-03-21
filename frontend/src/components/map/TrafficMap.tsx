import React, { useEffect, useRef, useMemo, useState } from 'react';
import Map, { Source, Layer, Marker, useMap } from 'react-map-gl/mapbox';
import 'mapbox-gl/dist/mapbox-gl.css';
import { useFeedStore, useIncidentStore } from '../../store';
import { CameraPopup } from './CameraPopup';
import { api } from '../../services/api';

const NYC_CENTER: [number, number] = [-74.0060, 40.7128]; // [lng, lat] NYC fallback
const DEFAULT_ZOOM = 15;

const SEVERITY_RADIUS: Record<string, number> = {
  critical: 600,
  major: 450,
  moderate: 330,
  minor: 220,
};

const BIG_INTERSECTIONS = [
  { id: '1', name: "W 34th St & 7th Ave", lat: 40.7505, lng: -73.9904 },
  { id: '2', name: "Broadway & 34th St", lat: 40.7484, lng: -73.9878 },
  { id: '3', name: "10th Ave & 42nd St", lat: 40.7579, lng: -73.9980 },
  { id: '4', name: "Tribune Chowk", lat: 30.7270, lng: 76.7675 },
  { id: '5', name: "Piccadily Chowk", lat: 30.7246, lng: 76.7621 }
];

const MapController: React.FC<{ city: string }> = ({ city }) => {
  const { cityCenter } = useFeedStore();
  const { current: map } = useMap();
  const prevCityRef = useRef<string>('');

  useEffect(() => {
    if (map && cityCenter && prevCityRef.current !== city) {
      map.flyTo({
        center: [cityCenter.lng, cityCenter.lat],
        zoom: cityCenter.zoom || DEFAULT_ZOOM,
        duration: 1500
      });
      prevCityRef.current = city;
    }
  }, [city, cityCenter, map]);

  return null;
};

const TrafficMap: React.FC = () => {
  const { cityCenter, city } = useFeedStore();
  const { incidents, currentIncident, setCollisions, incidentRoutes, congestionZones } = useIncidentStore();
  const [selectedCamera, setSelectedCamera] = useState<typeof BIG_INTERSECTIONS[0] | null>(null);

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

  // Build GeoJSON for incident gradient zones
  const incidentGeoJSON = useMemo(() => ({
    type: 'FeatureCollection' as const,
    features: incidents
      .filter(inc => inc.status === 'active' && inc.city === city)
      .flatMap(inc => {
        const baseRadius = SEVERITY_RADIUS[inc.severity] || 330;
        return [
          { type: 'Feature' as const, properties: { layer: 'outer', radiusMeters: baseRadius, id: inc.id },
            geometry: { type: 'Point' as const, coordinates: [inc.location.lng, inc.location.lat] } },
          { type: 'Feature' as const, properties: { layer: 'middle', radiusMeters: baseRadius * 0.5, id: inc.id },
            geometry: { type: 'Point' as const, coordinates: [inc.location.lng, inc.location.lat] } },
          { type: 'Feature' as const, properties: { layer: 'inner', radiusMeters: baseRadius * 0.25, id: inc.id },
            geometry: { type: 'Point' as const, coordinates: [inc.location.lng, inc.location.lat] } },
        ];
      })
  }), [incidents, city]);

  // Build GeoJSON for routes
  const routeGeoJSON = useMemo(() => {
    const consolidatedIncidentIds = new Set<string>();
    incidentRoutes.forEach(rp => {
      if ((rp as any).is_consolidated && (rp as any).incident_ids) {
        ((rp as any).incident_ids as string[]).forEach(id => consolidatedIncidentIds.add(id));
      }
    });

    const features: any[] = [];
    incidentRoutes.forEach(rp => {
      const isConsolidated = (rp as any).is_consolidated;
      if (isConsolidated) {
        const hasActive = ((rp as any).incident_ids || []).some((id: string) =>
          incidents.some(i => i.id === id && i.city === city && i.status === 'active')
        );
        if (!hasActive) return;
      } else {
        const isActive = incidents.some(i => i.id === rp.incidentId && i.city === city && i.status === 'active');
        if (!isActive || consolidatedIncidentIds.has(rp.incidentId)) return;
      }

      if (rp.blocked?.geometry?.coordinates?.length >= 5) {
        features.push({
          type: 'Feature',
          properties: { routeType: 'blocked', incidentId: rp.incidentId },
          geometry: rp.blocked.geometry
        });
      }
      if (rp.alternate?.geometry?.coordinates?.length >= 5) {
        features.push({
          type: 'Feature',
          properties: { routeType: 'alternate', incidentId: rp.incidentId, isConsolidated: !!isConsolidated },
          geometry: rp.alternate.geometry
        });
      }
    });

    return { type: 'FeatureCollection' as const, features };
  }, [incidentRoutes, incidents, city]);

  // Build GeoJSON for congestion zones
  const congestionGeoJSON = useMemo(() => ({
    type: 'FeatureCollection' as const,
    features: congestionZones
      .filter((z: any) => z.city === city)
      .flatMap((zone: any) =>
        (zone.segment_geometries || [])
          .filter((seg: any) => seg.geometry && seg.geometry.length >= 2)
          .map((seg: any) => ({
            type: 'Feature' as const,
            properties: { severity: zone.severity, name: seg.name, speed: seg.speed },
            geometry: { type: 'LineString' as const, coordinates: seg.geometry }
          }))
      )
  }), [congestionZones, city]);

  return (
    <div className="w-full h-full relative">
      <Map
        mapboxAccessToken={import.meta.env.VITE_MAPBOX_TOKEN}
        initialViewState={{
          longitude: cityCenter?.lng || NYC_CENTER[0],
          latitude: cityCenter?.lat || NYC_CENTER[1],
          zoom: cityCenter?.zoom || DEFAULT_ZOOM
        }}
        style={{ width: '100%', height: '100%' }}
        mapStyle="mapbox://styles/mapbox/dark-v11"
      >
        <MapController city={city} />

        {/* Congestion zone road overlays */}
        <Source id="congestion" type="geojson" data={congestionGeoJSON}>
          <Layer
            id="congestion-lines"
            type="line"
            paint={{
              'line-color': ['case', ['==', ['get', 'severity'], 'severe'], '#ef4444', '#f59e0b'],
              'line-width': 12,
              'line-opacity': 0.7,
            }}
            layout={{ 'line-cap': 'round', 'line-join': 'round' }}
          />
        </Source>

        {/* Incident gradient zones */}
        <Source id="incidents" type="geojson" data={incidentGeoJSON}>
          <Layer
            id="incident-outer"
            type="circle"
            filter={['==', ['get', 'layer'], 'outer']}
            paint={{
              'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 30, 15, 100, 18, 180],
              'circle-color': '#fbbf24',
              'circle-opacity': 0.15,
            }}
          />
          <Layer
            id="incident-middle"
            type="circle"
            filter={['==', ['get', 'layer'], 'middle']}
            paint={{
              'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 15, 15, 50, 18, 90],
              'circle-color': '#f59e0b',
              'circle-opacity': 0.35,
            }}
          />
          <Layer
            id="incident-inner"
            type="circle"
            filter={['==', ['get', 'layer'], 'inner']}
            paint={{
              'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 8, 15, 25, 18, 45],
              'circle-color': '#ef4444',
              'circle-opacity': 0.7,
            }}
          />
        </Source>

        {/* Route layers */}
        <Source id="routes" type="geojson" data={routeGeoJSON}>
          {/* Route casing (outline) for visibility - renders first (bottom) */}
          <Layer
            id="route-casing"
            type="line"
            paint={{
              'line-color': '#ffffff',
              'line-width': 10,
              'line-opacity': 0.3,
            }}
            layout={{ 'line-cap': 'round', 'line-join': 'round' }}
          />
          {/* Blocked route - dashed red, renders above casing */}
          <Layer
            id="blocked-routes"
            type="line"
            filter={['==', ['get', 'routeType'], 'blocked']}
            paint={{
              'line-color': '#ef4444',
              'line-width': 6,
              'line-opacity': 0.9,
              'line-dasharray': [3, 2],
            }}
            layout={{ 'line-cap': 'round', 'line-join': 'round' }}
          />
          {/* Alternate route - solid green, renders on top */}
          <Layer
            id="alternate-routes"
            type="line"
            filter={['==', ['get', 'routeType'], 'alternate']}
            paint={{
              'line-color': ['case', ['get', 'isConsolidated'], '#8b5cf6', '#22c55e'],
              'line-width': 8,
              'line-opacity': 1,
            }}
            layout={{ 'line-cap': 'round', 'line-join': 'round' }}
          />
        </Source>

        {/* Incident markers with labels */}
        {incidents.filter(inc => inc.status === 'active' && inc.city === city).map(inc => (
          <Marker key={`marker-${inc.id}`} longitude={inc.location.lng} latitude={inc.location.lat}>
            <div className="relative">
              <div className="w-3 h-3 rounded-full bg-red-500 border-2 border-white shadow-lg animate-pulse" />
              <div className="absolute -top-8 left-1/2 -translate-x-1/2 whitespace-nowrap bg-black/90 px-2 py-1 rounded text-[10px] font-mono text-white border border-gray-700">
                ⚠️ {inc.severity.toUpperCase()}: {inc.on_street}
              </div>
            </div>
          </Marker>
        ))}

        {/* Camera markers */}
        {BIG_INTERSECTIONS.map(cam => (
          <Marker
            key={`cam-${cam.id}`}
            longitude={cam.lng}
            latitude={cam.lat}
            onClick={(e) => {
              e.originalEvent.stopPropagation();
              setSelectedCamera(cam);
            }}
          >
            <div className="w-5 h-5 rounded-full bg-blue-500/80 border-2 border-white cursor-pointer flex items-center justify-center hover:bg-blue-400 transition-colors">
              <span className="text-[10px]">📹</span>
            </div>
          </Marker>
        ))}

        {/* Camera popup */}
        {selectedCamera && (
          <CameraPopup
            cam={selectedCamera}
            onClose={() => setSelectedCamera(null)}
          />
        )}
      </Map>
    </div>
  );
};

export default TrafficMap;