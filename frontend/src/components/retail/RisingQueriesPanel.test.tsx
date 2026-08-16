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

function respondWith(rows: RisingQuery[], total: number = rows.length) {
  const fetchMock = vi.fn(
    async () =>
      ({
        ok: true,
        status: 200,
        json: async () => rows,
        headers: { get: (name: string) => (name === "X-Total-Count" ? String(total) : null) },
      }) as unknown as Response,
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
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

  // Fix round 1, Important #2: the live table holds 658 rows and the
  // server's own unpadded default page size is 100 (demand/api/app.py),
  // so calling the endpoint with no `limit` would silently render at most
  // a sixth of what exists, captioned as though it were complete. The
  // explicit value is now the route's own ceiling (1000), not the shared
  // `MAX_PAGE_SIZE` (500) the other list endpoints use.
  it("requests the server's maximum page size explicitly, rather than accepting a silently truncated default", async () => {
    respondWith([row({})]);
    mount();

    await screen.findByText("gafas eclipse");
    const url = (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toContain("/demand/api/rising-queries");
    expect(url).toContain("limit=1000");
  });

  it("states the exact count shown, without implying it is exhaustive", async () => {
    respondWith([
      row({ id: "1", query: "gafas eclipse" }),
      row({ id: "2", query: "protector solar", cluster_id: "other" }),
    ]);
    mount();

    await screen.findByText("gafas eclipse");
    // Two distinct clusters were returned, so the honest count is 2 rows —
    // never worded as though this were "the rising searches in Madrid".
    expect(screen.getByText(/showing 2 rising searches/i)).toBeTruthy();
  });

  // The server, not a client-side row count, is now the source of truth for
  // whether more rows exist: `X-Total-Count` carries the post-tier-filter
  // total, and the caption only claims partial coverage when that total
  // exceeds what actually arrived.
  it("flags explicitly when the server's total exceeds what was returned", async () => {
    const rows = Array.from({ length: 500 }, (_, i) =>
      row({ id: `id-${i}`, cluster_id: `cluster-${i}`, query: `query ${i}` }),
    );
    respondWith(rows, 700);
    mount();

    expect(await screen.findByText(/showing 500 of 700 rising searches/i)).toBeTruthy();
  });

  it("requests the route ceiling, not the old 500 cap", async () => {
    respondWith([row({ query: "comprar cerveza barata" })], 1);
    mount();
    await screen.findByText(/comprar cerveza barata/i);
    const url = String((globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]);
    expect(url).toContain("limit=1000");
  });

  it("says how many of the total it is showing when the total is larger", async () => {
    respondWith([row({ query: "comprar cerveza barata" })], 1200);
    mount();
    expect(await screen.findByText(/showing 1 of 1200/i)).toBeTruthy();
  });

  it("does not say 'of N' when it holds every row", async () => {
    respondWith([row({ query: "comprar cerveza barata" })], 1);
    mount();
    expect(await screen.findByText(/^showing 1 rising searches?\.$/i)).toBeTruthy();
  });
});
