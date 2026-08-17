/**
 * The ONLY entry to the chart library (D11, the Bklit-based successor to
 * D9's retired chart wrapper).
 *
 * Bklit components are vendored source under ./bklit/, and reversing D11 must
 * be a rewrite of this folder and nothing else — so no sibling imports from
 * ./bklit/ except the chart components beside this file, and nothing outside
 * components/retail/charts/ imports any of it.
 *
 * It preserves the two behaviours every panel needs identically, carried
 * over from the chart wrapper it replaces:
 *
 * 1. **Charts never animate.** A dashboard that animates on every refetch
 *    draws the eye to motion rather than to the number. Bklit's animations
 *    are JS-driven (motion), so the tokens.css reduced-motion kill switch
 *    cannot reach them — instead, every chart beside this file passes
 *    `animate={false}` / `animationDuration={0}`, and the containment test
 *    greps for it (charts.containment.test.ts).
 * 2. **An accessible name.** Bklit renders an <svg> plus portaled HTML
 *    labels, none of which carries a name — this div is the img.
 *
 * `height` has no default (A1 gave it one; A2 removed it). `BarChart`'s own
 * container sizes itself from `aspectRatio` against its own width and
 * ignores an ancestor's fixed height (`bar-chart.tsx:716-719` sets
 * `style={{ aspectRatio }}` with no `height: 100%`) — composing a fixed
 * `height` here with that would leave this frame one size and the BarChart
 * inside it another, independently-computed size, which on `overflow-visible`
 * either clips or overflows depending on which is taller. So `height` is
 * opt-in: pass it for `PieChart`'s fixed-size donut, where there is nothing
 * to conflict with, and omit it for `BarChart`, whose own `aspectRatio`
 * becomes the frame's only height lever.
 */
import type { ReactNode } from "react";
import "./bklit/bklit.css";

export interface BklitFrameProps {
  /** Accessible name — an unlabelled SVG chart reads as nothing. */
  ariaLabel: string;
  /** Omit for BarChart-based children (let `aspectRatio` govern height);
   * pass for PieChart-based children, whose own fixed `size` does not read
   * an ancestor height at all. */
  height?: number;
  children: ReactNode;
}

export default function BklitFrame({ ariaLabel, height, children }: BklitFrameProps) {
  return (
    <div
      className="bklit-frame"
      role="img"
      aria-label={ariaLabel}
      style={{ width: "100%", ...(height !== undefined && { height }) }}
    >
      {children}
    </div>
  );
}
