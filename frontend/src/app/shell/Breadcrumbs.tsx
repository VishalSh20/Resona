import { Fragment } from "react";
import { Link, useLocation } from "react-router-dom";
import { ChevronRight } from "lucide-react";

import { truncateId } from "@/lib/formatters/format";

const SEGMENT_LABELS: Record<string, string> = {
  simulations: "Simulations",
  benchmarks: "Benchmarks",
  agents: "Agents",
  new: "New",
  overview: "Overview",
  runs: "Runs",
  revisions: "Revisions",
  versions: "Versions",
};

export function Breadcrumbs() {
  const location = useLocation();
  const segments = location.pathname.split("/").filter(Boolean);
  const appSegments = segments[0] === "app" ? segments.slice(1) : segments;

  if (appSegments.length === 0) {
    return <span className="text-body-sm text-muted-foreground">Overview</span>;
  }

  const crumbs = appSegments.map((segment, index) => {
    const path = "/app/" + appSegments.slice(0, index + 1).join("/");
    const isLast = index === appSegments.length - 1;
    const isId = /^[a-z]+_/.test(segment);
    const label =
      SEGMENT_LABELS[segment] ?? (isId ? truncateId(segment, 6, 3) : segment);
    return { path, label, isLast };
  });

  return (
    <nav
      aria-label="Breadcrumb"
      className="flex min-w-0 items-center gap-1.5 text-body-sm"
    >
      <Link to="/app" className="text-muted-foreground hover:text-foreground">
        Home
      </Link>
      {crumbs.map((crumb) => (
        <Fragment key={crumb.path}>
          <ChevronRight
            className="size-3.5 shrink-0 text-muted-foreground"
            aria-hidden
          />
          {crumb.isLast ? (
            <span className="truncate font-medium text-foreground">
              {crumb.label}
            </span>
          ) : (
            <Link
              to={crumb.path}
              className="truncate text-muted-foreground hover:text-foreground"
            >
              {crumb.label}
            </Link>
          )}
        </Fragment>
      ))}
    </nav>
  );
}
