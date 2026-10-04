import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useInView, useReducedMotion } from "framer-motion";
import { Check } from "lucide-react";

import { Reveal } from "@/components/motion/Reveal";
import { LANDING_COPY } from "@/features/landing/copy";
import {
  LANGUAGE_CHECKS,
  LANGUAGE_SAMPLES,
  LANGUAGES,
} from "@/features/landing/data";
import { Eyebrow, SectionShell } from "@/features/landing/ui";

const { language } = LANDING_COPY;
const CHIPS = LANGUAGES.filter((item) => item.code !== "HINGLISH");

function LanguageChip({ code, delay }: { code: string; delay: number }) {
  return (
    <motion.span
      className="rounded-md border border-border bg-canvas px-3 py-1.5 font-geist-mono text-micro tracking-[0.1em] text-muted-foreground"
      animate={{ y: [0, -6, 0] }}
      transition={{ duration: 4 + delay, repeat: Infinity, ease: "easeInOut" }}
    >
      {code}
    </motion.span>
  );
}

function HighlightedSentence({ text }: { text: string }) {
  return (
    <p className="mt-4 text-title-md leading-relaxed text-foreground">
      {text.split(" ").map((word, index) => (
        <motion.span
          key={`${word}-${index}`}
          className="inline-block"
          initial={{ opacity: 0.25 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.35, delay: index * 0.07 }}
        >
          {word}
          {index < text.split(" ").length - 1 ? "\u00A0" : ""}
        </motion.span>
      ))}
    </p>
  );
}

export function LanguageSection() {
  const [index, setIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const inView = useInView(containerRef, { margin: "-120px" });
  const reduced = useReducedMotion();

  useEffect(() => {
    if (!inView || reduced) return;
    const id = setInterval(
      () => setIndex((value) => (value + 1) % LANGUAGE_SAMPLES.length),
      3600,
    );
    return () => clearInterval(id);
  }, [inView, reduced]);

  const sample = LANGUAGE_SAMPLES[index];

  return (
    <SectionShell className="border-t border-border">
      <div className="max-w-3xl">
        <Reveal>
          <Eyebrow>{language.eyebrow}</Eyebrow>
        </Reveal>
        <Reveal delay={0.05}>
          <p className="mt-5 text-title-lg text-foreground">{language.lead}</p>
        </Reveal>
        <Reveal delay={0.1}>
          <p className="mt-1 font-display text-[clamp(2rem,4vw,3rem)] italic leading-[1.05] text-foreground">
            {language.serif}
          </p>
        </Reveal>
        <Reveal delay={0.15}>
          <h2 className="mt-6 max-w-2xl text-title-md font-medium text-muted-foreground">
            {language.heading}
          </h2>
        </Reveal>
        <Reveal delay={0.2}>
          <p className="mt-4 max-w-2xl text-body text-muted-foreground">
            {language.body}
          </p>
        </Reveal>
      </div>

      <Reveal delay={0.15} className="mt-12">
        <div
          ref={containerRef}
          className="rounded-xl border border-border bg-surface p-6 md:p-8"
        >
          <div className="grid gap-10 lg:grid-cols-2 lg:items-center">
            <div>
              <div className="hidden justify-center gap-2 md:flex">
                {CHIPS.slice(0, 4).map((chip, chipIndex) => (
                  <LanguageChip
                    key={chip.code}
                    code={chip.code}
                    delay={chipIndex * 0.4}
                  />
                ))}
              </div>

              <div className="my-5 flex justify-center">
                <AnimatePresence mode="wait">
                  <motion.div
                    key={sample.code}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -12 }}
                    transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                    className="w-full max-w-sm rounded-xl border border-border bg-canvas p-6"
                  >
                    <Eyebrow>{sample.label}</Eyebrow>
                    <HighlightedSentence text={sample.text} />
                    <p className="mt-5 inline-flex items-center gap-2 font-geist-mono text-micro uppercase tracking-[0.14em] text-foreground">
                      <span
                        aria-hidden
                        className="size-1.5 rounded-full bg-success"
                      />
                      Code-switch detected
                    </p>
                  </motion.div>
                </AnimatePresence>
              </div>

              <div className="hidden justify-center gap-2 md:flex">
                {CHIPS.slice(4).map((chip, chipIndex) => (
                  <LanguageChip
                    key={chip.code}
                    code={chip.code}
                    delay={chipIndex * 0.4}
                  />
                ))}
              </div>

              <div className="mt-6 flex flex-wrap justify-center gap-2 md:hidden">
                {LANGUAGES.map((chip) => (
                  <span
                    key={chip.code}
                    className="rounded-md border border-border bg-canvas px-3 py-1.5 font-geist-mono text-micro tracking-[0.1em] text-muted-foreground"
                  >
                    {chip.code}
                  </span>
                ))}
              </div>
            </div>

            <div>
              <Eyebrow>Language signal</Eyebrow>

              <div className="mt-4 space-y-2">
                <div className="flex items-center justify-between text-body-sm text-foreground">
                  <span>{sample.majorLabel}</span>
                  <span className="tabular-nums text-muted-foreground">
                    {Math.round(sample.majorRatio * 100)}%
                  </span>
                </div>
                <div className="flex h-2 overflow-hidden rounded-full bg-border">
                  <motion.span
                    key={`${sample.code}-major`}
                    className="h-full rounded-full bg-foreground"
                    initial={{ width: 0 }}
                    animate={{ width: `${sample.majorRatio * 100}%` }}
                    transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
                  />
                </div>
                <div className="flex items-center justify-between text-body-sm text-muted-foreground">
                  <span>{sample.minorLabel}</span>
                  <span className="tabular-nums">
                    {Math.round(sample.minorRatio * 100)}%
                  </span>
                </div>
                <div className="flex h-2 overflow-hidden rounded-full bg-border">
                  <motion.span
                    key={`${sample.code}-minor`}
                    className="h-full rounded-full bg-muted-foreground/50"
                    initial={{ width: 0 }}
                    animate={{ width: `${sample.minorRatio * 100}%` }}
                    transition={{
                      duration: 0.7,
                      delay: 0.1,
                      ease: [0.22, 1, 0.36, 1],
                    }}
                  />
                </div>
              </div>

              <ul className="mt-6 space-y-3 border-t border-border pt-5">
                {LANGUAGE_CHECKS.map((check, checkIndex) => (
                  <motion.li
                    key={`${sample.code}-${check}`}
                    className="flex items-center gap-2.5 text-body-sm text-foreground"
                    initial={{ opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.35, delay: 0.2 + checkIndex * 0.08 }}
                  >
                    <Check className="size-4 shrink-0 text-success" aria-hidden />
                    {check}
                  </motion.li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </Reveal>
    </SectionShell>
  );
}
