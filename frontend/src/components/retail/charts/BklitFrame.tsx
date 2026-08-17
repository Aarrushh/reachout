/**
 * The ONLY entry to the chart library (D11, successor to D9's EChart.tsx).
 *
 * Bklit components are vendored source under ./bklit/, and reversing D11 must
 * be a rewrite of this folder and nothing else — so no sibling imports from
 * ./bklit/ except the chart components beside this file, and nothing outside
 * components/retail/charts/ imports any of it.
 *
 * It preserves the two behaviours every panel needs identically, carried
 * over from the ECharts wrapper it replaces:
 *
 * 1. **Charts never animate.** A dashboard that animates on every refetch
 *    draws the eye to motion rather than to the number. Bklit's animations
 *    are JS-driven (motion), so the tokens.css reduced-motion kill switch
 *    cannot reach them — instead, every chart beside this file passes
 *    `animate={false}` / `animationDuration={0}`, and the containment test
 *    greps for it (charts.containment.test.ts).
 * 2. **An accessible name.** Bklit renders an <svg> plus portaled HTML
 *    labels, none of which carries a name — this div is the img.
 */
import type { ReactNode } from "react";
import "./bklit/bklit.css";

export interface BklitFrameProps {
  /** Accessible name — an unlabelled SVG chart reads as nothing. */
  ariaLabel: string;
  height?: number;
  children: ReactNode;
}

export default function BklitFrame({ ariaLabel, height = 240, children }: BklitFrameProps) {
  return (
    <div className="bklit-frame" role="img" aria-label={ariaLabel} style={{ height, width: "100%" }}>
      {children}
    </div>
  );
}
