import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface MetaItem {
  label: string;
  value: ReactNode;
}

interface MetaListProps {
  items: MetaItem[];
  className?: string;
}

export function MetaList({ items, className }: MetaListProps) {
  return (
    <dl
      className={cn(
        "grid gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-3",
        className,
      )}
    >
      {items.map((item) => (
        <div key={item.label} className="min-w-0">
          <dt className="text-label uppercase tracking-wide text-muted-foreground">
            {item.label}
          </dt>
          <dd className="mt-0.5 text-body-sm">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
