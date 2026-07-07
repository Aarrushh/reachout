import { describe, expect, it } from "vitest";

import { t } from "./strings";

describe("i18n", () => {
  it("returns Spanish by default keys", () => {
    expect(t("es", "search.placeholder")).toContain("dolor de cabeza");
  });
  it("returns English variants", () => {
    expect(t("en", "entry.headline")).toBe("Where are you in Madrid?");
  });
  it("interpolates variables", () => {
    expect(t("en", "results.lowStock", { n: 3 })).toBe("only 3 left");
  });
});
