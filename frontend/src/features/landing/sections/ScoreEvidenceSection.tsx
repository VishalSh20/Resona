import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Check, ChevronDown } from "lucide-react";

import { Reveal } from "@/components/motion/Reveal";
import { LANDING_COPY } from "@/features/landing/copy";
import { Eyebrow, SectionShell } from "@/features/landing/ui";

const { score } = LANDING_COPY;

// Deterministic waveform shape (illustrative audio).
const WAVE = [
  4, 9, 14, 20, 26, 18, 11, 7, 5, 10, 17, 23, 29, 22, 15, 9, 6, 12, 19, 25, 31,
  24, 16, 10, 7, 13, 21, 27, 33, 25, 17, 11, 8, 14, 22, 28, 20, 13, 9, 6,
];

function Waveform() {
  return (
    <div className="flex h-10 items-center gap-[3px]" aria-hidden>
      {WAVE.map((value, index) => (
        <motion.span
          key={index}
          className="w-[2px] shrink-0 rounded-full bg-foreground/60"
          initial={{ height: 0 }}
          animate={{ height: (value / 33) * 40 }}
          transition={{ duration: 0.4, delay: index * 0.012, ease: "easeOut" }}
        />
      ))}
    </div>
  );
}

function EvidenceCard() {
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-surface">
      <div className="flex items-center justify-between border-b border-border px-6 py-4">
        <span className="font-geist-mono text-micro uppercase tracking-[0.14em] text-muted-foreground">
          {score.callLabel}
        </span>
      </div>

      <div className="space-y-5 px-6 py-6">
        <div>
          <p className="font-geist-mono text-micro uppercase tracking-[0.14em] text-muted-foreground">
            {score.callerLabel}
          </p>
          <p className="mt-1 text-body text-foreground">{score.callerLine}</p>
        </div>
        <div>
          <p className="font-geist-mono text-micro uppercase tracking-[0.14em] text-muted-foreground">
            {score.agentLabel}
          </p>
          <p className="mt-1 text-body text-foreground">{score.agentLine}</p>
        </div>

        <div>
          <p className="font-geist-mono text-micro uppercase tracking-[0.14em] text-muted-foreground">
            {score.audioLabel}
          </p>
          <div className="mt-2">
            <Waveform />
          </div>
        </div>

        <div className="flex items-center justify-between border-t border-border pt-5">
          <span className="font-geist-mono text-micro uppercase tracking-[0.14em] text-muted-foreground">
            {score.evaluationLabel}
          </span>
          <span className="text-body-sm text-foreground">
            {score.metricName}{" "}
            <span className="font-medium tabular-nums">{score.metricValue}%</span>
          </span>
        </div>

        <div>
          <p className="font-geist-mono text-micro uppercase tracking-[0.14em] text-muted-foreground">
            {score.reasoningLabel}
          </p>
          <p className="mt-1 text-body-sm text-muted-foreground">
            {score.reasoning}
          </p>
        </div>
      </div>
    </div>
  );
}

export function ScoreEvidenceSection() {
  const [open, setOpen] = useState(false);

  return (
    <SectionShell id="evidence">
      <div className="max-w-2xl">
        <Reveal>
          <Eyebrow>{score.eyebrow}</Eyebrow>
        </Reveal>
        <Reveal delay={0.05}>
          <h2 className="mt-5 font-display text-[clamp(2rem,4vw,3rem)] leading-[1.05] text-foreground">
            {score.heading}
          </h2>
        </Reveal>
        <Reveal delay={0.1}>
          <p className="mt-5 text-body-lg text-muted-foreground">{score.body}</p>
        </Reveal>
      </div>

      <div className="mt-12 grid gap-6 md:grid-cols-2 md:items-start">
        <Reveal>
          <div className="rounded-xl border border-border bg-surface p-6">
            <Eyebrow>{score.metricName}</Eyebrow>
            <p className="mt-3 font-display text-[clamp(3rem,7vw,4.5rem)] leading-none text-foreground">
              {score.metricValue}%
            </p>

            <ul className="mt-6 space-y-3">
              {score.checks.map((check) => (
                <li
                  key={check}
                  className="flex items-start gap-2.5 text-body-sm text-foreground"
                >
                  <Check className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
                  {check}
                </li>
              ))}
            </ul>

            <button
              type="button"
              onClick={() => setOpen((value) => !value)}
              aria-expanded={open}
              aria-controls="score-evidence-panel"
              className="mt-7 inline-flex items-center gap-2 font-geist-mono text-micro uppercase tracking-[0.14em] text-foreground transition-colors hover:text-muted-foreground"
            >
              {open ? "Hide evidence" : score.viewEvidence}
              {open ? (
                <ChevronDown className="size-3.5" aria-hidden />
              ) : (
                <ArrowRight className="size-3.5" aria-hidden />
              )}
            </button>
          </div>
        </Reveal>

        <AnimatePresence initial={false}>
          {open && (
            <motion.div
              id="score-evidence-panel"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 8 }}
              transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
            >
              <EvidenceCard />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </SectionShell>
  );
}
