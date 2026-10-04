import { create } from "zustand";

// Transient UI selection for the forensic viewer. Authoritative server objects
// are never copied here (docs/frontend/00 §7).
interface ForensicUiState {
  selectedAttemptId: string | null;
  selectedTurnId: string | null;
  selectedEventId: string | null;
  selectedToolCallId: string | null;
  eventSourceFilter: string | null;
  select: (selection: {
    attemptId?: string | null;
    turnId?: string | null;
    eventId?: string | null;
    toolCallId?: string | null;
  }) => void;
  setEventSourceFilter: (source: string | null) => void;
  reset: () => void;
}

export const useForensicUiStore = create<ForensicUiState>((set) => ({
  selectedAttemptId: null,
  selectedTurnId: null,
  selectedEventId: null,
  selectedToolCallId: null,
  eventSourceFilter: null,
  select: (selection) =>
    set((state) => ({
      selectedAttemptId:
        selection.attemptId !== undefined
          ? selection.attemptId
          : state.selectedAttemptId,
      selectedTurnId:
        selection.turnId !== undefined ? selection.turnId : state.selectedTurnId,
      selectedEventId:
        selection.eventId !== undefined ? selection.eventId : state.selectedEventId,
      selectedToolCallId:
        selection.toolCallId !== undefined
          ? selection.toolCallId
          : state.selectedToolCallId,
    })),
  setEventSourceFilter: (source) => set({ eventSourceFilter: source }),
  reset: () =>
    set({
      selectedAttemptId: null,
      selectedTurnId: null,
      selectedEventId: null,
      selectedToolCallId: null,
      eventSourceFilter: null,
    }),
}));
