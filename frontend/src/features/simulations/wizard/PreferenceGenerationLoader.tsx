import { useEffect, useState } from "react";
import { AlertCircle, LoaderCircle, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";

const MESSAGES = [
  "Making evaluation preferences...",
  "Choosing helpful metrics...",
  "Finding relevant personas...",
  "Preparing your evaluation...",
];

const ROTATE_MS = 1200;

interface PreferenceGenerationLoaderProps {
  status: "loading" | "error";
  error: unknown;
  onRetry: () => void;
}

export function PreferenceGenerationLoader({
  status,
  error,
  onRetry,
}: PreferenceGenerationLoaderProps) {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (status !== "loading") return;
    const timer = setInterval(
      () => setIndex((current) => (current + 1) % MESSAGES.length),
      ROTATE_MS,
    );
    return () => clearInterval(timer);
  }, [status]);

  if (status === "error") {
    const message =
      error instanceof ApiError ? error.message : "The request could not be completed.";
    return (
      <div className="flex min-h-[40vh] flex-col items-center justify-center gap-3 text-center">
        <AlertCircle className="size-6 text-destructive" aria-hidden />
        <p className="text-body-sm font-medium">
          Couldn't generate evaluation preferences.
        </p>
        <p className="max-w-sm text-micro text-muted-foreground">{message}</p>
        <Button variant="outline" size="sm" onClick={onRetry}>
          Try again
        </Button>
      </div>
    );
  }

  return (
    <div
      className="flex min-h-[40vh] flex-col items-center justify-center gap-5 text-center"
      role="status"
      aria-live="polite"
    >
      <span className="relative flex items-center justify-center">
        <LoaderCircle
          className="size-7 animate-spin text-muted-foreground"
          aria-hidden
        />
        <Sparkles
          className="absolute -right-2 -top-1 size-4 text-foreground"
          aria-hidden
        />
      </span>
      <div className="relative h-6 w-full max-w-sm overflow-hidden">
        <p
          key={index}
          className="animate-in fade-in-0 slide-in-from-bottom-1 text-body-sm text-muted-foreground duration-300"
        >
          {MESSAGES[index]}
        </p>
      </div>
    </div>
  );
}
