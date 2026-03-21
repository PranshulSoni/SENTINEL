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
  reportIncident: (report: { title: string; city: string; location_str: string; description: string }) =>
    fetch(`${API_BASE}/api/incidents/report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(report),
    }).then((r) => r.json()),
    
  getIncidents: (city?: string, status?: string) => {
    const params = new URLSearchParams();
    if (city) params.set('city', city);
    if (status) params.set('status', status);
    return fetch(`${API_BASE}/api/incidents?${params}`).then((r) => r.json());
  },

  getIncident: (id: string) =>
    fetch(`${API_BASE}/api/incidents/${id}`).then((r) => r.json()),

  resolveIncident: (id: string) =>
    fetch(`${API_BASE}/api/incidents/${id}/resolve`, { method: 'POST' }).then(
      (r) => r.json(),
    ),

  getLLMOutput: (id: string) =>
    fetch(`${API_BASE}/api/incidents/${id}/llm-output`).then((r) => r.json()),

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

  // WebSocket URL
  getWsUrl: () => {
    if (import.meta.env.VITE_API_URL) {
      return import.meta.env.VITE_API_URL.replace(/^http/, 'ws') + '/ws';
    }
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${window.location.host}/ws`;
  },
};
