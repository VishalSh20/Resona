export type StatusTone =
  | "success"
  | "warning"
  | "danger"
  | "info"
  | "neutral"
  | "muted";

// Explicit uppercase display labels. Values follow the backend's lowercase
// StrEnum wire format (e.g. "not_available"), never the human-facing casing.
const STATUS_LABELS: Record<string, string> = {
  queued: "QUEUED",
  starting: "STARTING",
  connecting: "CONNECTING",
  running: "RUNNING",
  terminating: "TERMINATING",
  terminal: "TERMINAL",
  completed: "COMPLETED",
  failed: "FAILED",
  timed_out: "TIMED OUT",
  cancelled: "CANCELLED",

  draft: "DRAFT",
  ready: "READY",
  partial: "PARTIAL",

  generated: "GENERATED",
  validating: "VALIDATING",
  validated: "VALIDATED",
  approved: "APPROVED",
  rejected: "REJECTED",
  executed: "EXECUTED",

  frozen: "FROZEN",
  retired: "RETIRED",

  computed: "COMPUTED",
  not_available: "NOT AVAILABLE",
  not_applicable: "NOT APPLICABLE",
  invalid: "INVALID",
  error: "ERROR",

  pass: "PASS",
  warning: "WARNING",
  passed: "PASSED",

  pending: "PENDING",
  succeeded: "SUCCEEDED",

  infrastructure_failed: "INFRASTRUCTURE FAILED",

  // Attempt failure classes
  infrastructure: "INFRASTRUCTURE",
  provider: "PROVIDER",
  transport: "TRANSPORT",
  media: "MEDIA",
  timeout: "TIMEOUT",
  malformed_stream: "MALFORMED STREAM",
  runner_crash: "RUNNER CRASH",

  // Composite / percentile
  complete: "COMPLETE",
  incomplete: "INCOMPLETE",
  unavailable: "UNAVAILABLE",
  insufficient_sample: "INSUFFICIENT SAMPLE",
};

const STATUS_TONES: Record<string, StatusTone> = {
  completed: "success",
  passed: "success",
  pass: "success",
  succeeded: "success",
  validated: "success",
  approved: "success",
  computed: "success",

  frozen: "info",
  ready: "info",
  running: "info",
  connecting: "info",
  starting: "info",
  validating: "info",

  queued: "neutral",
  draft: "neutral",
  generated: "neutral",
  executed: "neutral",
  terminal: "neutral",
  pending: "neutral",

  terminating: "warning",
  partial: "warning",
  warning: "warning",
  invalid: "warning",
  timed_out: "warning",

  failed: "danger",
  error: "danger",
  rejected: "danger",
  infrastructure_failed: "danger",

  cancelled: "muted",
  retired: "muted",
  not_available: "muted",
  not_applicable: "muted",

  complete: "success",
  incomplete: "warning",
  unavailable: "muted",
  insufficient_sample: "warning",

  infrastructure: "danger",
  provider: "danger",
  transport: "danger",
  media: "danger",
  timeout: "danger",
  malformed_stream: "danger",
  runner_crash: "danger",
};

function humanize(value: string): string {
  return value.replace(/_/g, " ").toUpperCase();
}

export function statusLabel(status: string | null | undefined): string {
  if (!status) return "UNKNOWN";
  return STATUS_LABELS[status] ?? humanize(status);
}

export function resolveStatusTone(
  status: string | null | undefined,
): StatusTone {
  if (!status) return "muted";
  return STATUS_TONES[status] ?? "neutral";
}
