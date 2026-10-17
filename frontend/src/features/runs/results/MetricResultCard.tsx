import { useState } from "react";
import { ChevronDown } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/status/StatusBadge";
import { cn } from "@/lib/utils";
import type { JudgeMetricDto } from "@/types/api";

interface MetricResultCardProps {
  metric: JudgeMetricDto;
}

export function MetricResultCard({ metric }: MetricResultCardProps) {
  const [open, setOpen] = useState(false);

  const score = typeof metric.value === "number" ? metric.value : null;
  const normalized = metric.normalized ?? null;

  return (
    <Card className="gap-0">
      <CardHeader
        className="cursor-pointer"
        onClick={() => setOpen((prev) => !prev)}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <CardTitle className="text-body-sm font-medium">
              {metric.metric_key}
            </CardTitle>
            {metric.summary && (
              <p className="text-body-sm text-muted-foreground line-clamp-2">
                {metric.summary}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "text-title-sm font-semibold tabular-nums",
                score != null && score >= 4
                  ? "text-green-600"
                  : score != null && score >= 3
                    ? "text-amber-600"
                    : "text-red-600"
              )}
            >
              {score != null ? score.toFixed(1) : "—"}
            </span>
            <ChevronDown
              className={cn(
                "size-4 text-muted-foreground transition-transform",
                open && "rotate-180"
              )}
            />
          </div>
        </div>
      </CardHeader>
      {open && (
        <CardContent className="border-t bg-muted/30">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1">
              <p className="text-label uppercase tracking-wide text-muted-foreground">
                Status
              </p>
              <StatusBadge status={metric.status} />
            </div>
            <div className="space-y-1">
              <p className="text-label uppercase tracking-wide text-muted-foreground">
                Confidence
              </p>
              <p className="text-body-sm tabular-nums">
                {metric.confidence != null
                  ? `${(metric.confidence * 100).toFixed(0)}%`
                  : "—"}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-label uppercase tracking-wide text-muted-foreground">
                Normalized
              </p>
              <p className="text-body-sm tabular-nums">
                {normalized != null ? `${normalized.toFixed(1)} / 100` : "—"}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-label uppercase tracking-wide text-muted-foreground">
                Direction
              </p>
              <p className="text-body-sm capitalize">
                {metric.direction?.replace(/_/g, " ") ?? "—"}
              </p>
            </div>
          </div>
          {metric.findings.length > 0 && (
            <div className="mt-4 space-y-2">
              <p className="text-label uppercase tracking-wide text-muted-foreground">
                Findings
              </p>
              <ul className="space-y-2">
                {metric.findings.slice(0, 3).map((finding, idx) => (
                  <li
                    key={idx}
                    className="rounded-md border bg-card p-2 text-body-sm"
                  >
                    <span
                      className={cn(
                        "mr-2 inline-flex rounded px-1.5 py-0.5 text-micro font-medium",
                        finding.severity === "critical"
                          ? "bg-red-100 text-red-700"
                          : finding.severity === "major"
                            ? "bg-amber-100 text-amber-700"
                            : "bg-blue-100 text-blue-700"
                      )}
                    >
                      {finding.severity}
                    </span>
                    {finding.explanation ?? finding.quote ?? "—"}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {metric.caveats.length > 0 && (
            <div className="mt-4 space-y-2">
              <p className="text-label uppercase tracking-wide text-muted-foreground">
                Caveats
              </p>
              <ul className="list-disc space-y-1 pl-5 text-body-sm text-muted-foreground">
                {metric.caveats.map((caveat, idx) => (
                  <li key={idx}>{caveat}</li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}
