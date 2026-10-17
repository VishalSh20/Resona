import { getAccessToken } from "@/lib/api/client";
import type { LiveConnectionState } from "@/types/ui";

import { nextReconnectDelay } from "./reconnect";

// Live observation feed for a run: `WS /api/v1/runs/{runId}/live?token=<jwt>`.
// The feed has no replay cursor, so callers must refetch authoritative snapshots
// on (re)connect; `onReconnect` is invoked for exactly that.
export interface RunLiveEvent {
  type: string;
  data: Record<string, unknown>;
}

export interface RunLiveHandlers {
  runId: string;
  onEvent: (event: RunLiveEvent) => void;
  onStateChange?: (state: LiveConnectionState) => void;
  onReconnect?: () => void;
}

function websocketBaseUrl(): string {
  const apiBase =
    (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api/v1";
  if (/^https?:\/\//i.test(apiBase)) {
    return apiBase.replace(/^http/i, "ws");
  }
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${apiBase}`;
}

export function connectRunLive(handlers: RunLiveHandlers): () => void {
  const { runId, onEvent, onStateChange, onReconnect } = handlers;
  let socket: WebSocket | null = null;
  let attempt = 0;
  let closed = false;
  let reconnectTimer: number | undefined;

  const setState = (state: LiveConnectionState) => onStateChange?.(state);

  const connect = () => {
    const token = getAccessToken();
    if (!token) {
      setState("closed");
      return;
    }
    setState(attempt === 0 ? "connecting" : "reconnecting");
    const url = `${websocketBaseUrl()}/runs/${runId}/live?token=${encodeURIComponent(token)}`;
    socket = new WebSocket(url);

    socket.onopen = () => {
      attempt = 0;
      setState("connected");
      onReconnect?.();
    };
    socket.onmessage = (message) => {
      try {
        onEvent(JSON.parse(message.data as string) as RunLiveEvent);
      } catch {
        // Ignore malformed frames; the REST snapshots remain authoritative.
      }
    };
    socket.onclose = (event) => {
      if (closed) {
        setState("closed");
        return;
      }
      if (event.code === 1008) {
        // Policy violation (expired/invalid token): do not spin on reconnect.
        setState("error");
        return;
      }
      setState("reconnecting");
      reconnectTimer = window.setTimeout(connect, nextReconnectDelay(attempt++));
    };
  };

  connect();

  return () => {
    closed = true;
    if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer);
    socket?.close();
    setState("closed");
  };
}
