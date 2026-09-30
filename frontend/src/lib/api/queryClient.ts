import { QueryClient } from "@tanstack/react-query";

// Defaults follow the frontend implementation map: normal configuration data is
// fresh for 30s, reads retry twice, mutations never retry implicitly. Live pages
// override staleTime/refetch behaviour per-query and rely on the WebSocket feed.
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 2,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 0,
    },
  },
});
