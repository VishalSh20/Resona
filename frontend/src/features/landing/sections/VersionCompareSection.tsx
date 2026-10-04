import { ArrowDown, ArrowRight, ArrowUp } from "lucide-react";

import { Reveal } from "@/components/motion/Reveal";
import { LANDING_COPY } from "@/features/landing/copy";
import { VERSION_DIFF } from "@/features/landing/data";
import { Eyebrow, SectionShell } from "@/features/landing/ui";
import { cn } from "@/lib/utils";

const { version } = LANDING_COPY;

function DiffRow({
  label,
  from,
  to,
  suffix,
  lowerIsBetter,
  delay,
}: {
  label: string;
  from: number;
  to: number;
  suffix: string;
  lowerIsBetter?: boolean;
  delay: number;
}) {
  const improved = lowerIsBetter ? to < from : to > from;
  const delta = to - from;

  return (
    <Reveal delay={delay}>
      <div className="flex items-center gap-3 border-b border-border/60 py-3 last:border-0">
        <span className="min-w-0 flex-1 truncate text-body-sm text-foreground">
          {label}
        </span>
        <span className="w-16 text-right tabular-nums text-body-sm text-muted-foreground">
          {from}
          {suffix}
        </span>
        <ArrowRight
          className="size-3.5 shrink-0 text-muted-foreground/60"
          aria-hidden
        />
        <span className="w-16 text-right tabular-nums text-body-sm font-medium text-foreground">
          {to}
          {suffix}
        </span>
        <span
          className={cn(
            "inline-flex w-16 items-center justify-end gap-0.5 text-micro tabular-nums",
            improved ? "text-success" : "text-warning",
          )}
        >
          {improved ? (
            <ArrowUp className="size-3" aria-hidden />
          ) : (
            <ArrowDown className="size-3" aria-hidden />
          )}
          {delta > 0 ? "+" : ""}
          {delta}
          {suffix}
        </span>
      </div>
    </Reveal>
  );
}

export function VersionCompareSection() {
  const { summary } = VERSION_DIFF;

  return (
    <SectionShell className="border-t border-border">
      <div className="max-w-2xl">
        <Reveal>
          <Eyebrow>{version.eyebrow}</Eyebrow>
        </Reveal>
        <Reveal delay={0.05}>
          <p className="mt-5 text-title-lg text-foreground">{version.lead}</p>
        </Reveal>
        <Reveal delay={0.1}>
          <p className="mt-1 font-display text-[clamp(2rem,4vw,3rem)] italic leading-[1.05] text-foreground">
            {version.serif}
          </p>
        </Reveal>
        <Reveal delay={0.15}>
          <p className="mt-5 text-body-lg text-muted-foreground">
            {version.body}
          </p>
        </Reveal>
      </div>

      <Reveal delay={0.15} className="mt-12">
        <div className="overflow-hidden rounded-xl border border-border bg-surface">
          <div className="flex items-center justify-between border-b border-border px-6 py-4">
            <Eyebrow>Agent version</Eyebrow>
            <div className="flex items-center gap-3 font-geist-mono text-micro tracking-[0.1em]">
              <span className="text-muted-foreground">{VERSION_DIFF.from}</span>
              <ArrowRight className="size-3.5 text-muted-foreground/60" aria-hidden />
              <span className="text-foreground">{VERSION_DIFF.to}</span>
            </div>
          </div>

          <div className="px-6 py-2">
            {VERSION_DIFF.rows.map((row, index) => (
              <DiffRow
                key={row.label}
                label={row.label}
                from={row.from}
                to={row.to}
                suffix={row.suffix}
                lowerIsBetter={row.lowerIsBetter}
                delay={0.05 + index * 0.08}
              />
            ))}
          </div>

          <div className="flex flex-col gap-2 border-t border-border px-6 py-5 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-body-sm text-foreground">
              <span className="font-medium tabular-nums">{summary.improved}</span>{" "}
              {version.summaryImproved} ·{" "}
              <span className="font-medium tabular-nums">
                {summary.regressed}
              </span>{" "}
              {version.summaryRegressed}
            </p>
            <p className="text-body-sm text-muted-foreground">
              {version.overall}{" "}
              <span className="font-medium tabular-nums text-foreground">
                {summary.overallFrom} → {summary.overallTo}
              </span>
            </p>
          </div>
        </div>
      </Reveal>
    </SectionShell>
  );
}
