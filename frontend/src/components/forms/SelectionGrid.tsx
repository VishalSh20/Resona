import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface SelectionGridProps {
  children: ReactNode;
  className?: string;
  /** Minimum card width before the grid wraps to fewer columns. */
  minWidth?: string;
}

// Responsive multi-select grid. Uses `min(100%, <min>)` so a single column can
// never force horizontal overflow on a narrow viewport.
export function SelectionGrid({
  children,
  className,
  minWidth = "200px",
}: SelectionGridProps) {
  return (
    <div
      className={cn("grid gap-2.5", className)}
      style={{
        gridTemplateColumns: `repeat(auto-fit, minmax(min(100%, ${minWidth}), 1fr))`,
      }}
    >
      {children}
    </div>
  );
}
