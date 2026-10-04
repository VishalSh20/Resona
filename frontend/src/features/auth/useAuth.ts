import { useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { authApi, type SignInInput, type SignUpInput } from "@/lib/api/auth";
import {
  UNAUTHORIZED_EVENT,
  clearAccessToken,
  getAccessToken,
  setAccessToken,
} from "@/lib/api/client";
import { useSessionStore } from "@/stores/sessionStore";

export function useSession() {
  return useSessionStore();
}

export function useSignIn() {
  const setUser = useSessionStore((state) => state.setUser);
  return useMutation({
    mutationFn: (input: SignInInput) => authApi.login(input),
    onSuccess: (session) => {
      setAccessToken(session.accessToken);
      setUser(session.user);
    },
  });
}

export function useSignUp() {
  const setUser = useSessionStore((state) => state.setUser);
  return useMutation({
    mutationFn: (input: SignUpInput) => authApi.register(input),
    onSuccess: (session) => {
      setAccessToken(session.accessToken);
      setUser(session.user);
    },
  });
}

export function useSignOut() {
  const queryClient = useQueryClient();
  return () => {
    clearAccessToken();
    useSessionStore.getState().markAnonymous();
    queryClient.clear();
  };
}

/**
 * Hydrates the session on boot: if a token is present, confirm it with /auth/me,
 * otherwise mark the session anonymous. Also reacts to 401s raised anywhere in
 * the API layer by dropping the session so the guard routes to sign-in.
 */
export function useSessionBootstrap() {
  const setUser = useSessionStore((state) => state.setUser);

  useEffect(() => {
    let cancelled = false;
    if (!getAccessToken()) {
      useSessionStore.getState().markAnonymous();
    } else {
      authApi
        .me()
        .then((user) => {
          if (!cancelled) setUser(user);
        })
        .catch(() => {
          if (!cancelled) {
            clearAccessToken();
            useSessionStore.getState().markAnonymous();
          }
        });
    }
    return () => {
      cancelled = true;
    };
  }, [setUser]);

  useEffect(() => {
    const onUnauthorized = () => {
      clearAccessToken();
      useSessionStore.getState().markAnonymous();
    };
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, []);
}
