import { create } from "zustand";

import type { AuthUserVM } from "@/lib/mappers";

export type SessionStatus = "unknown" | "authenticated" | "anonymous";

interface SessionState {
  user: AuthUserVM | null;
  status: SessionStatus;
  setUser: (user: AuthUserVM | null) => void;
  markAnonymous: () => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  user: null,
  status: "unknown",
  setUser: (user) =>
    set({ user, status: user ? "authenticated" : "anonymous" }),
  markAnonymous: () => set({ user: null, status: "anonymous" }),
}));
