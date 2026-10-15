import { Check } from "lucide-react";

import { cn } from "@/lib/utils";

export interface ChipOption {
  key: string;
  label: string;
}

interface ChipGroupProps {
  options: ChipOption[];
  value: string[];
  onChange: (value: string[]) => void;
  className?: string;
}

export function ChipGroup({
  options,
  value,
  onChange,
  className,
}: ChipGroupProps) {
  const selected = new Set(value);
  const toggle = (key: string) => {
    if (selected.has(key)) {
      onChange(value.filter((item) => item !== key));
    } else {
      onChange([...value, key]);
    }
  };

  return (
    <div className={cn("flex flex-wrap gap-1.5", className)}>
      {options.map((option) => {
        const active = selected.has(option.key);
        return (
          <button
            key={option.key}
            type="button"
            aria-pressed={active}
            onClick={() => toggle(option.key)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-body-sm outline-none transition-all",
              "hover:border-foreground/40 hover:bg-surface-hover hover:text-foreground",
              "focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50",
              active
                ? "border-foreground text-foreground ring-1 ring-foreground/15"
                : "border-border bg-surface text-muted-foreground",
            )}
          >
            {active && <Check className="size-3" aria-hidden />}
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
