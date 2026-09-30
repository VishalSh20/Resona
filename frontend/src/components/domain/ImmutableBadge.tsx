import { Lock } from "lucide-react";

import { cn } from "@/lib/utils";

interface ImmutableBadgeProps {
  label?: string;
  className?: string;
}

export function ImmutableBadge({
  label = "LOCKED",
  className,
}: ImmutableBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border border-amber-200 bg-amber-50 px-2 py-0.5 text-label font-medium text-amber-700",
        className,
      )}
    >
      <Lock className="size-3" aria-hidden />
      {label}
    </span>
  );
}
