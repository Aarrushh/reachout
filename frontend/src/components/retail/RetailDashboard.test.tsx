import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import RetailDashboard from "./RetailDashboard";
import type { AnalyticsResponse } from "../../types/AnalyticsResponse";

// ECharts renders into a canvas that jsdom does not implement. The chart
// library is not what these tests are about — the frame around it is — so it
// is replaced by a stub that exposes the option it was handed.
vi.mock("echarts-for-react", () => ({
  default: ({ option }: { option: Record<string, unknown> }) => (
    <div data-testid="echart" data-option={JSON.stringify(option)} />
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

function respondWith(body: AnalyticsResponse) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, status: 200, json: async () => body }) as unknown as Response),
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

    await screen.findByText(/top movers/i);
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

    await screen.findByText(/top movers/i);
    expect(screen.getAllByText(RESPONSE.caveat)).toHaveLength(3);
    // stock_out_risk has no points: empty state, chart absent, caveat present.
    expect(screen.getByText(/no data for this chart yet/i)).toBeTruthy();
    expect(screen.getAllByTestId("echart")).toHaveLength(2);
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

    await screen.findByText(/top movers/i);
    const url = (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toContain("/demand/api/analytics");
    expect(url).toContain("inventory_type=convenience_store");
  });
});
