const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

export async function fetchEvents(limit = 20) {
  const response = await fetch(`${BASE_URL}/events?limit=${limit}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch events: ${response.status}`);
  }
  const data = await response.json();
  return data.events || [];
}

export async function fetchHealth() {
  const response = await fetch(`${BASE_URL}/health`);
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status}`);
  }
  return response.json();
}
