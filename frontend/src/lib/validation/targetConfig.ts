const SECRET_HINT_FRAGMENTS = [
  "secret",
  "token",
  "password",
  "api_key",
  "apikey",
  "credential",
  "authorization",
  "private_key",
];

export function isSecretReference(value: unknown): boolean {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    const record = value as Record<string, unknown>;
    if ("$ref" in record || "secret_ref" in record) return true;
  }
  if (typeof value === "string") {
    return (
      value.startsWith("secret:") ||
      value.startsWith("secrets.") ||
      value.startsWith("$ref:")
    );
  }
  return false;
}

// Client mirror of the backend guard so users see the problem before submitting.
export function findRawSecrets(
  config: unknown,
  prefix = "endpoint_config",
): string[] {
  const found: string[] = [];

  const walk = (node: unknown, path: string): void => {
    if (Array.isArray(node)) {
      node.forEach((item, index) => walk(item, `${path}[${index}]`));
      return;
    }
    if (node && typeof node === "object") {
      for (const [key, value] of Object.entries(node as Record<string, unknown>)) {
        const childPath = `${path}.${key}`;
        const lower = key.toLowerCase();
        const isSecretKey = SECRET_HINT_FRAGMENTS.some((frag) =>
          lower.includes(frag),
        );
        if (isSecretKey && !isSecretReference(value)) found.push(childPath);
        walk(value, childPath);
      }
    }
  };

  walk(config, prefix);
  return found;
}

export function parseJsonObject(text: string): Record<string, unknown> {
  const trimmed = text.trim();
  if (trimmed === "") return {};
  const parsed: unknown = JSON.parse(trimmed);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("must be a JSON object");
  }
  return parsed as Record<string, unknown>;
}

export function formatJson(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2);
}
