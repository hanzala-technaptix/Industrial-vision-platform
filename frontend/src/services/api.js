const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

async function _json(path) {
  const r = await fetch(`${BASE_URL}${path}`);
  if (!r.ok) throw new Error(`GET ${path} → ${r.status}`);
  return r.json();
}

export async function fetchEvents(limit = 50, event_type) {
  const q = new URLSearchParams({ limit });
  if (event_type) q.set('event_type', event_type);
  const data = await _json(`/events?${q.toString()}`);
  return data.events || [];
}

export async function fetchStats()      { return _json('/events/stats'); }
export async function fetchHealth()     { return _json('/health'); }
export async function fetchDetectors()  { return _json('/detectors'); }
export async function fetchCameras()    { return _json('/cameras'); }

export function videoFeedUrl() {
  return `${BASE_URL}/video_feed`;
}
