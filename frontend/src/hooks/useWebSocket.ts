import { useEffect, useRef } from 'react';
import { useFeedStore, useIncidentStore } from '../store';
import { api } from '../services/api';

const normalizeCityCode = (value: unknown): 'nyc' | 'chandigarh' | null => {
  const raw = String(value || '').trim().toLowerCase();
  if (!raw) return null;
  if (raw === 'nyc' || raw === 'new york' || raw === 'new york city' || raw === 'new_york' || raw === 'new-york') {
    return 'nyc';
  }
  if (raw === 'chandigarh' || raw === 'chd' || raw === 'tri-city' || raw === 'tricity') {
    return 'chandigarh';
  }
  return null;
};

const inferCityFromCoordinates = (lat: unknown, lng: unknown): 'nyc' | 'chandigarh' | null => {
  const latN = Number(lat);
  const lngN = Number(lng);
  if (!Number.isFinite(latN) || !Number.isFinite(lngN)) return null;
  if (latN >= 40.4 && latN <= 41.1 && lngN >= -74.35 && lngN <= -73.55) return 'nyc';
  if (latN >= 30.55 && latN <= 30.9 && lngN >= 76.65 && lngN <= 76.95) return 'chandigarh';
  return null;
};

const inferIncidentCity = (payload: any): 'nyc' | 'chandigarh' | null => {
  const explicit = normalizeCityCode(payload?.city || payload?.data?.city);
  const coord = inferCityFromCoordinates(
    payload?.location?.coordinates?.[1] ?? payload?.data?.location?.coordinates?.[1],
    payload?.location?.coordinates?.[0] ?? payload?.data?.location?.coordinates?.[0],
  );
  if (coord && explicit && coord !== explicit) return coord;
  return explicit ?? coord ?? null;
};

export const useWebSocket = () => {
  const city = useFeedStore((s) => s.city);
  const { setSegments } = useFeedStore();
  // Keep both: our updateIncidentAssignment + incoming resolveIncident
  const {
    setIncident, setLLMOutput, setDiversionRoutes, setCollisions,
    addIncident, setCongestionZone, clearCongestionZone, setCongestionRoutes,
    setIncidentRoutes, resolveIncident, updateIncidentAssignment, updateIncidentPoliceDispatch,
    updateIncidentVLMAnalysis,
  } = useIncidentStore();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    const connect = () => {
      const ws = new WebSocket(api.getWsUrl(city));
      wsRef.current = ws;

      ws.onopen = () => console.log('[WS] Connected to city:', city);

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          const currentCity = useFeedStore.getState().city;

          switch (msg.type) {
            case 'feed_update':
              setSegments(msg.data.segments);
              break;
            case 'incident_detected': {
              const incidentCity = inferIncidentCity(msg.data);
              if (incidentCity && incidentCity !== currentCity) break;
              setCollisions([]);
              setIncident({
                id: msg.data._id || msg.data.id || 'unknown',
                city: incidentCity || currentCity,
                status: msg.data.status,
                severity: msg.data.severity,
                location: {
                  lat: msg.data.location?.coordinates?.[1] ?? 0,
                  lng: msg.data.location?.coordinates?.[0] ?? 0,
                },
                on_street: msg.data.on_street,
                cross_street: msg.data.cross_street || '',
                affected_segment_ids: msg.data.affected_segment_ids || [],
                detected_at: msg.data.detected_at,
                assigned_operator: msg.data.assigned_operator || null,
                needs_ambulance: msg.data.needs_ambulance || false,
                police_dispatched: msg.data.police_dispatched || false,
                police_dispatched_by: msg.data.police_dispatched_by || null,
                police_dispatched_at: msg.data.police_dispatched_at || null,
                media_url: msg.data.media_url || undefined,
              });
              break;
            }
            case 'incident_assigned': {
              const assignCity = normalizeCityCode(msg.data.city || msg.data.data?.city);
              if (assignCity && assignCity !== currentCity) break;
              updateIncidentAssignment(msg.data.incident_id, msg.data.operator);
              break;
            }
            case 'llm_output': {
              const llmCity =
                normalizeCityCode(msg.data.city || msg.data.data?.city) ||
                useIncidentStore.getState().incidents.find((i) => i.id === msg.data.incident_id)?.city ||
                null;
              if (llmCity && llmCity !== currentCity) break;
              setLLMOutput(msg.data);
              // Only update diversion routes if new data is non-empty
              if (msg.data.diversion_geometry && msg.data.diversion_geometry.length > 0) {
                setDiversionRoutes(msg.data.diversion_geometry);
              }
              break;
            }
            case 'diversion_routes':
              console.log('[WS] Diversion routes received:', msg.data.routes?.length || 0, 'routes');
              setDiversionRoutes(msg.data.routes || []);
              break;
            case 'collisions':
              setCollisions(msg.data.collisions || []);
              break;
            case 'congestion_alert': {
              const congestionCity = normalizeCityCode(msg.data.city || msg.data.data?.city);
              if (congestionCity && congestionCity !== currentCity) break;
              console.log('[WS] Congestion alert:', msg.data.primary_street);
              setCongestionZone(msg.data);
              if (msg.data.alternate_routes && msg.data.alternate_routes.length > 0) {
                const routesWithZone = msg.data.alternate_routes.map((r: any) => ({
                  ...r,
                  _zoneId: msg.data.zone_id,
                  _type: 'congestion',
                }));
                setCongestionRoutes(routesWithZone);
              }
              break;
            }
            case 'congestion_cleared':
              console.log('[WS] Congestion cleared:', msg.data.zone_id);
              clearCongestionZone(msg.data.zone_id);
              break;
            case 'incident_routes': {
              const routeCity =
                normalizeCityCode(msg.data.city || msg.data.data?.city) ||
                useIncidentStore.getState().incidents.find((i) => i.id === msg.data.incident_id)?.city ||
                null;
              if (routeCity && routeCity !== currentCity) break;
              const routeIncidentId = msg.data.incident_id || 'unknown';
              console.log('[WS] Incident routes received for', routeIncidentId, '- blocked:',
                msg.data.blocked?.geometry?.coordinates?.length || 0, 'pts, alternate:',
                msg.data.alternate?.geometry?.coordinates?.length || 0, 'pts');
              setIncidentRoutes(
                routeIncidentId,
                msg.data.blocked,
                msg.data.alternate,
                msg.data.origin,
                msg.data.destination,
                {
                  version: msg.data.version || 'v1',
                  meta: msg.data.meta || {},
                  incident_ids: msg.data.incident_ids,
                  is_consolidated: msg.data.is_consolidated,
                  group_center: msg.data.group_center,
                },
              );
              break;
            }
            case 'incident_resolved': {
              const resolvedCity =
                normalizeCityCode(msg.data.city || msg.data.data?.city) ||
                useIncidentStore.getState().incidents.find((i) => i.id === (msg.data.incident_id || msg.data._id || ''))?.city ||
                null;
              if (resolvedCity && resolvedCity !== currentCity) break;
              const resolvedId = msg.data.incident_id || msg.data._id || 'unknown';
              console.log('[WS] Incident resolved:', resolvedId);
              resolveIncident(resolvedId);
              break;
            }
            case 'police_dispatched': {
              const eventCity =
                normalizeCityCode(msg.data.city || msg.data.data?.city) ||
                useIncidentStore.getState().incidents.find((i) => i.id === msg.data.incident_id)?.city ||
                null;
              if (eventCity && eventCity !== currentCity) break;
              updateIncidentPoliceDispatch(msg.data.incident_id, {
                police_dispatched: true,
                police_dispatched_by: msg.data.operator || null,
                police_dispatched_at: msg.data.dispatched_at || null,
              });
              break;
            }
            case 'vlm_analysis': {
              const eventCity = normalizeCityCode(msg.data.city || msg.data.data?.city) ||
                useIncidentStore.getState().incidents.find((i) => i.id === msg.data.incident_id)?.city ||
                null;
              if (eventCity && eventCity !== currentCity) break;
              updateIncidentVLMAnalysis(msg.data.incident_id, msg.data.analysis);
              break;
            }
          }
        } catch (e) {
          console.error('[WS] Parse error:', e);
        }
      };

      ws.onclose = () => {
        console.log('[WS] Disconnected, reconnecting in 3s...');
        reconnectTimer.current = setTimeout(connect, 3000);
      };

      ws.onerror = (err) => console.error('[WS] Error:', err);
    };

    connect();

    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [city, setSegments, setIncident, setLLMOutput, setDiversionRoutes, setCollisions,
      resolveIncident, updateIncidentAssignment, addIncident,
      setCongestionZone, clearCongestionZone, setCongestionRoutes, setIncidentRoutes,
      updateIncidentPoliceDispatch]);
};
