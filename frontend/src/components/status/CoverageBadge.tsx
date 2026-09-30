import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { formatPercent } from "@/lib/formatters/format";

interface CoverageBadgeProps {
  ratio?: number | null;
  count?: number | null;
  total?: number | null;
}

export function CoverageBadge({ ratio, count, total }: CoverageBadgeProps) {
  const hasFraction = count != null && total != null && total > 0;
  const displayRatio = ratio ?? (hasFraction ? count / total : null);

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="inline-flex items-center gap-1.5 tabular-nums text-body-sm text-muted-foreground">
          {hasFraction ? (
            <>
              <span>
                {count}/{total}
              </span>
              <span className="text-micro">{formatPercent(displayRatio)}</span>
            </>
          ) : (
            formatPercent(displayRatio)
          )}
        </span>
      </TooltipTrigger>
      <TooltipContent>
        Coverage measures observability of the metric. It is not a quality score.
      </TooltipContent>
    </Tooltip>
  );
}
