import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import AppShell from "./AppShell";

// Retail mode now fetches analytics and draws charts (U3). Neither belongs to
// what this file tests — which half the shell renders — so the chart frame
// is stubbed (jsdom has no ResizeObserver for Bklit's @visx/responsive
// sizing) and fetch never resolves, leaving the dashboard in its loading
// state.
vi.mock("../components/retail/charts/BklitFrame", () => ({
  default: () => <div data-testid="bklit-frame" />,
}));
vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));

function mountAt(url: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>
        <AppShell>
          <div data-testid="consumer-content">consumer content</div>
        </AppShell>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AppShell", () => {
  it("renders the toggle in every mode", () => {
    mountAt("/");
    expect(screen.getByRole("button", { name: /retail mode|modo tienda/i })).toBeTruthy();
  });

  it("shows the wrapped routes when no mode is set", () => {
    mountAt("/");
    expect(screen.getByTestId("consumer-content")).toBeTruthy();
  });

  it("shows retail instead of the consumer routes at ?mode=retail", () => {
    mountAt("/?mode=retail");
    // The consumer half must be absent, not merely covered: an offline cache
    // or a screen reader would still reach it if it were only hidden.
    expect(screen.queryByTestId("consumer-content")).toBeNull();
    expect(screen.getByRole("heading", { name: /retail mode|modo tienda/i })).toBeTruthy();
  });

  it("treats an unrecognised mode as consumer", () => {
    mountAt("/?mode=wharrgarbl");
    expect(screen.getByTestId("consumer-content")).toBeTruthy();
  });

  it("round-trips the param through the toggle", async () => {
    const { container } = mountAt("/?lang=en");
    const button = screen.getByRole("button", { name: /retail mode/i });

    expect(button.getAttribute("aria-pressed")).toBe("false");
    button.click();

    // Pressed state and rendered half both follow the URL, so asserting the
    // button is enough to know the param was written.
    const pressed = await screen.findByRole("button", { name: /shopper mode/i });
    expect(pressed.getAttribute("aria-pressed")).toBe("true");
    expect(container.querySelector(".app-shell")?.getAttribute("data-mode")).toBe("retail");

    // And back again — consumer is the absence of the param, not mode=consumer.
    pressed.click();
    const unpressed = await screen.findByRole("button", { name: /retail mode/i });
    expect(unpressed.getAttribute("aria-pressed")).toBe("false");
    expect(screen.getByTestId("consumer-content")).toBeTruthy();
  });
});
