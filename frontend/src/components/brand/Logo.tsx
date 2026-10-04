import { BRAND } from "@/lib/constants/brand";
import { cn } from "@/lib/utils";

interface LogoProps {
  compact?: boolean;
  showTagline?: boolean;
  className?: string;
}

export function Logo({ compact = false, showTagline = false, className }: LogoProps) {
  return (
    <span className={cn("flex items-center gap-2", className)}>
      <img
        src="/icon.png"
        alt=""
        aria-hidden
        className={cn(
          "shrink-0 rounded-sm object-contain",
          compact ? "size-6" : "size-7",
        )}
      />
      <span className="flex flex-col">
        <span
          className={cn(
            "font-display leading-none",
            compact ? "text-title-md" : "text-title-lg",
          )}
        >
          {BRAND.name}
        </span>
        {showTagline && (
          <span className="mt-1 text-micro font-medium text-muted-foreground">
            {BRAND.tagline}
          </span>
        )}
      </span>
    </span>
  );
}
