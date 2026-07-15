import { describe, expect, it } from "vitest";

import { composeReply, type ShopContext } from "./shopkeeper";

const CTX: ShopContext = {
  shopId: "s1",
  shopName: "Farmacia Sol",
  itemName: "Paracetamol 1g",
  price: 3.5,
  stockQty: 12,
};

describe("composeReply", () => {
  it("answers stock questions from real stock data", () => {
    expect(composeReply(CTX, "¿Lo tenéis en stock?", "es")).toContain("12");
    expect(composeReply(CTX, "Is it in stock?", "en")).toContain("in stock");
  });

  it("answers price questions with the formatted price", () => {
    expect(composeReply(CTX, "how much does it cost?", "en")).toContain("€3.50");
  });

  it("offers to hold when low stock, refuses when out", () => {
    const low = { ...CTX, stockQty: 2 };
    expect(composeReply(low, "hay stock?", "es")).toContain("2");
    const out = { ...CTX, stockQty: 0 };
    expect(composeReply(out, "can you hold one?", "en")).toMatch(/out of/i);
  });

  it("confirms a reservation when stocked", () => {
    expect(composeReply(CTX, "¿Me lo puedes apartar?", "es")).toContain("te guardo");
  });

  it("falls back helpfully in the right language", () => {
    expect(composeReply(CTX, "xyzzy", "es")).toContain("Paracetamol 1g");
    expect(composeReply(CTX, "xyzzy", "en")).toContain("What do you need?");
  });
});
