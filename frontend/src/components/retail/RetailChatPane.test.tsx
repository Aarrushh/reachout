import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import RetailChatPane from "./RetailChatPane";

describe("RetailChatPane", () => {
  it("renders as a pane, not as a modal", () => {
    const { container } = render(<RetailChatPane lang="en" />);

    // No scrim and no dialog role: a column that is always on screen is not a
    // dialog, and announcing it as one makes a screen reader wait for a
    // dismissal that never comes.
    expect(container.querySelector(".chat-scrim")).toBeNull();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(container.querySelector(".chat-panel--pane")).toBeTruthy();
    // Nothing to close, so no close button.
    expect(screen.queryByRole("button", { name: /close chat/i })).toBeNull();
  });

  it("says on screen that the shop and stock are samples", () => {
    render(<RetailChatPane lang="en" />);

    // The load-bearing assertion of this whole task. The pane quotes a stock
    // level, and retail mode has no inventory sync — so if this notice ever
    // disappears, a shopkeeper is being shown a made-up number about their
    // own shop with nothing marking it as invented.
    expect(screen.getByText(/not your real inventory/i)).toBeTruthy();
    expect(screen.getByText(/simulated replies/i)).toBeTruthy();
  });

  it("shows the sample notice in Spanish too", () => {
    render(<RetailChatPane lang="es" />);
    expect(screen.getByText(/no es tu inventario real/i)).toBeTruthy();
  });

  it("answers a question from the mock, with no backend", async () => {
    render(<RetailChatPane lang="en" />);

    fireEvent.click(screen.getByRole("button", { name: /is it in stock\?/i }));

    // The reply is composed locally by chat/shopkeeper.ts (string templates,
    // no AI, no fetch) after a typing delay.
    await waitFor(
      () => expect(screen.getByText(/in stock \(12 units right now\)/i)).toBeTruthy(),
      { timeout: 4000 },
    );
  });
});
