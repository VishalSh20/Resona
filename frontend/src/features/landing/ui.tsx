import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function Eyebrow({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <p
      className={cn(
        "font-geist-mono text-micro uppercase tracking-[0.14em] text-muted-foreground",
        className,
      )}
    >
      {children}
    </p>
  );
}

interface SectionShellProps {
  id?: string;
  children: ReactNode;
  className?: string;
  innerClassName?: string;
}

export function SectionShell({
  id,
  children,
  className,
  innerClassName,
}: SectionShellProps) {
  return (
    <section id={id} className={cn("relative bg-canvas", className)}>
      <div
        className={cn(
          "mx-auto max-w-5xl px-6 py-20 md:py-28",
          innerClassName,
        )}
      >
        {children}
      </div>
    </section>
  );
}
