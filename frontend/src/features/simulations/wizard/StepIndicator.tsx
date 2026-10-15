import { Check } from "lucide-react";

import { cn } from "@/lib/utils";

interface StepIndicatorProps {
  steps: readonly string[];
  current: number;
}

export function StepIndicator({ steps, current }: StepIndicatorProps) {
  return (
    <nav aria-label="Progress">
      <ol className="hidden flex-wrap items-center gap-x-3 gap-y-2 md:flex">
        {steps.map((label, index) => {
          const done = index < current;
          const active = index === current;
          return (
            <li
              key={label}
              aria-current={active ? "step" : undefined}
              className="flex min-w-0 items-center gap-2"
            >
              <span
                className={cn(
                  "flex size-6 shrink-0 items-center justify-center rounded-full border text-micro font-medium tabular-nums transition-colors",
                  done && "border-foreground bg-foreground text-background",
                  active && "border-foreground text-foreground",
                  !done && !active && "border-border text-muted-foreground",
                )}
              >
                {done ? <Check className="size-3.5" aria-hidden /> : index + 1}
              </span>
              <span
                className={cn(
                  "whitespace-nowrap text-body-sm",
                  active ? "font-medium text-foreground" : "text-muted-foreground",
                )}
              >
                {label}
              </span>
            </li>
          );
        })}
      </ol>

      <p className="text-body-sm text-muted-foreground md:hidden">
        Step {current + 1} of {steps.length} ·{" "}
        <span className="font-medium text-foreground">{steps[current]}</span>
      </p>
    </nav>
  );
}
