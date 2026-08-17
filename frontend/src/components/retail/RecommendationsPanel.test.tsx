import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import RecommendationsPanel from "./RecommendationsPanel";
import type { RecommendationsResponse } from "../../types/RecommendationsResponse";

type Recommendation = RecommendationsResponse["recommendations"][number];

function row(overrides: Partial<Recommendation>): Recommendation {
  return {
    id: "rec-1",
    store_id: "b0eb92f6-6faf-4650-bbc4-6564cc14063a",
    signal_id: "signal-1",
    headline: "Sube el interés por grocery en Madrid",
    body: "Tienes 15 productos de esta categoría en stock.",
    action: "stock_up",
    confidence: "high",
    caveat: "Basado en interés de búsqueda en Madrid, no en compras reales.",
    created_at: "2026-08-17T09:00:00+00:00",
    ...overrides,
  };
}

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <RecommendationsPanel lang="en" />
    </QueryClientProvider>,
  );
}

function respondWith(recommendations: Recommendation[], storeId = "b0eb92f6-6faf-4650-bbc4-6564cc14063a") {
  const fetchMock = vi.fn(
    async () =>
      ({
        ok: true,
        status: 200,
        json: async () => ({ store_id: storeId, recommendations }),
      }) as unknown as Response,
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("RecommendationsPanel", () => {
  beforeEach(() => vi.unstubAllGlobals());
  afterEach(() => vi.unstubAllGlobals());

  // C4: confidence is per row, never one badge for the whole panel — three
  // rows from one payload must each carry their own chip.
  it("renders a distinct confidence chip per row from a single payload", async () => {
    respondWith([
      row({ id: "1", action: "stock_up", confidence: "high" }),
      row({ id: "2", action: "feature_in_window", confidence: "medium" }),
      row({ id: "3", action: "watch", confidence: "low" }),
    ]);
    const { container } = mount();

    await screen.findByText("Stock up");

    expect(container.querySelectorAll(".chart-panel__chip--high").length).toBe(1);
    expect(container.querySelectorAll(".chart-panel__chip--medium").length).toBe(1);
    expect(container.querySelectorAll(".chart-panel__chip--low").length).toBe(1);
  });

  // C3: every distinct caveat string the server sends must be visible in
  // flow text, verbatim — never dropped, never a tooltip.
  it("shows a distinct caveat string from the payload, verbatim", async () => {
    const caveat = "Basado en interés de búsqueda en Madrid, no en compras reales.";
    respondWith([row({ caveat })]);
    mount();

    await screen.findByText("Stock up");
    expect(screen.getByText(caveat)).toBeTruthy();
  });

  // C7: the endpoint sends no X-Total-Count, so the count line must state a
  // plain N and never claim "of" some larger total it cannot back up.
  it("states the plain shown count, with no 'of' in the copy", async () => {
    respondWith([row({ id: "1" }), row({ id: "2" })]);
    mount();

    const countLine = await screen.findByText(/showing 2 recommendations/i);
    expect(countLine.textContent).not.toMatch(/\bof\b/i);
  });

  it("renders the panel's empty state for an empty recommendations array", async () => {
    respondWith([]);
    mount();

    expect(await screen.findByText(/no data for this chart yet/i)).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("reports a failure with role=\"alert\" instead of a silent empty panel", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: false, status: 502, json: async () => ({}) }) as unknown as Response),
    );
    mount();

    expect(await screen.findByRole("alert")).toBeTruthy();
  });
});
