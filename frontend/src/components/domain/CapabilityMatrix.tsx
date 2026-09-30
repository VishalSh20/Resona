import {
  AFFECTED_METRICS,
  CAPABILITY_GROUPS,
  isCapabilityAvailable,
} from "@/lib/constants/capabilities";
import { metricLabel } from "@/lib/constants/metrics";

interface CapabilityMatrixProps {
  snapshot: Record<string, unknown> | null | undefined;
}

export function CapabilityMatrix({ snapshot }: CapabilityMatrixProps) {
  return (
    <div className="space-y-5">
      {CAPABILITY_GROUPS.map((group) => (
        <div key={group.key}>
          <h3 className="mb-1.5 text-label font-medium uppercase tracking-wide text-muted-foreground">
            {group.label}
          </h3>
          <div className="overflow-hidden rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40 text-left text-label text-muted-foreground">
                  <th className="px-3 py-1.5 font-medium">Capability</th>
                  <th className="px-3 py-1.5 font-medium">Available</th>
                  <th className="px-3 py-1.5 font-medium">Affected metrics</th>
                </tr>
              </thead>
              <tbody>
                {group.fields.map((field) => {
                  const available = isCapabilityAvailable(
                    snapshot,
                    group.key,
                    field.key,
                  );
                  const affected = AFFECTED_METRICS[field.key] ?? [];
                  return (
                    <tr
                      key={field.key}
                      className="border-b border-border last:border-0"
                    >
                      <td className="px-3 py-1.5">
                        <span className="font-mono text-micro">
                          {field.key}
                        </span>
                        <span className="ml-2 text-micro text-muted-foreground">
                          {field.label}
                        </span>
                      </td>
                      <td className="px-3 py-1.5">
                        <span
                          className={
                            available
                              ? "text-green-600"
                              : "text-muted-foreground"
                          }
                        >
                          {available ? "✓" : "✕"}
                        </span>
                      </td>
                      <td className="px-3 py-1.5 text-micro text-muted-foreground">
                        {affected.length > 0
                          ? affected.map((m) => metricLabel(m)).join(", ")
                          : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}
