import { cn } from "@/lib/utils";

interface ScoreRingProps {
  score: number | null | undefined;
  size?: number;
  stroke?: number;
  className?: string;
}

export function ScoreRing({
  score,
  size = 96,
  stroke = 8,
  className,
}: ScoreRingProps) {
  const safeScore =
    score != null && Number.isFinite(score) ? Math.max(0, Math.min(100, score)) : null;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = safeScore != null ? circumference - (safeScore / 100) * circumference : 0;

  let colorClass = "text-muted-foreground";
  if (safeScore != null) {
    if (safeScore >= 80) colorClass = "text-green-500";
    else if (safeScore >= 60) colorClass = "text-amber-500";
    else colorClass = "text-red-500";
  }

  return (
    <div
      className={cn(
        "relative inline-flex flex-col items-center justify-center",
        className
      )}
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className={cn("-rotate-90", colorClass)}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={stroke}
          strokeOpacity={0.15}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-700"
        />
      </svg>
      <span className="absolute text-title-sm font-semibold">
        {safeScore != null ? Math.round(safeScore) : "—"}
      </span>
    </div>
  );
}
