import { Navigate, Outlet, useLocation } from "react-router-dom";

import { LoadingState } from "@/components/domain/States";
import { useSession, useSessionBootstrap } from "@/features/auth/useAuth";

export function RequireAuth() {
  useSessionBootstrap();
  const session = useSession();
  const location = useLocation();

  if (session.status === "unknown") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas">
        <LoadingState label="Loading session…" />
      </div>
    );
  }

  if (session.status === "anonymous") {
    return (
      <Navigate
        to="/signin"
        replace
        state={{ from: location.pathname + location.search }}
      />
    );
  }

  return <Outlet />;
}
