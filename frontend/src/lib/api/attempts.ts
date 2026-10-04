import { http } from "./client";
import {
  toCallAttemptVM,
  toConversationVM,
  toMediaArtifactVM,
  toPaginatedEventsVM,
} from "@/lib/mappers";
import type {
  CallAttemptDto,
  ConversationDto,
  MediaArtifactDto,
  PaginatedEventsDto,
} from "@/types/api";
import type {
  CallAttemptVM,
  ConversationVM,
  MediaArtifactVM,
  PaginatedEventsVM,
} from "@/types/domain";

export interface EventFilters {
  source?: string;
  type?: string;
  from_ms?: number;
  to_ms?: number;
  limit?: number;
  offset?: number;
}

function toQuery(filters?: EventFilters): string {
  if (!filters) return "";
  const params = new URLSearchParams();
  if (filters.source) params.set("source", filters.source);
  if (filters.type) params.set("type", filters.type);
  if (filters.from_ms != null) params.set("from_ms", String(filters.from_ms));
  if (filters.to_ms != null) params.set("to_ms", String(filters.to_ms));
  if (filters.limit != null) params.set("limit", String(filters.limit));
  if (filters.offset != null) params.set("offset", String(filters.offset));
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export const attemptsApi = {
  get: (attemptId: string) =>
    http.get<CallAttemptDto>(`/call-attempts/${attemptId}`).then(toCallAttemptVM),
  getEvents: (attemptId: string, filters?: EventFilters) =>
    http
      .get<PaginatedEventsDto>(
        `/call-attempts/${attemptId}/events${toQuery(filters)}`,
      )
      .then(toPaginatedEventsVM),
  getConversation: (attemptId: string) =>
    http
      .get<ConversationDto>(`/call-attempts/${attemptId}/conversation`)
      .then(toConversationVM),
  getMedia: (attemptId: string) =>
    http
      .get<MediaArtifactDto[]>(`/call-attempts/${attemptId}/media`)
      .then((rows) => rows.map(toMediaArtifactVM)),
};

export type {
  CallAttemptVM,
  ConversationVM,
  MediaArtifactVM,
  PaginatedEventsVM,
};
