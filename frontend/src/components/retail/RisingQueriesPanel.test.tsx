import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import RisingQueriesPanel from "./RisingQueriesPanel";
import type { RisingQuery } from "../../types/RisingQuery";

function row(overrides: Partial<RisingQuery>): RisingQuery {
  return {
    id: "id-1",
    parent_keyword: "gafas de sol",
    query: "gafas eclipse",
    growth_pct: 120,
    is_breakout: false,
    geo: "ES-MD",
    gprop: "",
    captured_at: "2026-08-01T00:00:00Z",
    captured_date: "2026-08-01",
    relevance_score: 5,
    relevance_tier: "commercial",
    relevance_reasons: ["contains_parent_keyword"],
    cluster_id: "eclipse gafas",
    ...overrides,
  };
}

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <RisingQueriesPanel lang="en" />
    </QueryClientProvider>,
  );
}

function respondWith(rows: RisingQuery[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, status: 200, json: async () => rows }) as unknown as Response),
  );
}

describe("RisingQueriesPanel", () => {
  beforeEach(() => vi.unstubAllGlobals());
  afterEach(() => vi.unstubAllGlobals());

  it("renders a Breakout label and no numeric growth value for a breakout row", async () => {
    respondWith([row({ query: "gafas eclipse", growth_pct: null, is_breakout: true })]);
    mount();

    expect(await screen.findByText("Breakout")).toBeTruthy();

    // The load-bearing assertion: a fabricated zero next to a real
    // percentage is the exact failure this whole pipeline exists to avoid.
    expect(screen.queryByText("0")).toBeNull();
    expect(screen.queryByText("0%")).toBeNull();
    expect(screen.queryByText(/^\+?0%?$/)).toBeNull();
  });

  it("renders the actual growth_pct for a quantified row", async () => {
    respondWith([row({ query: "protector solar", growth_pct: 87.5, is_breakout: false })]);
    mount();

    expect(await screen.findByText("+87.5%")).toBeTruthy();
    expect(screen.queryByText("Breakout")).toBeNull();
  });

  it("collapses rows sharing a cluster_id into one displayed entry", async () => {
    respondWith([
      row({ id: "1", query: "gafas eclipse", cluster_id: "eclipse gafas", growth_pct: 200 }),
      row({ id: "2", query: "gafas para el eclipse", cluster_id: "eclipse gafas", growth_pct: 180 }),
      row({ id: "3", query: "gafas eclipse solar", cluster_id: "eclipse gafas", growth_pct: 210 }),
    ]);
    mount();

    await screen.findByText("gafas eclipse");
    expect(screen.queryByText("gafas para el eclipse")).toBeNull();
    expect(screen.queryByText("gafas eclipse solar")).toBeNull();
    expect(screen.getByText(/3 similar searches/i)).toBeTruthy();
  });

  it("renders the empty state, not an error, for an empty response", async () => {
    respondWith([]);
    mount();

    expect(await screen.findByText(/no data for this chart yet/i)).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("carries its own caveat naming Madrid search interest, not this shop's inventory", async () => {
    respondWith([row({})]);
    mount();

    await screen.findByText("gafas eclipse");
    expect(screen.getByText(/search interest across madrid/i)).toBeTruthy();
    expect(screen.getByText(/not this shop's inventory/i)).toBeTruthy();
  });

  it("shows no confidence chip, since the endpoint has none of its own", async () => {
    respondWith([row({})]);
    const { container } = mount();

    await screen.findByText("gafas eclipse");
    expect(container.querySelector(".chart-panel__chip")).toBeNull();
  });

  it("reports a failure instead of a silent empty panel", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: false, status: 502, json: async () => ({}) }) as unknown as Response),
    );
    mount();

    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.queryByText(/no data for this chart yet/i)).toBeNull();
  });
});
