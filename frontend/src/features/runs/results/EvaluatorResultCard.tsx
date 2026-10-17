import type { ReactNode } from "react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { StatusBadge } from "@/components/status/StatusBadge";
import { formatDurationMs, truncateId } from "@/lib/formatters/format";
import type { CallRunDto, JudgeRunResultDto } from "@/types/api";
import { CallRecording } from "./CallRecording";
import { ConversationTranscript } from "./ConversationTranscript";
import { MetricsGrid } from "./MetricsGrid";
import { JudgeSummary } from "./JudgeSummary";

interface EvaluatorResultCardProps {
  callRun: CallRunDto;
  judgeResult?: JudgeRunResultDto | null;
}

export function EvaluatorResultCard({
  callRun,
  judgeResult,
}: EvaluatorResultCardProps) {
  const selectedAttemptId = callRun.selected_attempt_id;

  const judgeMetrics = judgeResult?.metrics ?? [];
  const displayMetrics = judgeMetrics.length > 0 ? judgeMetrics : [];

  return (
    <div className="space-y-4 pt-2">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Info label="Status" value={<StatusBadge status={callRun.status} />} />
        <Info label="Repetition" value={callRun.repetition_no} />
        <Info label="Duration" value={formatDurationMs(callRun.duration_ms)} />
        <Info
          label="Selected attempt"
          value={
            selectedAttemptId ? truncateId(selectedAttemptId, 8, 4) : "—"
          }
        />
      </div>

      {judgeResult && <JudgeSummary result={judgeResult} />}

      <Tabs defaultValue="metrics">
        <TabsList>
          <TabsTrigger value="metrics">
            Metrics ({displayMetrics.length})
          </TabsTrigger>
          {selectedAttemptId && (
            <>
              <TabsTrigger value="recording">Recording</TabsTrigger>
              <TabsTrigger value="conversation">Conversation</TabsTrigger>
            </>
          )}
        </TabsList>
        <TabsContent value="metrics" className="mt-4">
          <MetricsGrid metrics={displayMetrics} />
        </TabsContent>
        {selectedAttemptId && (
          <>
            <TabsContent value="recording" className="mt-4">
              <CallRecording attemptId={selectedAttemptId} />
            </TabsContent>
            <TabsContent value="conversation" className="mt-4">
              <ConversationTranscript attemptId={selectedAttemptId} />
            </TabsContent>
          </>
        )}
      </Tabs>
    </div>
  );
}

function Info({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="space-y-1">
      <p className="text-label uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="text-body-sm font-medium">{value}</p>
    </div>
  );
}
