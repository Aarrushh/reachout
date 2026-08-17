import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ClickSpark from "./ClickSpark";

/**
 * D12 local patch R1 acceptance test (docs/IMPLEMENTATION_PLAN_V3.md section
 * 4.3, section 6.6) - the ClickSpark half of the same reduced-motion gap
 * BlurText.test.tsx covers: upstream ClickSpark has no reduced-motion
 * handling, and a canvas/rAF-driven burst can't be reached by the CSS
 * `prefers-reduced-motion` kill switch in `tokens.css`.
 *
 * jsdom has no ResizeObserver; ClickSpark observes its own parent on mount
 * regardless of which branch the click handler takes, so every test needs a
 * stand-in even though the assertions only care about the click handler.
 */
class FakeResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

function stubMatchMedia(matches: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      matches,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  );
}

describe("ClickSpark", () => {
  beforeEach(() => {
    vi.stubGlobal("ResizeObserver", FakeResizeObserver);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("under reduced motion: spawns no sparks, but the child's own onClick still fires", () => {
    stubMatchMedia(true);
    const onChildClick = vi.fn();

    const { container } = render(
      <ClickSpark sparkColor="var(--terracotta)" sparkRadius={18} sparkCount={8}>
        <button onClick={onChildClick}>go</button>
      </ClickSpark>,
    );

    const canvasEl = container.querySelector("canvas") as HTMLCanvasElement;
    // The spark-spawning code path reads the canvas's own bounding rect to
    // place the burst; under reduced motion the click handler returns
    // before reaching it, so a spy on this specific element is a precise
    // "no sparks were queued" signal (the mount-time ResizeObserver effect
    // reads the *parent's* rect, a different element, so it can't leak into
    // this count).
    const rectSpy = vi.spyOn(canvasEl, "getBoundingClientRect");

    fireEvent.click(screen.getByRole("button", { name: "go" }));

    expect(onChildClick).toHaveBeenCalledTimes(1);
    expect(rectSpy).not.toHaveBeenCalled();
  });

  it("with motion allowed: reads the canvas rect to queue a spark on click", () => {
    stubMatchMedia(false);
    const onChildClick = vi.fn();

    const { container } = render(
      <ClickSpark sparkColor="var(--terracotta)" sparkRadius={18} sparkCount={8}>
        <button onClick={onChildClick}>go</button>
      </ClickSpark>,
    );

    const canvasEl = container.querySelector("canvas") as HTMLCanvasElement;
    const rectSpy = vi.spyOn(canvasEl, "getBoundingClientRect");

    fireEvent.click(screen.getByRole("button", { name: "go" }));

    expect(onChildClick).toHaveBeenCalledTimes(1);
    expect(rectSpy).toHaveBeenCalled();
  });
});
