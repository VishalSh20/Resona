import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Play } from "lucide-react";

import { Button } from "@/components/ui/button";
import { mediaApi } from "@/lib/api/media";
import { formatDurationMs } from "@/lib/formatters/format";
import type { MediaArtifactVM } from "@/types/domain";

interface AudioArtifactPlayerProps {
  artifact: MediaArtifactVM;
  evidenceRange?: [number, number] | null;
}

/**
 * Plays an original/analysis media artifact via a just-in-time signed URL.
 * Playback (and the URL fetch) only starts on demand. No waveform rendering in
 * v1 — the component exposes the true clock range and can seek to an evidence
 * offset.
 */
export function AudioArtifactPlayer({
  artifact,
  evidenceRange,
}: AudioArtifactPlayerProps) {
  const [requested, setRequested] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const urlQuery = useQuery({
    queryKey: ["media-url", artifact.id],
    queryFn: () => mediaApi.getSignedUrl(artifact.id),
    enabled: requested,
    staleTime: 0,
    gcTime: 0,
  });

  const seekToEvidence = () => {
    if (audioRef.current && evidenceRange?.[0] != null) {
      audioRef.current.currentTime = evidenceRange[0] / 1000;
      void audioRef.current.play();
    }
  };

  return (
    <div className="space-y-2 rounded-lg border border-border bg-surface p-3">
      <div className="flex items-center justify-between text-body-sm">
        <span>
          <span className="font-medium capitalize">{artifact.track}</span>
          <span className="ml-2 text-micro text-muted-foreground">
            {artifact.representation} · {artifact.format ?? "?"} ·{" "}
            {artifact.sampleRate ?? "?"} Hz · {artifact.channels ?? "?"}ch
          </span>
        </span>
        <span className="font-mono text-micro text-muted-foreground">
          {formatDurationMs(artifact.durationMs)}
        </span>
      </div>

      {!requested && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => setRequested(true)}
        >
          <Play className="size-4" /> Load audio
        </Button>
      )}

      {requested && urlQuery.isLoading && (
        <p className="text-micro text-muted-foreground">Fetching signed URL…</p>
      )}
      {urlQuery.isError && (
        <p className="text-micro text-red-600">
          Could not fetch a playback URL for this artifact.
        </p>
      )}
      {urlQuery.data && (
        <div className="space-y-2">
          {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
          <audio
            ref={audioRef}
            controls
            src={urlQuery.data.url}
            className="w-full"
          />
          {evidenceRange && (
            <Button type="button" variant="outline" size="sm" onClick={seekToEvidence}>
              Seek to evidence ({(evidenceRange[0] / 1000).toFixed(3)}s)
            </Button>
          )}
        </div>
      )}

      {artifact.sha256 && (
        <p className="truncate font-mono text-micro text-muted-foreground">
          sha256 {artifact.sha256}
        </p>
      )}
    </div>
  );
}
