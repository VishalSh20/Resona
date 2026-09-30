import { Check, Copy } from "lucide-react";

import { cn } from "@/lib/utils";
import { truncateId } from "@/lib/formatters/format";
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard";

interface CopyableIdProps {
  id: string;
  full?: boolean;
  className?: string;
}

export function CopyableId({ id, full = false, className }: CopyableIdProps) {
  const { copied, copy } = useCopyToClipboard();

  return (
    <button
      type="button"
      onClick={() => void copy(id)}
      title="Copy ID"
      className={cn(
        "group inline-flex max-w-full items-center gap-1.5 font-mono text-micro text-muted-foreground transition-colors hover:text-foreground",
        className,
      )}
    >
      <span className={cn(!full && "truncate")}>
        {full ? id : truncateId(id, 10, 4)}
      </span>
      {copied ? (
        <Check className="size-3 shrink-0 text-green-600" aria-hidden />
      ) : (
        <Copy
          className="size-3 shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
          aria-hidden
        />
      )}
    </button>
  );
}
