import { formatClockMs } from "@/lib/formatters/format";
import type { CallTurnVM, ToolCallVM } from "@/types/domain";

interface TimelineProps {
  turns: CallTurnVM[];
  tools: ToolCallVM[];
  onSeek?: (ms: number) => void;
}

interface LaneItem {
  id: string;
  startMs: number;
  endMs: number;
  label: string;
  className: string;
}

function buildLanes(turns: CallTurnVM[], tools: ToolCallVM[]) {
  const caller: LaneItem[] = [];
  const agent: LaneItem[] = [];
  for (const turn of turns) {
    const item: LaneItem = {
      id: turn.id,
      startMs: turn.startMs,
      endMs: Math.max(turn.endMs, turn.startMs + 1),
      label: `T${turn.sequenceNo}`,
      className: turn.speaker === "caller" ? "bg-teal-500/70" : "bg-blue-500/70",
    };
    (turn.speaker === "caller" ? caller : agent).push(item);
  }
  const toolItems: LaneItem[] = tools.map((tool) => ({
    id: tool.id,
    startMs: tool.startMs,
    endMs: Math.max(tool.endMs, tool.startMs + 1),
    label: `#${tool.ordinal}`,
    className: "bg-violet-500/70",
  }));
  return { caller, agent, toolItems };
}

const LANES: { key: "caller" | "agent" | "toolItems"; label: string }[] = [
  { key: "caller", label: "CALLER AUDIO" },
  { key: "agent", label: "AGENT AUDIO" },
  { key: "toolItems", label: "TOOLS" },
];

export function Timeline({ turns, tools, onSeek }: TimelineProps) {
  const lanes = buildLanes(turns, tools);
  const maxMs = Math.max(
    1,
    ...lanes.caller.map((i) => i.endMs),
    ...lanes.agent.map((i) => i.endMs),
    ...lanes.toolItems.map((i) => i.endMs),
  );

  return (
    <div className="space-y-1.5 rounded-lg border border-border bg-surface p-3">
      <div className="flex justify-between text-micro text-muted-foreground">
        <span>{formatClockMs(0)}</span>
        <span>runner monotonic</span>
        <span>{formatClockMs(maxMs)}</span>
      </div>
      {LANES.map((lane) => (
        <div key={lane.key} className="flex items-center gap-2">
          <span className="w-24 shrink-0 text-micro text-muted-foreground">
            {lane.label}
          </span>
          <div className="relative h-4 flex-1 rounded bg-muted">
            {lanes[lane.key].map((item) => (
              <button
                key={item.id}
                type="button"
                title={`${item.label} · ${formatClockMs(item.startMs)} → ${formatClockMs(item.endMs)}`}
                onClick={() => onSeek?.(item.startMs)}
                className={`absolute top-0 h-4 rounded ${item.className}`}
                style={{
                  left: `${(item.startMs / maxMs) * 100}%`,
                  width: `${Math.max(((item.endMs - item.startMs) / maxMs) * 100, 0.6)}%`,
                }}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
