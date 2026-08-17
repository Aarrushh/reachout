import { useQuery } from "@tanstack/react-query";

import { fetchRecommendations } from "../../api/client";
import { t } from "../../i18n/strings";
import type { Lang } from "../../i18n/strings";
import ChartPanel from "./charts/ChartPanel";
import type { RecommendationsResponse } from "../../types/RecommendationsResponse";

type Recommendation = RecommendationsResponse["recommendations"][number];

const ACTION_KEY = {
  stock_up: "retail.recommendations.action.stockUp",
  feature_in_window: "retail.recommendations.action.feature",
  watch: "retail.recommendations.action.watch",
} as const;

/**
 * The most actionable data in the system, on screen for the first time:
 * `/demand/api/recommendations`, until now 1,541 rows feeding zero pixels.
 *
 * Honesty rules, inherited from the folder it sits beside:
 * - Confidence is PER ROW (the schema carries it per recommendation), so
 *   each card wears its own chip — never one badge for the panel.
 * - Every distinct `caveat` string in the payload is printed verbatim in the
 *   panel footer. Today the canonical text is one string; if the server ever
 *   sends two, both appear, because deduplication may drop repetition but
 *   must never drop a sentence the backend approved.
 * - `headline`/`body` are server text, shown as sent, never translated.
 * - The count line states how many rows are shown. The endpoint sends no
 *   X-Total-Count, so no "of N" is invented (an optional backend task adds
 *   the header; the copy upgrades to shownPartial only when it exists).
 */
export default function RecommendationsPanel({ lang }: { lang: Lang }) {
  const recs = useQuery({
    queryKey: ["recommendations"],
    queryFn: () => fetchRecommendations(),
  });

  const title = t(lang, "retail.chart.recommendations");

  if (recs.isPending) {
    return (
      <ChartPanel lang={lang} title={title} caveat="" isEmpty={false}>
        <p className="retail-dash__state">{t(lang, "retail.loading")}</p>
      </ChartPanel>
    );
  }

  if (recs.isError) {
    return (
      <ChartPanel lang={lang} title={title} caveat="" isEmpty={false}>
        <p className="retail-dash__state retail-dash__state--error" role="alert">
          {t(lang, "retail.loadFailed")}
        </p>
      </ChartPanel>
    );
  }

  const rows = recs.data.recommendations;
  const caveats = [...new Set(rows.map((r) => r.caveat))].join(" ");

  return (
    <ChartPanel
      lang={lang}
      title={title}
      eyebrow={t(lang, "retail.provenance.search")}
      caveat={caveats}
      isEmpty={rows.length === 0}
    >
      <p className="recommendations__count-line">
        {t(lang, "retail.recommendations.shown", { count: rows.length })}
      </p>
      <ul className="recommendations__list">
        {rows.map((r: Recommendation) => (
          <li key={r.id} className={`recommendations__row recommendations__row--${r.action}`}>
            <div className="recommendations__row-head">
              <span className="recommendations__action microcaps">
                {t(lang, ACTION_KEY[r.action])}
              </span>
              <span className={`chart-panel__chip chart-panel__chip--${r.confidence}`}>
                {t(lang, "retail.confidenceLabel", {
                  level: t(lang, `retail.confidence.${r.confidence}` as const),
                })}
              </span>
            </div>
            <p className="recommendations__headline">{r.headline}</p>
            <p className="recommendations__body">{r.body}</p>
          </li>
        ))}
      </ul>
    </ChartPanel>
  );
}
