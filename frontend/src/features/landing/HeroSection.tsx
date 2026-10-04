import { Link } from "react-router-dom";
import { ArrowRight, ChevronDown } from "lucide-react";

import PatternWaves from "@/components/backgrounds/PatternWaves/PatternWaves";
import { Button } from "@/components/ui/button";
import { LANDING_COPY } from "@/features/landing/copy";
import { LandingNav } from "@/features/landing/LandingNav";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { usePointerParallax } from "@/hooks/usePointerParallax";
import { useScrollFade } from "@/hooks/useScrollFade";

const { hero } = LANDING_COPY;

export function HeroSection() {
  const isCompact = useMediaQuery("(max-width: 767px)");
  const parallax = usePointerParallax({ range: isCompact ? 0 : 7 });
  const progress = useScrollFade(600);

  return (
    <section
      id="top"
      className="relative isolate flex min-h-[92svh] flex-col overflow-hidden bg-white"
    >
      <div className="absolute inset-0 z-0">
        <div
          className="absolute -inset-8 transition-transform duration-300 ease-out"
          style={{
            transform: `translate3d(${parallax.x}px, ${parallax.y}px, 0)`,
          }}
        >
          <PatternWaves
            preset="mesh"
            pattern="plus"
            wave="swell"
            spacing={14}
            markSize={0.8}
            depth={1}
            light={-52}
            shine={0.35}
            contrast={1.7}
            speed={0.3}
            scale={1.1}
            direction={325}
            color="#2e0066"
            backgroundColor="#ffffff"
            opacity={isCompact ? 0.8 : 1}
            fade="edges"
            fadeSize={0.45}
            intro
            interactive
          />
        </div>

        <div className="absolute inset-0 bg-[radial-gradient(62%_66%_at_50%_46%,rgba(255,255,255,0.8)_0%,rgba(255,255,255,0.56)_42%,rgba(255,255,255,0.24)_70%,rgba(255,255,255,0)_88%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(85%_75%_at_50%_46%,rgba(255,255,255,0.95),rgba(255,255,255,0.65)_55%,rgba(255,255,255,0)_82%)] md:hidden" />
        <div className="absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-white/85 to-transparent" />
        <div className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-b from-transparent to-canvas" />
      </div>

      <LandingNav />

      <div
        className="relative z-10 flex flex-1 flex-col items-center justify-center px-6 text-center"
        style={{
          opacity: 1 - progress,
          transform: `translateY(${-40 * progress}px)`,
        }}
      >
        <h1 className="font-sans text-[clamp(2.5rem,6vw,5rem)] font-semibold leading-[1.02] tracking-[-0.03em] text-foreground">
          <span className="block">
            {hero.headlinePrefix}{" "}
            <span className="font-display font-normal tracking-normal">
              {hero.headlineEmphasis}
            </span>
          </span>
          <span className="mt-1 block font-display font-normal italic">
            {hero.headlineAccent}
          </span>
        </h1>

        <p className="mt-7 max-w-xl text-body-lg text-muted-foreground">
          {hero.description}
        </p>

        <div className="mt-9 flex w-full flex-col items-stretch gap-3 sm:w-auto sm:flex-row sm:items-center">
          <Button size="lg" asChild>
            <Link to="/signup">
              {hero.primaryCta}
              <ArrowRight />
            </Link>
          </Button>
          <Button size="lg" variant="outline" asChild>
            <a href="#how-it-works">{hero.secondaryCta}</a>
          </Button>
        </div>

        <p className="mt-8 font-geist-mono text-micro tracking-[0.08em] text-muted-foreground">
          ✦ {hero.signal}
        </p>
      </div>

      <div className="relative z-10 flex justify-center pb-8">
        <a
          href="#how-it-works"
          className="inline-flex items-center gap-2 font-geist-mono text-micro uppercase tracking-[0.16em] text-foreground/70 transition-colors hover:text-foreground"
        >
          <ChevronDown className="size-3.5" aria-hidden />
          {hero.scrollHint}
        </a>
      </div>
    </section>
  );
}
