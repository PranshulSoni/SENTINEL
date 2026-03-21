const API_BASE = import.meta.env.VITE_API_URL || '';

export const api = {
  // Feed
  getCurrentSegments: () =>
    fetch(`${API_BASE}/api/feed/current`).then((r) => r.json()),

  getCity: () =>
    fetch(`${API_BASE}/api/feed/city`).then((r) => r.json()),

  switchCity: (city: string) =>
    fetch(`${API_BASE}/api/feed/city/switch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ city }),
    }).then((r) => r.json()),

  getBaselines: () =>
    fetch(`${API_BASE}/api/feed/baselines`).then((r) => r.json()),

  // Incidents
  getIncidents: (city?: string, status: string = 'active') => {
    const params = new URLSearchParams();
    params.set('status', status);
    if (city) params.set('city', city);
    return fetch(`${API_BASE}/api/incidents?${params}`).then((r) => r.json());
  },

  getIncident: (id: string) =>
    fetch(`${API_BASE}/api/incidents/${id}`).then((r) => r.json()),

  resolveIncident: (id: string, operator: string) =>
    fetch(`${API_BASE}/api/incidents/${id}/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ operator }),
    }).then((r) => r.json()),

  dismissIncident: (id: string, operator: string) =>
    fetch(`${API_BASE}/api/incidents/${id}/dismiss`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ operator }),
    }).then((r) => r.json()),

  getLLMOutput:(id: string) =>
    fetch(`${API_BASE}/api/incidents/${id}/llm-output`).then((r) => r.json()),

  getIncidentRoutes: async (incidentId: string) => {
    const res = await fetch(`${API_BASE}/api/incidents/${incidentId}/routes`);
    if (!res.ok) return null;
    return res.json();
  },

  // Collisions
  getNearbyCollisions: (lat: number, lng: number, radius?: number) => {
    const params = new URLSearchParams({
      lat: String(lat),
      lng: String(lng),
    });
    if (radius) params.set('radius_deg', String(radius));
    return fetch(`${API_BASE}/api/collisions/nearby?${params}`).then((r) =>
      r.json(),
    );
  },

  getCollisionContext: (lat: number, lng: number) => {
    const params = new URLSearchParams({
      lat: String(lat),
      lng: String(lng),
    });
    return fetch(`${API_BASE}/api/collisions/context?${params}`).then((r) =>
      r.json(),
    );
  },

  // Chat — real backend endpoint
  sendChat: async (message: string, incidentId?: string, extra?: Record<string, unknown>) => {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, incident_id: incidentId || null, ...extra }),
    });
    if (!res.ok) throw new Error(`Chat failed: ${res.status}`);
    return res.json();
  },

  getChatHistory: (incidentId: string) =>
    fetch(`${API_BASE}/api/chat/history/${incidentId}`).then((r) => r.json()),

  clearChatHistory: (incidentId: string) =>
    fetch(`${API_BASE}/api/chat/history/${incidentId}`, { method: 'DELETE' }).then((r) => r.json()),

  // LLM
  regenerateLLM: (incidentId: string) =>
    fetch(`${API_BASE}/api/llm/regenerate/${incidentId}`, { method: 'POST' }).then((r) => r.json()),

  // Demo injection
  injectIncident: (params: {
    city?: string;
    severity?: 'minor' | 'major' | 'critical';
    street_name?: string;
    cross_street?: string;
    lat?: number;
    lng?: number;
  }) =>
    fetch(`${API_BASE}/api/demo/inject-incident`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    }).then((r) => r.json()),

  getCongestionZones: (city: string = 'nyc') =>
    fetch(`${API_BASE}/api/congestion/zones/default?city=${city}`).then((r) => r.json()),

  getDemoStreets: (city: string = 'nyc') =>
    fetch(`${API_BASE}/api/demo/streets?city=${city}`).then((r) => r.json()),

  // WebSocket URL
  getWsUrl: () => {
    if (import.meta.env.VITE_API_URL) {
      return import.meta.env.VITE_API_URL.replace(/^http/, 'ws') + '/ws';
    }
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${window.location.host}/ws`;
  },
};
