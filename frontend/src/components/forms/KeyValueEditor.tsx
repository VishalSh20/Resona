import { Plus, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface KeyValueEditorProps {
  value: Record<string, unknown>;
  onChange: (value: Record<string, unknown>) => void;
}

function stringifyValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (value === undefined) return "";
  return JSON.stringify(value);
}

function parseValue(text: string): unknown {
  const trimmed = text.trim();
  if (trimmed === "") return "";
  try {
    return JSON.parse(trimmed);
  } catch {
    return text;
  }
}

export function KeyValueEditor({ value, onChange }: KeyValueEditorProps) {
  const entries = Object.entries(value);

  function updateKey(index: number, nextKey: string) {
    const next: Record<string, unknown> = {};
    entries.forEach(([key, entryValue], i) => {
      next[i === index ? nextKey : key] = entryValue;
    });
    onChange(next);
  }

  function updateValue(index: number, text: string) {
    const next: Record<string, unknown> = {};
    entries.forEach(([key, entryValue], i) => {
      next[key] = i === index ? parseValue(text) : entryValue;
    });
    onChange(next);
  }

  function remove(index: number) {
    const next: Record<string, unknown> = {};
    entries.forEach(([key, entryValue], i) => {
      if (i !== index) next[key] = entryValue;
    });
    onChange(next);
  }

  function add() {
    let candidate = "key";
    let suffix = 1;
    while (candidate in value) {
      candidate = `key_${suffix}`;
      suffix += 1;
    }
    onChange({ ...value, [candidate]: "" });
  }

  return (
    <div className="space-y-2">
      {entries.length === 0 && (
        <p className="text-micro text-muted-foreground">No entries.</p>
      )}
      {entries.map(([key, entryValue], index) => (
        <div key={`${key}-${index}`} className="flex items-center gap-2">
          <Input
            value={key}
            placeholder="key"
            className="w-1/3 font-mono text-mono"
            onChange={(event) => updateKey(index, event.target.value)}
          />
          <Input
            value={stringifyValue(entryValue)}
            placeholder="value"
            className="flex-1 font-mono text-mono"
            onChange={(event) => updateValue(index, event.target.value)}
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={() => remove(index)}
            aria-label="Remove entry"
          >
            <X className="size-4" />
          </Button>
        </div>
      ))}
      <Button type="button" variant="outline" size="sm" onClick={add}>
        <Plus className="size-4" /> Add entry
      </Button>
    </div>
  );
}
