import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { attemptsApi } from "@/lib/api/attempts";
import { mediaApi } from "@/lib/api/media";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatDurationMs } from "@/lib/formatters/format";
import type { MediaArtifactVM } from "@/types/domain";

interface CallRecordingProps {
  attemptId: string;
}

export function CallRecording({ attemptId }: CallRecordingProps) {
  const mediaQuery = useQuery({
    queryKey: ["attempts", attemptId, "media"],
    queryFn: () => attemptsApi.getMedia(attemptId),
    enabled: Boolean(attemptId),
  });
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const artifacts = mediaQuery.data ?? [];
  const caller = artifacts.find((a) => a.track === "caller");
  const agent = artifacts.find((a) => a.track === "agent");
  const mixed = artifacts.find((a) => a.track === "mixed");
  const selected =
    artifacts.find((a) => a.id === selectedId) ?? mixed ?? artifacts[0];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-body-sm font-medium">Call recording</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {mediaQuery.isLoading && (
          <p className="text-body-sm text-muted-foreground">Loading media…</p>
        )}
        {mediaQuery.isError && (
          <p className="text-body-sm text-red-600">Could not load media.</p>
        )}
        {!mediaQuery.isLoading && !mediaQuery.isError && artifacts.length === 0 && (
          <p className="text-body-sm text-muted-foreground">No media artifacts.</p>
        )}
        {artifacts.length > 0 && (
          <>
            <div className="flex flex-wrap gap-2">
              <TrackButton
                label="Caller"
                active={selected?.id === caller?.id}
                onClick={() => caller && setSelectedId(caller.id)}
                disabled={!caller}
              />
              <TrackButton
                label="Agent"
                active={selected?.id === agent?.id}
                onClick={() => agent && setSelectedId(agent.id)}
                disabled={!agent}
              />
              <TrackButton
                label="Mixed"
                active={selected?.id === mixed?.id}
                onClick={() => mixed && setSelectedId(mixed.id)}
                disabled={!mixed}
              />
            </div>
            {selected ? (
              <AudioPlayer key={selected.id} artifact={selected} />
            ) : (
              <p className="text-body-sm text-muted-foreground">
                Select a track to play.
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function TrackButton({
  label,
  active,
  onClick,
  disabled,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <Button
      variant={active ? "default" : "outline"}
      size="sm"
      onClick={onClick}
      disabled={disabled}
    >
      {label}
    </Button>
  );
}

function AudioPlayer({ artifact }: { artifact: MediaArtifactVM }) {
  const urlQuery = useQuery({
    queryKey: ["media-url", artifact.id],
    queryFn: () => mediaApi.getSignedUrl(artifact.id),
    staleTime: 0,
    gcTime: 0,
  });

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-body-sm">
        <span className="font-medium capitalize">{artifact.track}</span>
        <span className="text-micro text-muted-foreground">
          {artifact.format} · {artifact.sampleRate} Hz · {artifact.channels}ch ·{" "}
          {formatDurationMs(artifact.durationMs)}
        </span>
      </div>
      {urlQuery.isLoading && (
        <p className="text-body-sm text-muted-foreground">
          Fetching playback URL…
        </p>
      )}
      {urlQuery.isError && (
        <p className="text-body-sm text-red-600">
          Could not fetch playback URL.
        </p>
      )}
      {urlQuery.data && (
        // eslint-disable-next-line jsx-a11y/media-has-caption
        <audio controls src={urlQuery.data.url} className="w-full" />
      )}
    </div>
  );
}
