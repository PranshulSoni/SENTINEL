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
  setSegments: (segments) =>
    set({ segments, lastUpdate: new Date().toISOString() }),
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

interface IncidentState {
  currentIncident: Incident | null;
  llmOutput: LLMOutput | null;
  incidents: Incident[];
  diversionRoutes: any[];
  collisions: any[];
  setIncident: (incident: Incident | null) => void;
  setLLMOutput: (output: LLMOutput | null) => void;
  addIncident: (incident: Incident) => void;
  clearIncident: () => void;
  setDiversionRoutes: (routes: any[]) => void;
  setCollisions: (collisions: any[]) => void;
}

export const useIncidentStore = create<IncidentState>((set) => ({
  currentIncident: null,
  llmOutput: null,
  incidents: [],
  diversionRoutes: [],
  collisions: [],
  setIncident: (incident) =>
    set((state) => ({
      currentIncident: incident,
      incidents: incident
        ? [...state.incidents.filter((i) => i.id !== incident.id), incident]
        : state.incidents,
    })),
  setLLMOutput: (output) => set({ llmOutput: output }),
  addIncident: (incident) =>
    set((state) => ({ incidents: [...state.incidents, incident] })),
  clearIncident: () => set({ currentIncident: null, llmOutput: null, diversionRoutes: [], collisions: [] }),
  setDiversionRoutes: (routes) => set({ diversionRoutes: routes }),
  setCollisions: (collisions) => set({ collisions }),
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
