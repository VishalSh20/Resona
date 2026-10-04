import { Reveal } from "@/components/motion/Reveal";
import { ProviderLogo } from "@/components/brand/ProviderLogo";
import { LANDING_COPY } from "@/features/landing/copy";
import { PROVIDERS } from "@/features/landing/data";
import { Eyebrow, SectionShell } from "@/features/landing/ui";

const { providers } = LANDING_COPY;

export function ProvidersSection() {
  return (
    <SectionShell className="border-t border-border">
      <div className="max-w-2xl">
        <Reveal>
          <Eyebrow>{providers.eyebrow}</Eyebrow>
        </Reveal>
        <Reveal delay={0.05}>
          <h2 className="mt-5 font-display text-[clamp(2rem,4vw,3rem)] leading-[1.05] text-foreground">
            {providers.heading}
          </h2>
        </Reveal>
        <Reveal delay={0.1}>
          <p className="mt-5 text-body-lg text-muted-foreground">
            {providers.body}
          </p>
        </Reveal>
      </div>

      <Reveal delay={0.15}>
        <div className="mt-10 flex flex-wrap items-center gap-x-10 gap-y-6">
          {PROVIDERS.map((provider) => (
            <div
              key={provider.slug}
              className="flex items-center gap-2.5 text-muted-foreground transition-colors hover:text-foreground"
            >
              <ProviderLogo slug={provider.slug} className="size-6" />
              <span className="text-title-sm font-medium">{provider.name}</span>
            </div>
          ))}
        </div>
      </Reveal>
    </SectionShell>
  );
}
