import { cn } from "@/lib/utils";
import {
  resolveStatusTone,
  statusLabel,
  type StatusTone,
} from "@/lib/constants/status";

const toneClasses: Record<StatusTone, string> = {
  success: "border-green-200 bg-green-50 text-green-700",
  warning: "border-amber-200 bg-amber-50 text-amber-700",
  danger: "border-red-200 bg-red-50 text-red-700",
  info: "border-blue-200 bg-blue-50 text-blue-700",
  neutral: "border-zinc-200 bg-zinc-100 text-zinc-700",
  muted: "border-zinc-200 bg-zinc-50 text-zinc-500",
};

const toneDot: Record<StatusTone, string> = {
  success: "bg-green-500",
  warning: "bg-amber-500",
  danger: "bg-red-500",
  info: "bg-blue-500",
  neutral: "bg-zinc-400",
  muted: "bg-zinc-300",
};

interface StatusBadgeProps {
  status: string | null | undefined;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const tone = resolveStatusTone(status);

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-label font-medium whitespace-nowrap",
        toneClasses[tone],
        className,
      )}
    >
      <span
        className={cn("size-1.5 rounded-full", toneDot[tone])}
        aria-hidden
      />
      {statusLabel(status)}
    </span>
  );
}
