// Bounded exponential backoff for the live WebSocket. The backend live feed
// has no replay cursor, so on reconnect the caller must refetch authoritative
// snapshots rather than assume it can replay missed events.
const BASE_DELAY_MS = 500;
const MAX_DELAY_MS = 10_000;

export function nextReconnectDelay(attempt: number): number {
  const exponential = Math.min(BASE_DELAY_MS * 2 ** attempt, MAX_DELAY_MS);
  const jitter = exponential * 0.2 * Math.random();
  return Math.round(exponential + jitter);
}
