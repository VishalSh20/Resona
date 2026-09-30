import { Check, Copy } from "lucide-react";

import { cn } from "@/lib/utils";
import { truncateHash } from "@/lib/formatters/format";
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard";

interface HashBadgeProps {
  hash: string | null | undefined;
  className?: string;
}

export function HashBadge({ hash, className }: HashBadgeProps) {
  const { copied, copy } = useCopyToClipboard();

  if (!hash) {
    return <span className="text-micro text-muted-foreground">—</span>;
  }

  return (
    <button
      type="button"
      onClick={() => void copy(hash)}
      title="Copy hash"
      className={cn(
        "group inline-flex items-center gap-1.5 font-mono text-micro text-muted-foreground transition-colors hover:text-foreground",
        className,
      )}
    >
      <span>sha256:{truncateHash(hash)}</span>
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
