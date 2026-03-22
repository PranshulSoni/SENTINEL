import { create } from 'zustand';
import type { TrafficSegment, Incident, LLMOutput, ChatMessage } from '../types';
import { api } from '../services/api';

// Hardcoded city centers — used for instant map snap without waiting on API
const CITY_CENTERS: Record<string, { lat: number; lng: number; zoom: number }> = {
  nyc:         { lat: 40.7549, lng: -73.984,  zoom: 14 },
  chandigarh:  { lat: 30.7333, lng: 76.7794,  zoom: 14 },
};

interface FeedState {
  city: 'nyc' | 'chandigarh';
  segments: TrafficSegment[];
  lastUpdate: string | null;
  baselines: Record<string, any>;
  cityCenter: { lat: number; lng: number; zoom: number } | null;
  setCity: (city: 'nyc' | 'chandigarh') => void;
  setSegments: (segments: TrafficSegment[]) => void;
  // Segments is typed as any[] internally to support _lastSeen tracking

  setBaselines: (baselines: Record<string, any>) => void;
  setCityCenter: (center: { lat: number; lng: number; zoom: number }) => void;
  switchCity: (city: 'nyc' | 'chandigarh') => Promise<void>;
  fetchBaselines: () => Promise<void>;
  fetchCityInfo: () => Promise<void>;
}

export const useFeedStore = create<FeedState>((set) => ({
  city: 'nyc',
  segments: [],
  lastUpdate: null,
  baselines: {},
  cityCenter: CITY_CENTERS['nyc'],
  setCity: (city) => set({ city, segments: [] }),
  setSegments: (newSegments) =>
    set((state) => {
      const now = Date.now();
      const merged = new Map<string, any>();
      for (const s of state.segments as any[]) {
        merged.set(s.link_id, s);
      }
      for (const s of newSegments) {
        merged.set(s.link_id, { ...s, _lastSeen: now });
      }
      const alive = Array.from(merged.values()).filter(
        (s: any) => !s._lastSeen || now - s._lastSeen < 15000
      );
      return { segments: alive, lastUpdate: new Date().toISOString() };
    }),
  setBaselines: (baselines) => set({ baselines }),
  setCityCenter: (cityCenter) => set({ cityCenter }),
  switchCity: async (city) => {
    // Snap map to new city immediately — no API round-trip needed
    useIncidentStore.getState().clearAllForCity();
    set({ city, segments: [], baselines: {}, cityCenter: CITY_CENTERS[city] });
    try {
      await api.switchCity(city);
      const [baselineData] = await Promise.all([
        api.getBaselines(),
        useIncidentStore.getState().fetchIncidents(city),
      ]);
      set({ baselines: baselineData.baselines });
    } catch (e) {
      console.error('Failed to switch city:', e);
    }
  },
  fetchBaselines: async () => {
    try {
      const data = await api.getBaselines();
      set({ baselines: data.baselines });
    } catch (e) {
      console.error('Failed to fetch baselines:', e);
    }
  },
  fetchCityInfo: async () => {
    try {
      const data = await api.getCity();
      set({ city: data.city, cityCenter: data.center });
    } catch (e) {
      console.error('Failed to fetch city info:', e);
    }
  },
}));

interface IncidentRoutePair {
  version?: 'v1' | 'v2' | string;
  incidentId: string;
  blocked: any;
  alternate: any;
  origin: number[];
  destination: number[];
  meta?: {
    routing_engine?: string;
    fallback_used?: boolean;
    ors_calls?: number;
    astar_score?: number;
    [key: string]: any;
  };
  // Consolidated route fields
  incident_ids?: string[];
  is_consolidated?: boolean;
  group_center?: number[];
}

interface IncidentState {
  currentIncident: Incident | null;
  llmOutput: LLMOutput | null;
  incidents: Incident[];
  diversionRoutes: any[];
  collisions: any[];
  congestionZones: any[];
  congestionRoutes: any[];
  incidentRoutes: IncidentRoutePair[];
  setIncident: (incident: Incident | null) => void;
  setLLMOutput: (output: LLMOutput | null) => void;
  addIncident: (incident: Incident) => void;
  clearIncident: () => void;
  setDiversionRoutes: (routes: any[]) => void;
  setCollisions: (collisions: any[]) => void;
  setCongestionZone: (zone: any) => void;
  clearCongestionZone: (zoneId: string) => void;
  setCongestionRoutes: (routes: any[]) => void;
  setIncidentRoutes: (
    incidentId: string,
    blocked: any,
    alternate: any,
    origin: number[],
    dest: number[],
    extras?: Partial<IncidentRoutePair>,
  ) => void;
  resolveIncident: (incidentId: string) => void;
  dismissIncident: (incidentId: string) => void;
  fetchIncidents: (city?: string) => Promise<void>;
  updateIncidentAssignment: (incidentId: string, operator: string) => void;
  clearAllForCity: () => void;   // wipe everything when city switches
}

export const useIncidentStore = create<IncidentState>((set) => ({
  currentIncident: null,
  llmOutput: null,
  incidents: [],
  diversionRoutes: [],
  collisions: [],
  congestionZones: [],
  congestionRoutes: [],
  incidentRoutes: [],
  setIncident:(incident) =>
    set((state) => ({
      currentIncident: incident,
      incidents: incident
        ? [...state.incidents.filter((i) => i.id !== incident.id), incident]
        : state.incidents,
    })),
  setLLMOutput: (output) => set({ llmOutput: output }),
  addIncident: (incident) =>
    set((state) => ({ incidents: [...state.incidents, incident] })),
  clearIncident: () => set((state) => {
    const currentId = state.currentIncident?.id;
    if (!currentId) return {};
    const remainingIncidents = state.incidents.filter((i) => i.id !== currentId);
    const remainingRoutes = state.incidentRoutes.filter((r) => r.incidentId !== currentId);
    return {
      currentIncident: remainingIncidents.length > 0 ? remainingIncidents[remainingIncidents.length - 1] : null,
      llmOutput: null,
      incidents: remainingIncidents,
      incidentRoutes: remainingRoutes,
      diversionRoutes: [],
      collisions: [],
    };
  }),
  setDiversionRoutes: (routes) => set({ diversionRoutes: routes }),
  setCollisions: (collisions) => set({ collisions }),
  setCongestionZone: (zone) =>
    set((state) => ({
      congestionZones: [
        ...state.congestionZones.filter((z: any) => z.zone_id !== zone.zone_id),
        { ...zone, _city: zone.city ?? zone._city },   // persist city on zone
      ],
    })),
  clearCongestionZone: (zoneId) =>
    set((state) => ({
      congestionZones: state.congestionZones.filter((z: any) => z.zone_id !== zoneId),
      congestionRoutes: state.congestionRoutes.filter((r: any) => r._zoneId !== zoneId),
    })),
  setCongestionRoutes: (routes) => set({ congestionRoutes: routes }),
  setIncidentRoutes: (incidentId, blocked, alternate, origin, dest, extras) =>
    set((state) => ({
      incidentRoutes: [
        ...state.incidentRoutes.filter((r) => r.incidentId !== incidentId),
        { incidentId, blocked, alternate, origin, destination: dest, ...(extras || {}) },
      ],
    })),
  resolveIncident: (incidentId) =>
    set((state) => {
      const wasCurrentIncident = state.currentIncident?.id === incidentId;
      const remainingIncidents = state.incidents.filter((i) => i.id !== incidentId);
      const remainingRoutes = state.incidentRoutes.filter((r) => r.incidentId !== incidentId);
      return {
        incidents: remainingIncidents,
        incidentRoutes: remainingRoutes,
        currentIncident: wasCurrentIncident
          ? (remainingIncidents.length > 0 ? remainingIncidents[remainingIncidents.length - 1] : null)
          : state.currentIncident,
        llmOutput: wasCurrentIncident ? null : state.llmOutput,
      };
    }),
  dismissIncident: (incidentId) =>
    set((state) => {
      const wasCurrentIncident = state.currentIncident?.id === incidentId;
      const remainingIncidents = state.incidents.filter((i) => i.id !== incidentId);
      const remainingRoutes = state.incidentRoutes.filter((r) => r.incidentId !== incidentId);
      return {
        incidents: remainingIncidents,
        incidentRoutes: remainingRoutes,
        currentIncident: wasCurrentIncident
          ? (remainingIncidents.length > 0 ? remainingIncidents[remainingIncidents.length - 1] : null)
          : state.currentIncident,
        llmOutput: wasCurrentIncident ? null : state.llmOutput,
      };
    }),
  fetchIncidents:async (city?: string) => {
    try {
      const data = await api.getIncidents(city);
      if (Array.isArray(data)) {
        const mapped: Incident[] = data.map((inc: any) => ({
          id: inc._id || inc.id || 'unknown',
          city: inc.city,
          status: inc.status,
          severity: inc.severity,
          location: {
            lat: inc.location?.coordinates?.[1] ?? 0,
            lng: inc.location?.coordinates?.[0] ?? 0,
          },
          on_street: inc.on_street,
          cross_street: inc.cross_street || '',
          affected_segment_ids: inc.affected_segment_ids || [],
          detected_at: inc.detected_at,
          assigned_operator: inc.assigned_operator || null,
        }));
        set({ incidents: mapped });
        // Load stored routes for each active incident
        const activeIncidents = mapped.filter((i: Incident) => i.status === 'active');
        const routeResults = await Promise.allSettled(
          activeIncidents.map((inc: Incident) => api.getIncidentRoutes(inc.id))
        );
        const loadedRoutes: IncidentRoutePair[] = [];
        routeResults.forEach((result, idx) => {
          if (result.status === 'fulfilled' && result.value?.blocked?.geometry?.coordinates?.length >= 2) {
            const data = result.value;
            loadedRoutes.push({
              version: data.version || 'v1',
              incidentId: activeIncidents[idx].id,
              blocked: data.blocked,
              alternate: data.alternate,
              origin: data.origin,
              destination: data.destination,
              meta: data.meta || {},
            });
          }
        });
        set({ incidentRoutes: loadedRoutes });
      }
    } catch (e) {
      console.error('Failed to fetch incidents:', e);
    }
  },
  clearAllForCity: () =>
    set({
      incidents: [],
      currentIncident: null,
      llmOutput: null,
      diversionRoutes: [],
      collisions: [],
      congestionZones: [],
      congestionRoutes: [],
      incidentRoutes: [],
    }),
  updateIncidentAssignment: (incidentId: string, operator: string) =>
    set((state) => ({
      incidents: state.incidents.map((inc) =>
        inc.id === incidentId ? { ...inc, assigned_operator: operator } : inc
      ),
      currentIncident:
        state.currentIncident?.id === incidentId
          ? { ...state.currentIncident, assigned_operator: operator }
          : state.currentIncident,
    })),
}));

interface ChatState {
  messages: ChatMessage[];
  isStreaming: boolean;
  addMessage: (message: ChatMessage) => void;
  setStreaming: (isStreaming: boolean) => void;
  clearChat: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isStreaming: false,
  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  setStreaming: (isStreaming) => set({ isStreaming }),
  clearChat: () => set({ messages: [] }),
}));

export const OPERATORS = {
  nyc: [
    'Tariq Rahimi',
    'Nasrin Ahmadzai',
    'Bilal Chaudhry',
    'Zara Siddiqui',
    'Farrukh Yusupov',
    'Layla Karimi',
  ],
  chandigarh: [
    'Arjun Mehta',
    'Priya Sharma',
    'Rohit Bhatia',
    'Ananya Kapoor',
    'Vikram Sandhu',
    'Neha Grewal',
  ],
};

interface OperatorState {
  operator: string;
  setOperator: (operator: string) => void;
}

const getInitialOperator = () => {
  try {
    const saved = localStorage.getItem('sentinel_operator_session');
    if (saved) {
      const parsed = JSON.parse(saved);
      if (parsed.operator) return parsed.operator;
    }
  } catch (e) {}
  return OPERATORS.nyc[0]; // Default fallback
};

export const useOperatorStore = create<OperatorState>((set) => ({
  operator: getInitialOperator(),
  setOperator: (operator) => {
    set({ operator });
    try {
      localStorage.setItem('sentinel_operator_session', JSON.stringify({ operator }));
    } catch (e) {}
  },
}));
