import { ArrowDown } from "lucide-react";

import { Reveal } from "@/components/motion/Reveal";
import { LANDING_COPY } from "@/features/landing/copy";
import {
  COVERAGE_DIMENSIONS,
  JUDGMENT_SIGNALS,
  OBJECTIVE_SIGNALS,
} from "@/features/landing/data";
import { Eyebrow, SectionShell } from "@/features/landing/ui";

const { coverage } = LANDING_COPY;

function SignalList({
  title,
  body,
  items,
}: {
  title: string;
  body: string;
  items: readonly string[];
}) {
  return (
    <div className="rounded-xl border border-border bg-surface p-6">
      <Eyebrow>{title}</Eyebrow>
      <p className="mt-2 text-body-sm text-muted-foreground">{body}</p>
      <ul className="mt-4 flex flex-wrap gap-2">
        {items.map((item) => (
          <li
            key={item}
            className="rounded-md border border-border bg-canvas px-2.5 py-1.5 text-body-sm text-foreground"
          >
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function CoverageSection() {
  return (
    <SectionShell className="border-t border-border">
      <div className="max-w-2xl">
        <Reveal>
          <Eyebrow>{coverage.eyebrow}</Eyebrow>
        </Reveal>
        <Reveal delay={0.05}>
          <h2 className="mt-5 font-display text-[clamp(2rem,4vw,3rem)] leading-[1.05] text-foreground">
            {coverage.heading}
          </h2>
        </Reveal>
        <Reveal delay={0.1}>
          <p className="mt-5 text-body-lg text-muted-foreground">
            {coverage.body}
          </p>
        </Reveal>
      </div>

      <div className="mt-12 grid gap-8 lg:grid-cols-2">
        <Reveal>
          <div className="rounded-xl border border-border bg-surface p-6">
            <Eyebrow>{coverage.coverageLabel}</Eyebrow>

            <ul className="mt-4 grid grid-cols-2 gap-2">
              {COVERAGE_DIMENSIONS.map((dimension) => (
                <li
                  key={dimension}
                  className="rounded-lg border border-border bg-canvas px-3 py-2 text-body-sm text-foreground"
                >
                  {dimension}
                </li>
              ))}
            </ul>

            <div className="my-5 flex justify-center">
              <ArrowDown className="size-4 text-muted-foreground" aria-hidden />
            </div>

            <div className="rounded-lg border border-border bg-canvas px-4 py-3 text-center">
              <span className="font-geist-mono text-micro uppercase tracking-[0.14em] text-muted-foreground">
                {coverage.evidenceLabel}
              </span>
            </div>

            <div className="my-3 flex justify-center">
              <ArrowDown className="size-4 text-muted-foreground" aria-hidden />
            </div>

            <div className="rounded-lg bg-foreground px-4 py-3 text-center">
              <span className="font-geist-mono text-micro uppercase tracking-[0.14em] text-background">
                {coverage.confidenceLabel}
              </span>
            </div>
          </div>
        </Reveal>

        <Reveal delay={0.1}>
          <div className="flex flex-col gap-4">
            <SignalList
              title={coverage.objectiveTitle}
              body={coverage.objectiveBody}
              items={OBJECTIVE_SIGNALS}
            />
            <SignalList
              title={coverage.judgmentTitle}
              body={coverage.judgmentBody}
              items={JUDGMENT_SIGNALS}
            />
          </div>
        </Reveal>
      </div>
    </SectionShell>
  );
}
