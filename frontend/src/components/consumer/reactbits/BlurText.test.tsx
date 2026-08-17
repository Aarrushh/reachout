import { render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import BlurText from "./BlurText";

/**
 * D12 local patch R1 acceptance test (docs/IMPLEMENTATION_PLAN_V3.md section
 * 4.3, section 6.6). Upstream BlurText has no reduced-motion handling at
 * all, and the CSS `prefers-reduced-motion` kill switch in `tokens.css`
 * cannot reach a JS-driven `motion.span` animation - this is the entire
 * reason the patch exists, so it gets its own test rather than trusting a
 * code-review glance.
 *
 * jsdom implements neither `matchMedia` nor `IntersectionObserver`;
 * `BlurText` calls both unconditionally on mount (the observer effect runs
 * before the reduced-motion branch, regardless of which branch renders), so
 * both need a stand-in here even though only `matchMedia`'s value is what
 * the test varies.
 */
class FakeIntersectionObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

const NBSP = " ";

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

describe("BlurText", () => {
  beforeEach(() => {
    vi.stubGlobal("IntersectionObserver", FakeIntersectionObserver);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("under reduced motion: renders the full text instantly, with zero motion.span animations", () => {
    stubMatchMedia(true);

    const { container } = render(
      <BlurText text="hola mundo" animateBy="words" delay={80} stepDuration={0.3} className="entry-h1" />,
    );

    // Same text in, same text out - a non-breaking space stands in for the
    // word join, same as the animated branch, so a shopper reads identical
    // copy either way.
    expect(container.textContent).toBe(`hola${NBSP}mundo`);

    const spans = Array.from(container.querySelectorAll("span"));
    expect(spans.length).toBeGreaterThan(0);
    // motion.span always carries this inline hint so the compositor can
    // prepare the animated properties; the reduced-motion fallback is a
    // plain <span> that never sets it. Its absence on every span is the
    // "zero motion.span animations" the brief asks for.
    for (const span of spans) {
      expect(span.style.willChange).toBe("");
    }
  });

  it("with motion allowed: renders motion.span elements that do carry the animation hint", () => {
    stubMatchMedia(false);

    const { container } = render(<BlurText text="hola mundo" animateBy="words" />);

    expect(container.textContent).toBe(`hola${NBSP}mundo`);
    const spans = Array.from(container.querySelectorAll("span"));
    expect(spans.length).toBeGreaterThan(0);
    expect(spans.some((s) => s.style.willChange !== "")).toBe(true);
  });
});
