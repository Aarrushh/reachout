import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import RetailDashboard from "./RetailDashboard";
import type { AnalyticsResponse } from "../../types/AnalyticsResponse";
import type { RisingQuery } from "../../types/RisingQuery";

// Bklit's BarChart/PieChart size themselves via @visx/responsive's
// ParentSize, which needs a real ResizeObserver reporting non-zero container
// size — jsdom has none, so without a stand-in the vendored charts never
// mount their SVG at all (see bklit-patches.test.tsx). That vendored-source
// layout detail is not what these tests are about — the frame around it is —
// so BklitFrame itself is replaced by a stub that exposes only its
// aria-label, the one thing these tests need to count and identify panels by.
vi.mock("./charts/BklitFrame", () => ({
  default: ({ ariaLabel }: { ariaLabel: string }) => (
    <div data-testid="bklit-frame" aria-label={ariaLabel} role="img" />
  ),
}));

const RESPONSE: AnalyticsResponse = {
  inventory_type: "convenience_store",
  generated_from: "fixture",
  generated_at: "2026-08-04T09:00:00Z",
  caveat: "Basado en interés de búsqueda en Madrid, no en compras reales.",
  segments: {
    top_movers: {
      confidence: "medium",
      points: [
        { keyword: "protector solar", category: null, interest_avg: 78.4, delta_pct: 42.6, direction: "rising" },
      ],
    },
    category_mix: {
      confidence: "high",
      points: [{ category: "grocery", share_pct: 41.5, product_count: 42 }],
    },
    stock_out_risk: { confidence: "low", points: [] },
  },
};

function mount(lang: "es" | "en" = "en") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <RetailDashboard lang={lang} />
    </QueryClientProvider>,
  );
}

// RetailDashboard now fires three independent fetches once analytics loads:
// its own /analytics call, the discovery panel's /rising-queries call, and
// the recommendations panel's /recommendations call. Routing by URL keeps
// each test's analytics fixture from being handed back for the other two
// requests too, which would not even be the right shape.
function respondWith(body: AnalyticsResponse, risingQueries: RisingQuery[] = []) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (String(url).includes("/rising-queries")) {
        return {
          ok: true,
          status: 200,
          json: async () => risingQueries,
          headers: { get: (name: string) => (name === "X-Total-Count" ? String(risingQueries.length) : null) },
        } as unknown as Response;
      }
      if (String(url).includes("/recommendations")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({ store_id: "b0eb92f6-6faf-4650-bbc4-6564cc14063a", recommendations: [] }),
        } as unknown as Response;
      }
      return { ok: true, status: 200, json: async () => body } as unknown as Response;
    }),
  );
}

describe("RetailDashboard", () => {
  beforeEach(() => vi.unstubAllGlobals());
  afterEach(() => vi.unstubAllGlobals());

  it("says the data is practice data when the response says fixture", async () => {
    respondWith(RESPONSE);
    mount();

    // The honesty rule the plan states outright: never present practice data
    // as live. `generated_from` is the only thing that distinguishes them,
    // and the shapes are byte-identical, so dropping this label would leave
    // canned numbers looking exactly like the shop's own.
    expect(await screen.findByText(/practice data, not your shop's/i)).toBeTruthy();
  });

  it("does not cry practice data when the response is live", async () => {
    respondWith({ ...RESPONSE, generated_from: "live" });
    mount();

    await screen.findByRole("heading", { name: /^top movers$/i });
    expect(screen.queryByText(/practice data/i)).toBeNull();
  });

  it("renders each segment with its own confidence, not one shared label", async () => {
    respondWith(RESPONSE);
    mount();

    // Three different confidences in one payload. A dashboard that showed the
    // response's first, or a hardcoded one, would pass a weaker test.
    expect(await screen.findByText("Confidence: medium")).toBeTruthy();
    expect(screen.getByText("Confidence: high")).toBeTruthy();
    expect(screen.getByText("Confidence: low")).toBeTruthy();
  });

  it("puts the caveat on every panel, including the empty one", async () => {
    respondWith(RESPONSE);
    mount();

    await screen.findByRole("heading", { name: /^top movers$/i });
    expect(screen.getAllByText(RESPONSE.caveat)).toHaveLength(3);
    // stock_out_risk has no points: empty state, chart absent, caveat present.
    expect(screen.getByText(/no data for this chart yet/i)).toBeTruthy();
    expect(screen.getAllByTestId("bklit-frame")).toHaveLength(2);
  });

  it("reports a failed fetch instead of rendering empty charts", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: false, status: 502, json: async () => ({}) }) as unknown as Response),
    );
    mount();

    // An error must not look like "no data yet" — one means try again, the
    // other means the shop genuinely has nothing trending.
    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
    expect(screen.getByText(/could not load the analytics/i)).toBeTruthy();
    expect(screen.queryByText(/no data for this chart yet/i)).toBeNull();
  });

  it("asks the demand service for the convenience-store analytics", async () => {
    respondWith(RESPONSE);
    mount();

    await screen.findByRole("heading", { name: /^top movers$/i });
    const url = (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toContain("/demand/api/analytics");
    expect(url).toContain("inventory_type=convenience_store");
  });

  it("defaults to the 3-month timeframe and refetches on switching to 12 months", async () => {
    respondWith(RESPONSE);
    mount();

    await screen.findByRole("heading", { name: /^top movers$/i });
    const calls = (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls;
    const firstAnalyticsCall = calls.find((c) => String(c[0]).includes("/demand/api/analytics"));
    expect(String(firstAnalyticsCall?.[0])).toContain("timeframe=today+3-m");

    // This is the critical correctness rule (task-4, requirement 2): a
    // 3-month reading and a 12-month reading of the same keyword are on
    // different, non-convertible scales, so switching the toggle must issue
    // a brand new fetch rather than reslicing what is already in memory.
    fireEvent.click(screen.getByRole("button", { name: "12 months" }));

    await waitFor(() => {
      const callsAfter = (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls;
      const secondAnalyticsCall = callsAfter
        .filter((c) => String(c[0]).includes("/demand/api/analytics"))
        .at(-1);
      expect(String(secondAnalyticsCall?.[0])).toContain("timeframe=today+12-m");
    });
  });

  it("does not let the timeframe toggle appear to move category mix or stock-out risk", async () => {
    respondWith(RESPONSE);
    mount();

    await screen.findByRole("heading", { name: /^top movers$/i });

    // Placement, not just wording: the toggle's caption names the two
    // segments it does NOT govern, and both charts still render outside
    // the toggle's own column.
    expect(screen.getByText(/category mix and stock-out risk/i)).toBeTruthy();
  });

  it("tells the shopkeeper the two timeframes are not comparable", async () => {
    respondWith(RESPONSE);
    mount();

    expect(
      await screen.findByText(/cannot be compared with each other/i),
    ).toBeTruthy();
  });

  it("describes the percentages the charts actually draw, and denies only what they are not", async () => {
    // The Top Movers x-axis is formatted "{value}%" over `delta_pct`, so a
    // paragraph above it saying "these numbers are not a percentage" reads
    // as a contradiction of the only numbers on screen. `interest_avg` — the
    // uncapped relative index — has no render site in this app. The copy
    // must name week-on-week change and rule out sales, customers and market
    // share, which are the readings that would cost a shopkeeper money.
    respondWith(RESPONSE);
    mount();

    expect(
      await screen.findByText(/change in search interest against the previous week/i),
    ).toBeTruthy();
    expect(screen.getByText(/not sales, customers or market share/i)).toBeTruthy();
  });

  it("keeps category mix and stock-out risk mounted while a timeframe refetch is in flight, instead of blanking the whole dashboard", async () => {
    // Fix round 1, Important #1: with `timeframe` in the queryKey, switching
    // it used to create a brand-new query with no cached data, so
    // `analytics.isPending` went true and the dashboard's early return
    // replaced everything — category_mix, stock_out_risk, the discovery
    // panel — with a generic "Loading analytics…" line. That defeated the
    // requirement that the toggle must not APPEAR to change the two
    // inventory-derived segments. This test holds the second analytics
    // fetch open deliberately so it can assert on the DOM mid-flight,
    // not just on the eventual query-string value.
    let releaseSecondFetch: () => void = () => {};
    const secondFetchGate = new Promise<void>((resolve) => {
      releaseSecondFetch = resolve;
    });
    let analyticsCallCount = 0;

    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (String(url).includes("/rising-queries")) {
          return {
            ok: true,
            status: 200,
            json: async () => [],
            headers: { get: (name: string) => (name === "X-Total-Count" ? "0" : null) },
          } as unknown as Response;
        }
        if (String(url).includes("/recommendations")) {
          return {
            ok: true,
            status: 200,
            json: async () => ({ store_id: "b0eb92f6-6faf-4650-bbc4-6564cc14063a", recommendations: [] }),
          } as unknown as Response;
        }
        analyticsCallCount += 1;
        if (analyticsCallCount > 1) {
          await secondFetchGate;
        }
        return { ok: true, status: 200, json: async () => RESPONSE } as unknown as Response;
      }),
    );

    mount();
    await screen.findByRole("heading", { name: /^top movers$/i });
    expect(screen.getAllByTestId("bklit-frame").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "12 months" }));

    // Confirm the refetch actually started before asserting the DOM.
    await waitFor(() => expect(analyticsCallCount).toBeGreaterThanOrEqual(2));

    // The second fetch is still pending at this point (gated on
    // `secondFetchGate`) — this is exactly the window the bug blanked.
    expect(screen.getByRole("heading", { name: /^category mix$/i })).toBeTruthy();
    expect(screen.getByRole("heading", { name: /^stock-out risk$/i })).toBeTruthy();
    expect(screen.getAllByTestId("bklit-frame").length).toBeGreaterThan(0);
    expect(screen.queryByText(/loading analytics/i)).toBeNull();

    releaseSecondFetch();
    await waitFor(() => expect(analyticsCallCount).toBe(2));
  });
});
