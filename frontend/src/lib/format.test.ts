import { describe, expect, it } from "vitest";

import { formatDistance, formatPrice } from "./format";

describe("format", () => {
  it("shows meters under 1 km", () => {
    expect(formatDistance(0.412, "en")).toBe("412 m");
  });
  it("uses locale decimal for km", () => {
    expect(formatDistance(1.24, "es")).toBe("1,2 km");
    expect(formatDistance(1.24, "en")).toBe("1.2 km");
  });
  it("formats euros", () => {
    expect(formatPrice(3.8)).toBe("€3.80");
  });
});
