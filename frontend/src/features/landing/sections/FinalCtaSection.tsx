import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

import { Reveal } from "@/components/motion/Reveal";
import { Button } from "@/components/ui/button";
import { LANDING_COPY } from "@/features/landing/copy";
import { SectionShell } from "@/features/landing/ui";

const { cta } = LANDING_COPY;

export function FinalCtaSection() {
  return (
    <SectionShell className="border-t border-border">
      <div className="mx-auto max-w-2xl text-center">
        <Reveal>
          <p className="text-title-lg text-foreground">{cta.lead}</p>
        </Reveal>
        <Reveal delay={0.05}>
          <p className="mt-1 font-display text-[clamp(2.5rem,6vw,4.5rem)] italic leading-[1.02] text-foreground">
            {cta.serif}
          </p>
        </Reveal>
        <Reveal delay={0.1}>
          <p className="mt-6 text-body-lg text-muted-foreground">{cta.body}</p>
        </Reveal>
        <Reveal delay={0.15}>
          <div className="mt-8 flex justify-center">
            <Button size="lg" asChild>
              <Link to="/signup">
                {cta.cta}
                <ArrowRight />
              </Link>
            </Button>
          </div>
        </Reveal>
      </div>
    </SectionShell>
  );
}
