import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import AppShell from "./AppShell";

// This project runs vitest without `globals: true`, so RTL's automatic
// per-test cleanup never registers and every render stacks up in the same
// document. Without this, the second test onward sees two shells and every
// `getBy*` fails with "multiple elements found".
afterEach(cleanup);

function mountAt(url: string) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <AppShell>
        <div data-testid="consumer-content">consumer content</div>
      </AppShell>
    </MemoryRouter>,
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
