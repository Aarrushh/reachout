import type { ReactNode } from "react";

import { t } from "../../../i18n/strings";
import type { Lang } from "../../../i18n/strings";

type Confidence = "low" | "medium" | "high";

const CONFIDENCE_KEY = {
  low: "retail.confidence.low",
  medium: "retail.confidence.medium",
  high: "retail.confidence.high",
} as const;

/**
 * The frame every chart sits in: title, confidence chip, chart, caveat.
 *
 * Two things it enforces, both of them honesty rules rather than layout:
 *
 * 1. **The confidence chip and the caveat caption are always rendered**, as
 *    text in the flow. Neither is a tooltip and neither is behind a hover:
 *    a number whose honesty label costs a hover is a number presented as
 *    more certain than it is, and a phone cannot hover at all.
 * 2. **The caveat is the server's string, printed verbatim.** It is a
 *    schema-required field of the validated response, so translating or
 *    rewording it in the browser would put a caption on screen that the
 *    backend never approved.
 *
 * An empty segment is a normal state, not an error (D10, fixture-first): the
 * panel says there is nothing to show yet and still shows its caveat.
 */
export interface ChartPanelProps {
  lang: Lang;
  title: string;
  confidence: Confidence;
  caveat: string;
  /** Empty `points` renders the empty state instead of the chart. */
  isEmpty: boolean;
  children: ReactNode;
}

export default function ChartPanel({
  lang,
  title,
  confidence,
  caveat,
  isEmpty,
  children,
}: ChartPanelProps) {
  return (
    <section className="chart-panel">
      <header className="chart-panel__head">
        <h2 className="chart-panel__title">{title}</h2>
        <span className={`chart-panel__chip chart-panel__chip--${confidence}`}>
          {t(lang, "retail.confidenceLabel", { level: t(lang, CONFIDENCE_KEY[confidence]) })}
        </span>
      </header>

      {isEmpty ? (
        <p className="chart-panel__empty">{t(lang, "retail.chartEmpty")}</p>
      ) : (
        children
      )}

      <p className="chart-panel__caveat">{caveat}</p>
    </section>
  );
}
