import type { EntityId } from "./api";

export type LiveConnectionState =
  | "idle"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "closed"
  | "error";

export interface TimelineEvent {
  id: string;
  lane: string;
  startMs: number;
  endMs?: number;
  label: string;
  source?: string;
  severity?: string;
  payloadRef?: string;
}

export interface ForensicSelection {
  runId?: EntityId;
  attemptId?: EntityId;
  turnId?: EntityId;
  eventId?: EntityId;
  toolCallId?: EntityId;
  metricResultId?: EntityId;
}
