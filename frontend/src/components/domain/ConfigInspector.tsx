import { formatNumber } from "@/lib/formatters/format";
import { cn } from "@/lib/utils";

interface ConfigInspectorProps {
  value: unknown;
  className?: string;
}

const ARRAY_ITEM_LABEL_KEYS = [
  "name",
  "title",
  "label",
  "role",
  "tool_name",
  "type",
  "key",
  "id",
];

// Renders a provider config bucket as readable key/value structure instead of a
// raw JSON blob. Handles arbitrarily nested objects and arrays so each adapter's
// native shape stays intact without flattening it.
export function ConfigInspector({ value, className }: ConfigInspectorProps) {
  return (
    <div className={cn("min-w-0 text-body-sm", className)}>
      <ConfigValue value={value} depth={0} />
    </div>
  );
}

function Dash() {
  return <span className="text-muted-foreground">—</span>;
}

function formatConfigNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : formatNumber(value, 3);
}

function ConfigValue({ value, depth }: { value: unknown; depth: number }) {
  if (value == null || value === "") return <Dash />;
  if (typeof value === "boolean") return <>{value ? "Yes" : "No"}</>;
  if (typeof value === "number") return <>{formatConfigNumber(value)}</>;
  if (typeof value === "string") return <ConfigText value={value} />;
  if (Array.isArray(value)) return <ConfigArray items={value} depth={depth} />;
  return <ConfigObject value={value as Record<string, unknown>} depth={depth} />;
}

function ConfigText({ value }: { value: string }) {
  if (/^(https?|wss?):\/\//.test(value)) {
    return (
      <a
        href={value}
        target="_blank"
        rel="noreferrer noopener"
        className="break-all font-mono text-micro underline decoration-border underline-offset-2 hover:decoration-foreground"
      >
        {value}
      </a>
    );
  }
  if (value.length > 160 || value.includes("\n")) {
    return (
      <p className="whitespace-pre-wrap break-words leading-relaxed">{value}</p>
    );
  }
  return <span className="break-words">{value}</span>;
}

function ConfigObject({
  value,
  depth,
}: {
  value: Record<string, unknown>;
  depth: number;
}) {
  const entries = Object.entries(value);
  if (entries.length === 0) return <Dash />;

  const list = (
    <dl className={depth === 0 ? "divide-y divide-border" : "space-y-1.5"}>
      {entries.map(([name, entry]) => (
        <div
          key={name}
          className={cn(
            "grid grid-cols-1 gap-x-4 gap-y-0.5 sm:grid-cols-[minmax(0,13rem)_minmax(0,1fr)]",
            depth === 0 && "px-3 py-2.5",
          )}
        >
          <dt className="font-mono text-micro text-muted-foreground">{name}</dt>
          <dd className="min-w-0">
            <ConfigValue value={entry} depth={depth + 1} />
          </dd>
        </div>
      ))}
    </dl>
  );

  if (depth === 0) {
    return (
      <div className="overflow-hidden rounded-lg border border-border bg-surface">
        {list}
      </div>
    );
  }
  return list;
}

function ConfigArray({ items, depth }: { items: unknown[]; depth: number }) {
  if (items.length === 0) return <Dash />;

  const allPrimitive = items.every((item) => item == null || typeof item !== "object");
  if (allPrimitive) {
    return (
      <div className="flex flex-wrap gap-1.5">
        {items.map((item, index) => (
          <span
            key={index}
            className="rounded bg-muted px-1.5 py-0.5 font-mono text-micro"
          >
            {String(item)}
          </span>
        ))}
      </div>
    );
  }

  return (
    <ol className="space-y-2">
      {items.map((item, index) => (
        <li
          key={index}
          className="rounded-md border border-border bg-surface p-3"
        >
          <ConfigArrayItem item={item} index={index} depth={depth} />
        </li>
      ))}
    </ol>
  );
}

function ConfigArrayItem({
  item,
  index,
  depth,
}: {
  item: unknown;
  index: number;
  depth: number;
}) {
  const record = item && typeof item === "object" && !Array.isArray(item)
    ? (item as Record<string, unknown>)
    : undefined;

  if (!record) {
    return (
      <div className="flex items-start gap-2">
        <span className="text-micro text-muted-foreground">#{index + 1}</span>
        <ConfigValue value={item} depth={depth + 1} />
      </div>
    );
  }

  const labelKey = ARRAY_ITEM_LABEL_KEYS.find(
    (key) => typeof record[key] === "string" && record[key],
  );
  const label = labelKey ? (record[labelKey] as string) : undefined;
  const rest = labelKey
    ? Object.fromEntries(Object.entries(record).filter(([key]) => key !== labelKey))
    : record;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-micro text-muted-foreground">#{index + 1}</span>
        {label && <span className="text-body-sm font-medium">{label}</span>}
      </div>
      {Object.keys(rest).length > 0 && (
        <ConfigObject value={rest} depth={depth + 1} />
      )}
    </div>
  );
}
