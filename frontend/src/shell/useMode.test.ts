import { describe, expect, it } from "vitest";

import { parseMode } from "./useMode";

describe("parseMode", () => {
  it("selects retail only on the exact string", () => {
    expect(parseMode("retail")).toBe("retail");
  });

  it("falls back to consumer when the param is absent", () => {
    expect(parseMode(null)).toBe("consumer");
  });

  // Consumer is the safe default: an unrecognised value must never open the
  // shopkeeper's half. Case matters — the URL we write is lower-case, so
  // anything else came from somewhere we do not control.
  it.each(["", "RETAIL", "Retail", "consumer", "shop", "retail ", "retail;drop"])(
    "falls back to consumer for %o",
    (raw) => {
      expect(parseMode(raw)).toBe("consumer");
    },
  );
});
