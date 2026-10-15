import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { StepIndicator } from "@/features/simulations/wizard/StepIndicator";

interface SimulationFormShellProps {
  title: string;
  description?: ReactNode;
  steps: readonly string[];
  current: number;
  children: ReactNode;
  nav: ReactNode;
}

// Wizard chrome: header + step indicator, a scrollable content card, and a
// sticky action bar that stays reachable however long the form gets.
export function SimulationFormShell({
  title,
  description,
  steps,
  current,
  children,
  nav,
}: SimulationFormShellProps) {
  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6">
      <header className="space-y-4">
        <div className="min-w-0">
          <h1 className="font-display text-display-md">{title}</h1>
          {description && (
            <p className="mt-1 text-body-sm text-muted-foreground">
              {description}
            </p>
          )}
        </div>
        <StepIndicator steps={steps} current={current} />
      </header>

      <Card className="min-w-0 p-5 sm:p-6">
        <div className="min-w-0">{children}</div>
      </Card>

      <div className="sticky bottom-0 z-10 -mx-2 flex flex-wrap items-center justify-between gap-3 border-t border-border bg-canvas/95 px-2 py-3 backdrop-blur">
        {nav}
      </div>
    </div>
  );
}
