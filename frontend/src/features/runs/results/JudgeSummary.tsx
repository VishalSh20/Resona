import { AlertCircle, CheckCircle2, Clock } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/status/StatusBadge";
import { formatPercent } from "@/lib/formatters/format";
import type { JudgeRunResultDto } from "@/types/api";

interface JudgeSummaryProps {
  result: JudgeRunResultDto;
}

export function JudgeSummary({ result }: JudgeSummaryProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-body-sm font-medium">Judge summary</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="space-y-1">
          <p className="text-label uppercase tracking-wide text-muted-foreground">
            Evidence coverage
          </p>
          <p className="text-title-sm font-semibold">
            {formatPercent(result.evidence_coverage)}
          </p>
        </div>
        <div className="space-y-1">
          <p className="text-label uppercase tracking-wide text-muted-foreground">
            Status
          </p>
          <StatusBadge status={result.status} />
        </div>
        <div className="space-y-1">
          <p className="text-label uppercase tracking-wide text-muted-foreground">
            Latency
          </p>
          <p className="flex items-center gap-1.5 text-body-sm">
            <Clock className="size-3.5 text-muted-foreground" />
            {result.latency_ms != null
              ? `${result.latency_ms.toLocaleString()} ms`
              : "—"}
          </p>
        </div>
        <div className="space-y-1">
          <p className="text-label uppercase tracking-wide text-muted-foreground">
            Rubric
          </p>
          <p className="text-body-sm">{result.rubric_version}</p>
        </div>
        {result.needs_human_review && (
          <div className="flex items-center gap-2 text-amber-700 sm:col-span-2 lg:col-span-4">
            <AlertCircle className="size-4" />
            <p className="text-body-sm font-medium">Needs human review</p>
          </div>
        )}
        {result.alignment_conflict && (
          <div className="flex items-center gap-2 text-red-700 sm:col-span-2 lg:col-span-4">
            <AlertCircle className="size-4" />
            <p className="text-body-sm font-medium">Alignment conflict detected</p>
          </div>
        )}
        {!result.needs_human_review && !result.alignment_conflict && (
          <div className="flex items-center gap-2 text-green-700 sm:col-span-2 lg:col-span-4">
            <CheckCircle2 className="size-4" />
            <p className="text-body-sm font-medium">No flags raised</p>
          </div>
        )}
        {result.flags.length > 0 && (
          <div className="sm:col-span-2 lg:col-span-4">
            <p className="text-label uppercase tracking-wide text-muted-foreground">
              Flags
            </p>
            <ul className="mt-1 flex flex-wrap gap-2">
              {result.flags.map((flag) => (
                <li
                  key={flag}
                  className="rounded-full border bg-muted px-2.5 py-0.5 text-body-sm"
                >
                  {flag}
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
