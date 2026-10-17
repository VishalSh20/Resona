import { useQuery } from "@tanstack/react-query";

import { attemptsApi } from "@/lib/api/attempts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDurationMs } from "@/lib/formatters/format";
import { cn } from "@/lib/utils";

interface ConversationTranscriptProps {
  attemptId: string;
}

export function ConversationTranscript({
  attemptId,
}: ConversationTranscriptProps) {
  const conversationQuery = useQuery({
    queryKey: ["attempts", attemptId, "conversation"],
    queryFn: () => attemptsApi.getConversation(attemptId),
    enabled: Boolean(attemptId),
  });

  if (conversationQuery.isLoading) {
    return <p className="text-body-sm text-muted-foreground">Loading conversation…</p>;
  }
  if (conversationQuery.isError) {
    return (
      <p className="text-body-sm text-red-600">Could not load conversation.</p>
    );
  }

  const turns = conversationQuery.data?.turns ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-body-sm font-medium">Conversation</CardTitle>
      </CardHeader>
      <CardContent>
        {turns.length === 0 ? (
          <p className="text-body-sm text-muted-foreground">No transcript available.</p>
        ) : (
          <div className="space-y-3">
            {turns.map((turn) => (
              <div
                key={turn.id}
                className={cn(
                  "flex flex-col gap-1 rounded-lg border p-3",
                  turn.speaker === "caller"
                    ? "bg-blue-50/50 border-blue-100"
                    : "bg-green-50/50 border-green-100"
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <span
                    className={cn(
                      "text-micro font-semibold uppercase tracking-wide",
                      turn.speaker === "caller" ? "text-blue-700" : "text-green-700"
                    )}
                  >
                    {turn.speaker}
                  </span>
                  <span className="text-micro text-muted-foreground">
                    {formatDurationMs(turn.startMs)} — {formatDurationMs(turn.endMs)}
                  </span>
                </div>
                <p className="text-body-sm">
                  {turn.speaker === "caller"
                    ? turn.referenceText || "—"
                    : turn.observedText || "—"}
                </p>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
