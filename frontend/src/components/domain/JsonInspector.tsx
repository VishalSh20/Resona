import { Button } from "@/components/ui/button";
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard";
import { cn } from "@/lib/utils";

interface JsonInspectorProps {
  value: unknown;
  label?: string;
  className?: string;
  maxHeight?: string;
}

export function JsonInspector({
  value,
  label = "payload",
  className,
  maxHeight = "24rem",
}: JsonInspectorProps) {
  const { copied, copy } = useCopyToClipboard();
  const text = JSON.stringify(value, null, 2) ?? "null";

  return (
    <div
      className={cn(
        "overflow-hidden rounded-lg border border-border bg-surface",
        className,
      )}
    >
      <div className="flex items-center justify-between border-b border-border px-3 py-1.5">
        <span className="text-micro font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </span>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-6 px-2 text-micro"
          onClick={() => void copy(text)}
        >
          {copied ? "Copied" : "Copy JSON"}
        </Button>
      </div>
      <pre
        className="overflow-auto p-3 font-mono text-mono text-foreground"
        style={{ maxHeight }}
      >
        {text}
      </pre>
    </div>
  );
}
