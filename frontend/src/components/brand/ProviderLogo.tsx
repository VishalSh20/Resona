import { Bot } from "lucide-react";
import { siElevenlabs, siLivekit, siPipecat } from "simple-icons";

import { cn } from "@/lib/utils";

interface BrandIcon {
  title: string;
  path: string;
}

// Official brand marks from Simple Icons. Providers without a recognized mark
// (Vapi, Retell) fall back to a generic voice/agent icon rather than a fake logo.
const BRAND_ICONS: Record<string, BrandIcon> = {
  elevenlabs: siElevenlabs,
  livekit: siLivekit,
  pipecat: siPipecat,
};

interface ProviderLogoProps {
  slug?: string | null;
  className?: string;
}

export function ProviderLogo({ slug, className }: ProviderLogoProps) {
  const icon = slug ? BRAND_ICONS[slug.toLowerCase()] : undefined;

  if (!icon) {
    return (
      <Bot
        className={cn("size-5 text-muted-foreground", className)}
        aria-hidden
      />
    );
  }

  return (
    <svg
      role="img"
      viewBox="0 0 24 24"
      fill="currentColor"
      className={cn("size-5", className)}
    >
      <title>{icon.title}</title>
      <path d={icon.path} />
    </svg>
  );
}
