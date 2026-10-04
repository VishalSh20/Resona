import { motion } from "framer-motion";

import { Reveal } from "@/components/motion/Reveal";
import { LANDING_COPY } from "@/features/landing/copy";
import { CONVERSATION_EVENTS } from "@/features/landing/data";
import { Eyebrow, SectionShell } from "@/features/landing/ui";
import { cn } from "@/lib/utils";

const { edge } = LANDING_COPY;

function Fragment({ seed }: { seed: number }) {
  const bars = [10, 18, 26, 14, 22, 12];
  return (
    <div className="flex h-5 items-center gap-[3px]" aria-hidden>
      {bars.map((base, index) => {
        const height = ((base + seed * 7 + index * 3) % 24) + 4;
        return (
          <span
            key={index}
            className="w-[2px] rounded-full bg-foreground/25"
            style={{ height }}
          />
        );
      })}
    </div>
  );
}

export function EdgeCasesSection() {
  return (
    <SectionShell className="border-t border-border">
      <div className="max-w-2xl">
        <Reveal>
          <Eyebrow>{edge.eyebrow}</Eyebrow>
        </Reveal>
        <Reveal delay={0.05}>
          <h2 className="mt-5 font-display text-[clamp(2rem,4vw,3rem)] leading-[1.05] text-foreground">
            {edge.heading}
          </h2>
        </Reveal>
        <Reveal delay={0.1}>
          <p className="mt-5 text-body-lg text-muted-foreground">{edge.body}</p>
        </Reveal>
      </div>

      <div className="relative mt-12 max-w-2xl pl-6">
        <div
          aria-hidden
          className="absolute bottom-3 left-[7px] top-3 w-px bg-border"
        />
        <ul className="space-y-7">
          {CONVERSATION_EVENTS.map((event, index) => (
            <motion.li
              key={event.label}
              className="relative flex items-start justify-between gap-4"
              initial={{ opacity: 0.3, x: -6 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: "-45% 0px -45% 0px" }}
              transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
            >
              <span
                aria-hidden
                className={cn(
                  "absolute -left-6 top-1 size-3.5 rounded-full border-2",
                  event.state === "warn"
                    ? "border-warning bg-warning/20"
                    : "border-success bg-success/20",
                )}
              />
              <div>
                <p className="text-body text-foreground">{event.label}</p>
                {event.state === "warn" ? (
                  <span className="mt-1 inline-block font-geist-mono text-micro uppercase tracking-[0.14em] text-warning">
                    edge case
                  </span>
                ) : null}
              </div>
              <Fragment seed={index} />
            </motion.li>
          ))}
        </ul>
      </div>
    </SectionShell>
  );
}
