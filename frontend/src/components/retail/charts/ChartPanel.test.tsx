import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ChartPanel from "./ChartPanel";

const CAVEAT = "Basado en interés de búsqueda en Madrid, no en compras reales.";

function mount(props: Partial<React.ComponentProps<typeof ChartPanel>> = {}) {
  return render(
    <ChartPanel
      lang="en"
      title="Top movers"
      confidence="medium"
      caveat={CAVEAT}
      isEmpty={false}
      {...props}
    >
      <div data-testid="chart-body">chart</div>
    </ChartPanel>,
  );
}

describe("ChartPanel", () => {
  it("shows the confidence chip as text, not as a hover", () => {
    const { container } = mount({ confidence: "low" });

    expect(screen.getByText("Confidence: low")).toBeTruthy();
    // A `title` attribute anywhere in the frame would be a hover-only label,
    // which a phone cannot reveal at all.
    expect(container.querySelector("[title]")).toBeNull();
  });

  it("shows the server's caveat verbatim, alongside the chart", () => {
    mount();

    // Verbatim: the caveat is a schema-required field of a validated
    // response. Rewording or translating it here would put a sentence on
    // screen that the backend never approved.
    expect(screen.getByText(CAVEAT)).toBeTruthy();
    expect(screen.getByTestId("chart-body")).toBeTruthy();
  });

  it("still shows the caveat when the segment is empty", () => {
    mount({ isEmpty: true });

    // The empty state is where a caveat matters most: nothing is drawn, so
    // nothing else on the panel says what these numbers would have meant.
    expect(screen.queryByTestId("chart-body")).toBeNull();
    expect(screen.getByText(/no data for this chart yet/i)).toBeTruthy();
    expect(screen.getByText(CAVEAT)).toBeTruthy();
  });

  it("translates the chip but never the caveat", () => {
    mount({ lang: "es", confidence: "high" });

    expect(screen.getByText("Confianza: alta")).toBeTruthy();
    expect(screen.getByText(CAVEAT)).toBeTruthy();
  });
});
