import { motion, useReducedMotion } from "framer-motion";

import { Reveal } from "@/components/motion/Reveal";
import { LANDING_COPY } from "@/features/landing/copy";
import {
  CALL_AMBIENCE,
  PERSONAS,
  PERSONA_TRAITS,
} from "@/features/landing/data";
import { Eyebrow, SectionShell } from "@/features/landing/ui";

const { simulation } = LANDING_COPY;
const RADIUS = 160;
const ORBIT_SECONDS = 70;

function OrbitCard({
  label,
  angle,
  reduced,
}: {
  label: string;
  angle: number;
  reduced: boolean | null;
}) {
  return (
    <div
      className="absolute left-1/2 top-1/2"
      style={{
        transform: `translate(-50%, -50%) rotate(${angle}deg) translateY(-${RADIUS}px)`,
      }}
    >
      {/* Counter the per-card placement angle, then the ring rotation, so
          the label always reads upright while it orbits. */}
      <div style={{ transform: `rotate(${-angle}deg)` }}>
        <motion.div
          animate={reduced ? undefined : { rotate: -360 }}
          transition={{
            duration: ORBIT_SECONDS,
            repeat: Infinity,
            ease: "linear",
          }}
        >
          <span className="whitespace-nowrap rounded-lg border border-border bg-surface px-3 py-2 text-body-sm text-foreground shadow-sm">
            {label}
          </span>
        </motion.div>
      </div>
    </div>
  );
}

function PersonaOrbit() {
  const reduced = useReducedMotion();

  return (
    <div className="relative mx-auto hidden size-[24rem] md:block">
      <motion.div
        className="absolute inset-0"
        animate={reduced ? undefined : { rotate: 360 }}
        transition={
          reduced
            ? undefined
            : { duration: ORBIT_SECONDS, repeat: Infinity, ease: "linear" }
        }
      >
        {PERSONAS.map((persona, index) => (
          <OrbitCard
            key={persona}
            label={persona}
            angle={(index / PERSONAS.length) * 360}
            reduced={reduced}
          />
        ))}
      </motion.div>

      <div className="absolute left-1/2 top-1/2 flex size-28 -translate-x-1/2 -translate-y-1/2 flex-col items-center justify-center rounded-2xl border border-border bg-canvas">
        <span className="font-geist-mono text-micro uppercase tracking-[0.14em] text-muted-foreground">
          Caller
        </span>
      </div>
    </div>
  );
}

function Dimension({
  label,
  items,
  example,
}: {
  label: string;
  items?: readonly string[];
  example?: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <Eyebrow>{label}</Eyebrow>
      {items ? (
        <ul className="mt-3 flex flex-wrap gap-1.5">
          {items.map((item) => (
            <li
              key={item}
              className="rounded border border-border bg-canvas px-2 py-1 text-micro text-muted-foreground"
            >
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-body-sm text-muted-foreground">{example}</p>
      )}
    </div>
  );
}

export function SimulationSection() {
  return (
    <SectionShell className="border-t border-border">
      <div className="max-w-3xl">
        <Reveal>
          <Eyebrow>{simulation.eyebrow}</Eyebrow>
        </Reveal>
        <Reveal delay={0.05}>
          <p className="mt-5 text-title-lg text-foreground">{simulation.lead}</p>
        </Reveal>
        <Reveal delay={0.1}>
          <p className="mt-1 font-display text-[clamp(2rem,4vw,3rem)] italic leading-[1.05] text-foreground">
            {simulation.serif}
          </p>
        </Reveal>
        <Reveal delay={0.15}>
          <p className="mt-5 max-w-2xl text-body-lg text-muted-foreground">
            {simulation.body}
          </p>
        </Reveal>
      </div>

      <div className="mt-12 grid items-center gap-12 lg:grid-cols-2">
        <Reveal>
          <PersonaOrbit />
          <div className="mt-6 flex flex-wrap justify-center gap-2 md:hidden">
            {PERSONAS.map((persona) => (
              <span
                key={persona}
                className="rounded-lg border border-border bg-surface px-3 py-2 text-body-sm text-foreground"
              >
                {persona}
              </span>
            ))}
          </div>
        </Reveal>

        <Reveal delay={0.1}>
          <div className="flex flex-col gap-4">
            <Eyebrow>{simulation.dimensions}</Eyebrow>
            <Dimension label={simulation.personaLabel} items={PERSONAS} />
            <Dimension label={simulation.traitLabel} items={PERSONA_TRAITS} />
            <div className="grid gap-4 sm:grid-cols-2">
              <Dimension
                label={simulation.ambienceLabel}
                items={CALL_AMBIENCE}
              />
              <Dimension
                label={simulation.scenarioLabel}
                example={simulation.scenarioExample}
              />
            </div>
          </div>
        </Reveal>
      </div>
    </SectionShell>
  );
}
