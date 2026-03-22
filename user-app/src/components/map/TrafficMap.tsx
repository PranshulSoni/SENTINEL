import React, { useEffect, useMemo, useState } from 'react';
import Map, { Source, Layer, Marker, useMap } from 'react-map-gl/mapbox';
import 'mapbox-gl/dist/mapbox-gl.css';
import { useFeedStore, useIncidentStore } from '../../store';
import { api } from '../../services/api';

const FALLBACK_CENTER: [number, number] = [76.7794, 30.7333]; // [lng, lat] for Chandigarh
const DEFAULT_ZOOM = 15;

type SafeRoute = {
  incidentId: string;
  geometry: { type: 'LineString'; coordinates: number[][] };
  label: string;
  extraMinutes: number;
};

type BlockedRoute = {
  incidentId: string;
  geometry: { type: 'LineString'; coordinates: number[][] };
  label: string;
};

const midpoint = (coords: number[][]): number[] | null => {
  if (!Array.isArray(coords) || coords.length < 2) return null;
  return coords[Math.floor(coords.length / 2)] || null;
};

const MapController: React.FC = () => {
  const { cityCenter } = useFeedStore();
  const { current: map } = useMap();

  useEffect(() => {
    if (map && cityCenter) {
      map.flyTo({
        center: [cityCenter.lng, cityCenter.lat],
        zoom: cityCenter.zoom || DEFAULT_ZOOM,
        duration: 1500
      });
    }
  }, [cityCenter, map]);

  return null;
};

const TrafficMap: React.FC = () => {
  const { city, cityCenter } = useFeedStore();
  const { incidents } = useIncidentStore();
  const [safeRoutes, setSafeRoutes] = useState<SafeRoute[]>([]);
  const [blockedRoutes, setBlockedRoutes] = useState<BlockedRoute[]>([]);

  const activeCityIncidents = useMemo(
    () =>
      incidents.filter((inc: any) => {
        const incCity = (inc.city || '').toLowerCase();
        const status = (inc.status || 'active').toLowerCase();
        return incCity === city && status === 'active';
      }),
    [incidents, city],
  );

  useEffect(() => {
    let cancelled = false;

    const loadRoutes = async () => {
      try {
        const routeResults = await Promise.all(
          activeCityIncidents.map(async (inc: any) => {
            const incidentId = String(inc.id || inc._id || '');
            if (!incidentId) return null;
            const data = await api.getIncidentRoutes(incidentId);
            const safeCoords = data?.alternate?.geometry?.coordinates || [];
            const blockedCoords = data?.blocked?.geometry?.coordinates || [];
            const safeValid = Array.isArray(safeCoords) && safeCoords.length >= 2;
            const blockedValid = Array.isArray(blockedCoords) && blockedCoords.length >= 2;
            if (!safeValid && !blockedValid) return null;
            const extra = Number(
              data?.alternate?.estimated_actual_extra_minutes ??
                data?.alternate?.estimated_extra_minutes ??
                0,
            );
            return {
              incidentId,
              safe: safeValid
                ? {
                    geometry: { type: 'LineString' as const, coordinates: safeCoords },
                    label: data?.alternate?.label || 'SAFE ROUTE',
                  }
                : null,
              blocked: blockedValid
                ? {
                    geometry: { type: 'LineString' as const, coordinates: blockedCoords },
                    label: data?.blocked?.label || 'BLOCKED ROAD',
                  }
                : null,
              extraMinutes: Number.isFinite(extra) ? extra : 0,
            };
          }),
        );
        if (!cancelled) {
          const valid = routeResults.filter(Boolean) as Array<{
            incidentId: string;
            safe: { geometry: { type: 'LineString'; coordinates: number[][] }; label: string } | null;
            blocked: { geometry: { type: 'LineString'; coordinates: number[][] }; label: string } | null;
            extraMinutes: number;
          }>;
          setSafeRoutes(
            valid
              .filter((r) => Boolean(r.safe))
              .map((r) => ({
                incidentId: r.incidentId,
                geometry: r.safe!.geometry,
                label: r.safe!.label,
                extraMinutes: r.extraMinutes,
              })),
          );
          setBlockedRoutes(
            valid
              .filter((r) => Boolean(r.blocked))
              .map((r) => ({
                incidentId: r.incidentId,
                geometry: r.blocked!.geometry,
                label: r.blocked!.label,
              })),
          );
        }
      } catch {
        if (!cancelled) {
          setSafeRoutes([]);
          setBlockedRoutes([]);
        }
      }
    };

    loadRoutes();
    const timer = setInterval(loadRoutes, 8000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [activeCityIncidents]);

  const safeRouteGeoJSON = useMemo(
    () => ({
      type: 'FeatureCollection' as const,
      features: safeRoutes.map((route, idx) => ({
        type: 'Feature' as const,
        properties: { idx },
        geometry: route.geometry,
      })),
    }),
    [safeRoutes],
  );

  const blockedRouteGeoJSON = useMemo(
    () => ({
      type: 'FeatureCollection' as const,
      features: blockedRoutes.map((route, idx) => ({
        type: 'Feature' as const,
        properties: { idx },
        geometry: route.geometry,
      })),
    }),
    [blockedRoutes],
  );

  return (
    <div className="w-full h-full relative">
      <Map
        mapboxAccessToken={import.meta.env.VITE_MAPBOX_TOKEN}
        initialViewState={{
          longitude: cityCenter?.lng || FALLBACK_CENTER[0],
          latitude: cityCenter?.lat || FALLBACK_CENTER[1],
          zoom: cityCenter?.zoom || DEFAULT_ZOOM
        }}
        style={{ width: '100%', height: '100%' }}
        mapStyle="mapbox://styles/mapbox/light-v11"
      >
        <MapController />

        <Source id="blocked-routes" type="geojson" data={blockedRouteGeoJSON}>
          <Layer
            id="blocked-route-casing"
            type="line"
            paint={{
              'line-color': '#ffffff',
              'line-width': 10,
              'line-opacity': 0.46,
            }}
            layout={{ 'line-cap': 'round', 'line-join': 'round' }}
          />
          <Layer
            id="blocked-route-lines"
            type="line"
            paint={{
              'line-color': '#dc2626',
              'line-width': 7,
              'line-opacity': 0.98,
              'line-dasharray': [2, 1.4],
            }}
            layout={{ 'line-cap': 'round', 'line-join': 'round' }}
          />
        </Source>

        <Source id="safe-routes" type="geojson" data={safeRouteGeoJSON}>
          <Layer
            id="safe-route-lines"
            type="line"
            paint={{
              'line-color': '#16a34a',
              'line-width': 6,
              'line-opacity': 0.95,
            }}
            layout={{ 'line-cap': 'round', 'line-join': 'round' }}
          />
        </Source>

        {blockedRoutes.map((route) => {
          const mid = midpoint(route.geometry.coordinates);
          if (!mid || mid.length < 2) return null;
          return (
            <Marker key={`blocked-label-${route.incidentId}`} longitude={mid[0]} latitude={mid[1]}>
              <div className="bg-white/95 border border-gray-300 rounded px-2 py-1 shadow text-[10px] font-bold text-[#991b1b] whitespace-nowrap">
                {route.label}
              </div>
            </Marker>
          );
        })}

        {safeRoutes.map((route) => {
          const mid = midpoint(route.geometry.coordinates || []);
          if (!mid || mid.length < 2) return null;
          return (
            <Marker key={`safe-label-${route.incidentId}`} longitude={mid[0]} latitude={mid[1]}>
              <div className="bg-white/95 border border-gray-300 rounded px-2 py-1 shadow text-[10px] font-bold text-[#166534] whitespace-nowrap">
                {route.label} {route.extraMinutes > 0 ? `(+${route.extraMinutes.toFixed(1)} min)` : '(no delay)'}
              </div>
            </Marker>
          );
        })}
      </Map>
    </div>
  );
};

export default TrafficMap;
