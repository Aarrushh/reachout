import { render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Bar, BarChart } from "./index";

/**
 * D11 patch acceptance tests (docs/IMPLEMENTATION_PLAN_V3.md §3.4), run
 * against the vendored source itself rather than mocks.
 *
 * `BarChart`/`PieChart` size themselves via `@visx/responsive`'s
 * `ParentSize`, which needs a real `ResizeObserver` to report a non-zero
 * container size — jsdom has none, and jsdom's layout engine always reports
 * 0×0 regardless, so without a stand-in `BarChart` never mounts its SVG at
 * all (`width < 10 || height < 10` guard in bar-chart.tsx's `ChartInner`).
 * This fake fires synchronously with a fixed 400×200 rect so the chart
 * renders; because that size is fixed and known, the resulting geometry
 * (margin defaults 40/40/40/40 → 120px inner height/width) is fully
 * deterministic, not flaky pixel-measurement of a browser that isn't there.
 */
class FakeResizeObserver {
  #callback: ResizeObserverCallback;

  constructor(callback: ResizeObserverCallback) {
    this.#callback = callback;
  }

  observe() {
    this.#callback(
      [
        {
          contentRect: { width: 400, height: 200, top: 0, left: 0 },
        } as ResizeObserverEntry,
      ],
      this as unknown as ResizeObserver,
    );
  }

  unobserve() {}
  disconnect() {}
}

beforeEach(() => {
  vi.stubGlobal("ResizeObserver", FakeResizeObserver);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("P1 — Bar colorAccessor (D11 local patch, bar.tsx)", () => {
  it("colours each bar per-datum via colorAccessor instead of one static fill for the series", async () => {
    // Mirrors options.ts's topMoversView: one horizontal bar per keyword,
    // coloured by the server's `direction`, not by sign.
    const DIRECTION_FILL: Record<string, string> = {
      rising: "var(--chart-rising)",
      falling: "var(--chart-falling)",
      flat: "var(--chart-flat)",
    };
    const data = [
      { keyword: "zapatillas running", delta_pct: 34, direction: "rising" },
      { keyword: "botas de lluvia", delta_pct: -12, direction: "falling" },
      { keyword: "paraguas", delta_pct: 0, direction: "flat" },
    ];

    const { container } = render(
      <BarChart animationDuration={0} data={data} orientation="horizontal" xDataKey="keyword">
        <Bar
          animate={false}
          colorAccessor={(d) => DIRECTION_FILL[d.direction as string] ?? "var(--chart-flat)"}
          dataKey="delta_pct"
        />
      </BarChart>,
    );

    await waitFor(() => {
      const fills = Array.from(container.querySelectorAll("rect")).map((r) => r.getAttribute("fill"));
      expect(fills).toContain("var(--chart-rising)");
    });

    const fills = Array.from(container.querySelectorAll("rect")).map((r) => r.getAttribute("fill"));

    // All three direction colours present — three distinct fill values, one
    // per row, proving colorAccessor ran per-datum rather than the bars
    // sharing Bar's single static `fill` prop.
    expect(fills).toContain("var(--chart-rising)");
    expect(fills).toContain("var(--chart-falling)");
    expect(fills).toContain("var(--chart-flat)");
    expect(new Set(fills.filter((f) => f?.startsWith("var(--chart-")))).toEqual(
      new Set(["var(--chart-rising)", "var(--chart-falling)", "var(--chart-flat)"]),
    );
  });

  it("falls back to the static `fill` prop when colorAccessor is not given (unpatched behaviour preserved)", async () => {
    const data = [
      { category: "a", value: 10 },
      { category: "b", value: 20 },
    ];

    const { container } = render(
      <BarChart animationDuration={0} data={data} xDataKey="category">
        <Bar animate={false} dataKey="value" fill="var(--chart-risk)" />
      </BarChart>,
    );

    await waitFor(() => {
      const fills = Array.from(container.querySelectorAll("rect")).map((r) => r.getAttribute("fill"));
      expect(fills).toContain("var(--chart-risk)");
    });

    const fills = Array.from(container.querySelectorAll("rect")).map((r) => r.getAttribute("fill"));
    // Both bars share the one static fill — no colorAccessor, no per-datum split.
    expect(fills.filter((f) => f === "var(--chart-risk)")).toHaveLength(2);
  });
});

describe("P2 — BarChart domainMax (D11 local patch, bar-chart.tsx)", () => {
  it("pins the value-axis top to domainMax=100 instead of maxValue * 1.1 (=44 for a 40 max)", async () => {
    // StockOutRiskChart's real shape: one vertical bar per category, axis
    // pinned to 100 because risk_pct is a share of certainty (options.ts).
    const data = [
      { category: "lácteos", risk_pct: 40 },
      { category: "panadería", risk_pct: 10 },
    ];

    const { container } = render(
      <BarChart animationDuration={0} data={data} domainMax={100} xDataKey="category">
        <Bar animate={false} dataKey="risk_pct" fill="var(--chart-risk)" />
      </BarChart>,
    );

    await waitFor(() => {
      expect(container.querySelectorAll("rect[fill]").length).toBeGreaterThan(0);
    });

    // Fixed 400x200 parent, default margin 40/40/40/40 -> innerHeight = 120px.
    // domain [0, 100] mapped onto range [120, 0]: a risk_pct=40 bar should be
    // exactly 40/100 = 40% of inner height = 48px tall. Without the patch
    // (maxValue * 1.1 = 44, nice:true) the same datum would read as roughly
    // 40/44 ≈ 91% ≈ 109px — a materially taller bar reading as more urgent
    // than the server's own number supports.
    const barRect = Array.from(container.querySelectorAll("rect[fill='var(--chart-risk)']"))[0];
    expect(barRect).toBeTruthy();
    expect(Number(barRect?.getAttribute("height"))).toBeCloseTo(48, 0);
  });

  it("without domainMax, the same datum renders taller (maxValue * 1.1 headroom) — proves the patch changes behaviour", async () => {
    const data = [
      { category: "lácteos", risk_pct: 40 },
      { category: "panadería", risk_pct: 10 },
    ];

    const { container } = render(
      <BarChart animationDuration={0} data={data} xDataKey="category">
        <Bar animate={false} dataKey="risk_pct" fill="var(--chart-risk)" />
      </BarChart>,
    );

    await waitFor(() => {
      expect(container.querySelectorAll("rect[fill]").length).toBeGreaterThan(0);
    });

    const barRect = Array.from(container.querySelectorAll("rect[fill='var(--chart-risk)']"))[0];
    const height = Number(barRect?.getAttribute("height"));
    // 40 / (40 * 1.1) = 40/44 of 120px ≈ 109px — well above the pinned 48px.
    expect(height).toBeGreaterThan(90);
  });
});
