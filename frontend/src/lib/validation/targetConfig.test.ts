import { describe, expect, it } from "vitest";

import { findRawSecrets, parseJsonObject } from "./targetConfig";

describe("findRawSecrets", () => {
  it("flags raw secret values", () => {
    expect(findRawSecrets({ api_key: "sk-123" })).toEqual([
      "endpoint_config.api_key",
    ]);
  });

  it("allows secret references", () => {
    expect(findRawSecrets({ api_key: "secret:acme/key" })).toEqual([]);
    expect(findRawSecrets({ api_key: { $ref: "vault://acme" } })).toEqual([]);
  });

  it("walks nested objects and arrays", () => {
    const found = findRawSecrets({
      nested: { authorization: "Bearer x" },
      list: [{ token: "t" }],
    });
    expect(found).toEqual([
      "endpoint_config.nested.authorization",
      "endpoint_config.list[0].token",
    ]);
  });
});

describe("parseJsonObject", () => {
  it("parses a JSON object", () => {
    expect(parseJsonObject('{ "a": 1 }')).toEqual({ a: 1 });
  });

  it("rejects non-objects", () => {
    expect(() => parseJsonObject("[1,2]")).toThrow();
  });

  it("treats empty input as an empty object", () => {
    expect(parseJsonObject("   ")).toEqual({});
  });
});
