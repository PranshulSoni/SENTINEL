import { useEffect, useRef } from 'react';
import { useFeedStore, useIncidentStore } from '../store';
import { api } from '../services/api';

export const useWebSocket = () => {
  const { setSegments } = useFeedStore();
  const { setIncident, setLLMOutput, setDiversionRoutes } = useIncidentStore();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    const connect = () => {
      const ws = new WebSocket(api.getWsUrl());
      wsRef.current = ws;

      ws.onopen = () => console.log('[WS] Connected');

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          switch (msg.type) {
            case 'feed_update':
              setSegments(msg.data.segments);
              break;
            case 'incident_detected':
              setIncident({
                id: msg.data._id || msg.data.id || 'unknown',
                city: msg.data.city,
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
              });
              break;
            case 'llm_output':
              setLLMOutput(msg.data);
              if (msg.data.diversion_geometry) {
                setDiversionRoutes(msg.data.diversion_geometry);
              }
              break;
            case 'diversion_routes':
              setDiversionRoutes(msg.data.routes || []);
              break;
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
  }, [setSegments, setIncident, setLLMOutput, setDiversionRoutes]);
};
