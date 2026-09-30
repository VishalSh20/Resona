export interface AdapterOption {
  name: string;
  version: string;
  label: string;
}

// Mirrors the backend AdapterRegistry v1 seeds. WebRTC remains interface-only.
export const ADAPTER_OPTIONS: AdapterOption[] = [
  { name: "fake", version: "1.0.0", label: "fake — deterministic test target" },
  { name: "websocket", version: "1.0.0", label: "websocket" },
];

export const TRANSPORT_OPTIONS = [
  { value: "websocket", label: "WebSocket" },
  { value: "webrtc", label: "WebRTC (interface only)" },
] as const;

export function adapterVersion(name: string): string {
  return ADAPTER_OPTIONS.find((adapter) => adapter.name === name)?.version ?? "1.0.0";
}
