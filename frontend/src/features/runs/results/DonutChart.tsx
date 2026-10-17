import { cn } from "@/lib/utils";

interface DonutSegment {
  label: string;
  value: number;
  color: string;
}

interface DonutChartProps {
  data: DonutSegment[];
  size?: number;
  stroke?: number;
  className?: string;
}

export function DonutChart({
  data,
  size = 160,
  stroke = 24,
  className,
}: DonutChartProps) {
  const total = data.reduce((sum, item) => sum + item.value, 0);
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  let accumulated = 0;

  return (
    <div className={cn("inline-flex flex-col items-center", className)}>
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="currentColor"
            className="text-muted"
            strokeWidth={stroke}
            opacity={0.15}
          />
          {data.map((item) => {
            const share = total > 0 ? item.value / total : 0;
            const arc = share * circumference;
            accumulated += arc;
            return (
              <circle
                key={item.label}
                cx={size / 2}
                cy={size / 2}
                r={radius}
                fill="none"
                stroke={item.color}
                strokeWidth={stroke}
                strokeDasharray={`${arc} ${circumference - arc}`}
                strokeDashoffset={-accumulated + arc}
                className="transition-all duration-700"
              />
            );
          })}
        </svg>
      </div>
      <div className="mt-3 flex flex-wrap justify-center gap-3">
        {data.map((item) => (
          <div key={item.label} className="flex items-center gap-1.5 text-body-sm">
            <span
              className="inline-block size-2.5 rounded-full"
              style={{ backgroundColor: item.color }}
            />
            <span className="text-muted-foreground">{item.label}</span>
            <span className="tabular-nums font-medium">{item.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
