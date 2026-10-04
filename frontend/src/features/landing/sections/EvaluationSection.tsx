import { AnimatedBar } from "@/components/motion/AnimatedBar";
import { CountUp } from "@/components/motion/CountUp";
import { Reveal } from "@/components/motion/Reveal";
import { LANDING_COPY } from "@/features/landing/copy";
import { ILLUSTRATIVE_RUN, type EvalMetric } from "@/features/landing/data";
import { Eyebrow, SectionShell } from "@/features/landing/ui";

const { evaluation } = LANDING_COPY;

function MetricRow({ metric, delay }: { metric: EvalMetric; delay: number }) {
  return (
    <div className="flex items-center gap-4 py-1.5">
      <span className="min-w-0 flex-1 truncate text-body-sm text-foreground">
        {metric.label}
      </span>
      <span className="w-16 text-right tabular-nums text-body-sm text-muted-foreground">
        <CountUp value={metric.value} suffix={metric.suffix} />
      </span>
      <AnimatedBar
        fill={metric.fill}
        delay={delay}
        className="hidden w-28 sm:block sm:w-40"
      />
    </div>
  );
}

function EvaluationMatrix() {
  let index = 0;

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-surface">
      <div className="flex items-start justify-between gap-4 border-b border-border px-6 py-5">
        <div>
          <Eyebrow>Evaluation run</Eyebrow>
          <p className="mt-2 text-title-md font-medium text-foreground">
            {ILLUSTRATIVE_RUN.name}
            <span className="text-muted-foreground">
              {" "}
              · {ILLUSTRATIVE_RUN.sample}
            </span>
          </p>
        </div>
        <span className="font-geist-mono text-title-md text-muted-foreground/60">
          {ILLUSTRATIVE_RUN.code}
        </span>
      </div>

      <div className="space-y-8 px-6 py-7">
        {ILLUSTRATIVE_RUN.categories.map((category) => (
          <div key={category.id}>
            <p className="font-geist-mono text-micro uppercase tracking-[0.14em] text-muted-foreground">
              {category.label}
            </p>
            <div className="mt-3">
              {category.metrics.map((metric) => {
                const delay = index * 0.05;
                index += 1;
                return (
                  <MetricRow key={metric.key} metric={metric} delay={delay} />
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function EvaluationSection() {
  return (
    <SectionShell id="how-it-works">
      <div id="evaluate" className="max-w-2xl scroll-mt-24">
        <Reveal>
          <Eyebrow>{evaluation.eyebrow}</Eyebrow>
        </Reveal>
        <Reveal delay={0.05}>
          <h2 className="mt-5 font-display text-[clamp(2rem,4vw,3rem)] leading-[1.05] text-foreground">
            {evaluation.heading}
          </h2>
        </Reveal>
        <Reveal delay={0.1}>
          <p className="mt-5 text-body-lg text-muted-foreground">
            {evaluation.body}
          </p>
        </Reveal>
      </div>

      <Reveal delay={0.15} className="mt-12">
        <EvaluationMatrix />
      </Reveal>
    </SectionShell>
  );
}
