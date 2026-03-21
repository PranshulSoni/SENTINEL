import { create } from 'zustand';
import type { TrafficSegment, Incident, LLMOutput, ChatMessage } from '../types';
import { api } from '../services/api';

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
  cityCenter: null,
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
    try {
      const result = await api.switchCity(city);
      set({ city, segments: [], cityCenter: result.center, baselines: {} });
      const baselineData = await api.getBaselines();
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
  incidentId: string;
  blocked: any;
  alternate: any;
  origin: number[];
  destination: number[];
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
  setIncidentRoutes: (incidentId: string, blocked: any, alternate: any, origin: number[], dest: number[]) => void;
  resolveIncident: (incidentId: string) => void;
  fetchIncidents: (city?: string) => Promise<void>;
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
        zone,
      ],
    })),
  clearCongestionZone: (zoneId) =>
    set((state) => ({
      congestionZones: state.congestionZones.filter((z: any) => z.zone_id !== zoneId),
      congestionRoutes: state.congestionRoutes.filter((r: any) => r._zoneId !== zoneId),
    })),
  setCongestionRoutes: (routes) => set({ congestionRoutes: routes }),
  setIncidentRoutes: (incidentId, blocked, alternate, origin, dest) =>
    set((state) => ({
      incidentRoutes: [
        ...state.incidentRoutes.filter((r) => r.incidentId !== incidentId),
        { incidentId, blocked, alternate, origin, destination: dest },
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
        }));
        set({ incidents: mapped });
      }
    } catch (e) {
      console.error('Failed to fetch incidents:', e);
    }
  },
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
