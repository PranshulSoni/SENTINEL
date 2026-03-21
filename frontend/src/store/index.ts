import { create } from 'zustand';
import { TrafficSegment, Incident, LLMOutput, ChatMessage } from '../types';

interface FeedState {
  city: 'nyc' | 'chandigarh';
  segments: TrafficSegment[];
  lastUpdate: string | null;
  setCity: (city: 'nyc' | 'chandigarh') => void;
  setSegments: (segments: TrafficSegment[]) => void;
}

export const useFeedStore = create<FeedState>((set) => ({
  city: 'nyc',
  segments: [],
  lastUpdate: null,
  setCity: (city) => set({ city, segments: [] }),
  setSegments: (segments) => set({ segments, lastUpdate: new Date().toISOString() }),
}));

interface IncidentState {
  currentIncident: Incident | null;
  llmOutput: LLMOutput | null;
  setIncident: (incident: Incident | null) => void;
  setLLMOutput: (output: LLMOutput | null) => void;
}

export const useIncidentStore = create<IncidentState>((set) => ({
  currentIncident: null,
  llmOutput: null,
  setIncident: (incident) => set({ currentIncident: incident }),
  setLLMOutput: (output) => set({ llmOutput: output }),
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
