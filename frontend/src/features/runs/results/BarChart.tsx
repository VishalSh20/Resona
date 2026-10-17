import { cn } from "@/lib/utils";

interface BarChartItem {
  label: string;
  value: number;
  color?: string;
}

interface BarChartProps {
  data: BarChartItem[];
  max?: number;
  className?: string;
}

export function BarChart({ data, max, className }: BarChartProps) {
  const computedMax =
    max ??
    (data.length > 0 ? Math.max(...data.map((d) => d.value), 1) : 1);

  return (
    <div className={cn("space-y-2", className)}>
      {data.map((item) => {
        const width = Math.min(100, Math.max(0, (item.value / computedMax) * 100));
        return (
          <div key={item.label} className="space-y-1">
            <div className="flex items-center justify-between text-body-sm">
              <span className="truncate pr-4">{item.label}</span>
              <span className="shrink-0 tabular-nums">{item.value.toFixed(1)}</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{
                  width: `${width}%`,
                  backgroundColor: item.color ?? "#3b82f6",
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
