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
            const coords = data?.alternate?.geometry?.coordinates || [];
            if (!Array.isArray(coords) || coords.length < 2) return null;
            const extra = Number(
              data?.alternate?.estimated_actual_extra_minutes ??
                data?.alternate?.estimated_extra_minutes ??
                0,
            );
            return {
              incidentId,
              geometry: { type: 'LineString', coordinates: coords },
              label: data?.alternate?.label || 'SAFE ROUTE',
              extraMinutes: Number.isFinite(extra) ? extra : 0,
            } as SafeRoute;
          }),
        );
        if (!cancelled) {
          setSafeRoutes(routeResults.filter(Boolean) as SafeRoute[]);
        }
      } catch {
        if (!cancelled) setSafeRoutes([]);
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

        {/* SAFE ROUTES ONLY */}
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

        {safeRoutes.map((route) => {
          const coords = route.geometry.coordinates || [];
          const mid = coords[Math.floor(coords.length / 2)];
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
