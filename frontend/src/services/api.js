const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

async function _json(path, options) {
  const r = await fetch(`${BASE_URL}${path}`, options);
  if (!r.ok) {
    let detail = `GET ${path} → ${r.status}`;
    try {
      const body = await r.json();
      detail = body.detail || detail;
    } catch {
      /* keep status text */
    }
    throw new Error(detail);
  }
  return r.json();
}

export async function fetchEvents(limit = 50, event_type) {
  const q = new URLSearchParams({ limit });
  if (event_type) q.set('event_type', event_type);
  const data = await _json(`/events?${q.toString()}`);
  return data.events || [];
}

export async function fetchStats() { return _json('/events/stats'); }
export async function fetchHealth() { return _json('/health'); }
export async function fetchDetectors() { return _json('/detectors'); }
export async function fetchUseCases() { return _json('/use_cases'); }

export async function switchUseCase(id, source) {
  return _json(`/use_cases/${id}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(source ? { source } : {}),
  });
}

export function videoFeedUrl(token = 0) {
  return `${BASE_URL}/video_feed?t=${token}`;
}

