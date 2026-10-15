import type { ReactNode } from "react";
import { Check } from "lucide-react";

import { cn } from "@/lib/utils";

interface SelectableCardProps {
  selected: boolean;
  onToggle: () => void;
  title: ReactNode;
  description?: ReactNode;
  /** Small leading adornment (provider logo, icon, language code, …). */
  leading?: ReactNode;
  /** Extra content rendered under the description (e.g. a reason). */
  footer?: ReactNode;
  disabled?: boolean;
  className?: string;
}

// Border/ring selection state: the card keeps its normal surface and is marked
// selected with a strong border + subtle ring + check icon, never a filled
// background. The whole card is a single keyboard-accessible toggle button.
export function SelectableCard({
  selected,
  onToggle,
  title,
  description,
  leading,
  footer,
  disabled,
  className,
}: SelectableCardProps) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      disabled={disabled}
      onClick={onToggle}
      className={cn(
        "group relative flex w-full items-start gap-3 rounded-lg border bg-surface p-3 text-left outline-none transition-all",
        "hover:border-foreground/40 hover:bg-surface-hover",
        "focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50",
        "disabled:pointer-events-none disabled:opacity-50",
        selected
          ? "border-foreground ring-1 ring-foreground/15"
          : "border-border",
        className,
      )}
    >
      {leading && (
        <span className="mt-0.5 flex shrink-0 items-center justify-center text-muted-foreground transition-colors group-hover:text-foreground">
          {leading}
        </span>
      )}

      <span className="min-w-0 flex-1">
        <span className="block text-body-sm font-medium text-foreground">
          {title}
        </span>
        {description && (
          <span className="mt-0.5 block text-micro text-muted-foreground">
            {description}
          </span>
        )}
        {footer && <span className="mt-1.5 block">{footer}</span>}
      </span>

      <span
        aria-hidden
        className={cn(
          "mt-0.5 flex size-4 shrink-0 items-center justify-center transition-opacity",
          selected ? "text-foreground opacity-100" : "opacity-0",
        )}
      >
        <Check className="size-4" />
      </span>
    </button>
  );
}
