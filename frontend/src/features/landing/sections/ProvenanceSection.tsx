import { motion } from "framer-motion";

import { Reveal } from "@/components/motion/Reveal";
import { LANDING_COPY } from "@/features/landing/copy";
import { PROVENANCE_NODES } from "@/features/landing/data";
import { Eyebrow, SectionShell } from "@/features/landing/ui";

const { provenance } = LANDING_COPY;

export function ProvenanceSection() {
  return (
    <SectionShell className="border-t border-border">
      <div className="max-w-2xl">
        <Reveal>
          <Eyebrow>{provenance.eyebrow}</Eyebrow>
        </Reveal>
        <Reveal delay={0.05}>
          <h2 className="mt-5 font-display text-[clamp(2rem,4vw,3rem)] leading-[1.05] text-foreground">
            {provenance.heading}
          </h2>
        </Reveal>
        <Reveal delay={0.1}>
          <p className="mt-5 text-body-lg text-muted-foreground">
            {provenance.body}
          </p>
        </Reveal>
      </div>

      <ol className="relative mt-12 max-w-xl space-y-0">
        <div
          aria-hidden
          className="absolute bottom-5 left-[7px] top-5 w-px bg-border"
        />
        {PROVENANCE_NODES.map((node, index) => (
          <motion.li
            key={node.key}
            className="relative flex items-start gap-5 pb-8 last:pb-0"
            initial={{ opacity: 0.35 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true, margin: "-35% 0px -35% 0px" }}
            transition={{ duration: 0.45, delay: index * 0.12 }}
          >
            <motion.span
              aria-hidden
              className="relative z-10 mt-1.5 size-3.5 shrink-0 rounded-full border-2 border-foreground bg-canvas"
              initial={{ backgroundColor: "#fafafa" }}
              whileInView={{ backgroundColor: "#18181b" }}
              viewport={{ once: true, margin: "-35% 0px -35% 0px" }}
              transition={{ duration: 0.3, delay: index * 0.12 + 0.1 }}
            />
            <div className="min-w-0 rounded-lg border border-border bg-surface px-4 py-3">
              <Eyebrow>{node.label}</Eyebrow>
              <p className="mt-1 text-body-sm text-foreground">{node.detail}</p>
            </div>
          </motion.li>
        ))}
      </ol>
    </SectionShell>
  );
}
