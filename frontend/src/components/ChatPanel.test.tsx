import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ChatPanel from "./ChatPanel";
import type { ShopContext } from "../chat/shopkeeper";

const CTX: ShopContext = {
  shopId: "s1",
  shopName: "Farmacia Sol",
  itemName: "ibuprofeno 400 mg",
  price: 3.4,
  stockQty: 9,
};

/**
 * U2 added a `variant` prop to this shared component. These tests pin the
 * CONSUMER path — the one that already shipped — so the retail pane cannot
 * quietly change how the shopper's slide-over behaves.
 */
describe("ChatPanel, overlay variant (consumer)", () => {
  it("keeps the scrim and the dialog role by default", () => {
    const { container } = render(<ChatPanel ctx={CTX} lang="en" onClose={() => {}} />);

    expect(container.querySelector(".chat-scrim")).toBeTruthy();
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(container.querySelector(".chat-panel--pane")).toBeNull();
  });

  it("closes on the close button, on the scrim, and on Escape", () => {
    const onClose = vi.fn();
    const { container } = render(<ChatPanel ctx={CTX} lang="en" onClose={onClose} />);

    fireEvent.click(screen.getByRole("button", { name: /close chat/i }));
    expect(onClose).toHaveBeenCalledTimes(1);

    fireEvent.click(container.querySelector(".chat-scrim")!);
    expect(onClose).toHaveBeenCalledTimes(2);

    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(3);
  });

  it("does not close when the panel itself is clicked", () => {
    const onClose = vi.fn();
    const { container } = render(<ChatPanel ctx={CTX} lang="en" onClose={onClose} />);

    fireEvent.click(container.querySelector(".chat-panel")!);
    expect(onClose).not.toHaveBeenCalled();
  });

  it("leaves Escape alone in the pane variant", () => {
    const onClose = vi.fn();
    render(<ChatPanel ctx={CTX} lang="en" onClose={onClose} variant="pane" />);

    // A permanent column must not react to Escape — the key belongs to
    // whatever dialog is actually open on top of it.
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).not.toHaveBeenCalled();
  });
});
