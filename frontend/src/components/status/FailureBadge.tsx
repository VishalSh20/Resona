import { cn } from "@/lib/utils";

const FAILURE_LABELS: Record<string, string> = {
  infrastructure: "INFRASTRUCTURE",
  provider: "PROVIDER",
  transport: "TRANSPORT",
  media: "MEDIA",
  timeout: "TIMEOUT",
  malformed_stream: "MALFORMED STREAM",
  runner_crash: "RUNNER CRASH",
  cancelled: "CANCELLED",
};

interface FailureBadgeProps {
  failureClass: string | null | undefined;
  className?: string;
}

export function FailureBadge({ failureClass, className }: FailureBadgeProps) {
  if (!failureClass) return null;

  const isCancelled = failureClass === "cancelled";
  const label =
    FAILURE_LABELS[failureClass] ?? failureClass.replace(/_/g, " ").toUpperCase();

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-label font-medium",
        isCancelled ? "text-zinc-500" : "text-red-600",
        className,
      )}
    >
      <span
        className={cn(
          "size-1.5 rounded-full",
          isCancelled ? "bg-zinc-400" : "bg-red-500",
        )}
        aria-hidden
      />
      {label}
    </span>
  );
}
