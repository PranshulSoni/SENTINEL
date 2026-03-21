export interface TrafficSegment {
  link_id: string;
  link_name: string;
  speed: number;
  travel_time?: number;
  status: 'OK' | 'SLOW' | 'BLOCKED';
  lat: number;
  lng: number;
}

export interface SignalRecommendation {
  name: string;
  current_ns_green: number;
  recommended_ns_green: number;
  current_ew_green: number;
  recommended_ew_green: number;
  reasoning: string;
}

export interface DiversionRoute {
  priority: number;
  name: string;
  path: string[];
  estimated_absorption_pct: number;
  activate_condition: string;
}

export interface AlertDrafts {
  vms: string;
  radio: string;
  social_media: string;
}

export interface LLMOutput {
  signal_retiming?: {
    intersections: SignalRecommendation[];
  };
  diversions?: {
    routes: DiversionRoute[];
  };
  alerts?: AlertDrafts;
  narrative_update?: string;
  cctv_summary?: string;
  diversion_geometry?: any[];
}

export interface Incident {
  id: string;
  city: 'nyc' | 'chandigarh';
  status: 'active' | 'resolved';
  severity: 'minor' | 'major' | 'critical';
  location: {
    lat: number;
    lng: number;
  };
  on_street: string;
  cross_street: string;
  affected_segment_ids: string[];
  detected_at: string;
  assigned_operator?: string | null;
}

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
  timestamp: string;
}
