import { useQuery } from "@tanstack/react-query";

import { fetchRisingQueries } from "../../api/client";
import { t } from "../../i18n/strings";
import type { Lang } from "../../i18n/strings";
import ChartPanel from "./charts/ChartPanel";
import { groupRisingQueries } from "./risingQueries";

/**
 * Requirement 3 (task-4): Madrid's rising search queries, clustered so
 * near-duplicate phrasings collapse into one card, rendered inside a
 * `ChartPanel` like the three analytics charts.
 *
 * Two things make this panel different from the others in this folder:
 *
 * 1. It has its own fetch and its own `useQuery` — `/demand/api/rising-
 *    queries` is a separate endpoint from `/demand/api/analytics`, is not
 *    part of `AnalyticsResponse`, and does not take `timeframe`.
 * 2. It has no `confidence` to show — the endpoint carries none, so the
 *    `confidence` prop to `ChartPanel` is left unset rather than guessed.
 *    It does carry its own caveat text, since the server supplies none:
 *    these are search-interest signals about products the shop may not
 *    even stock, not this shop's sales.
 *
 * **The honesty rule**: `is_breakout: true` means Google refused to
 * quantify growth. That row (or a cluster containing one) renders the
 * "Breakout" label and never a number — not `0`, not `"0%"`, not a
 * quantified sibling's percentage standing in for it.
 */
export default function RisingQueriesPanel({ lang }: { lang: Lang }) {
  const rising = useQuery({
    queryKey: ["rising-queries"],
    queryFn: () => fetchRisingQueries(),
  });

  const title = t(lang, "retail.chart.risingQueries");
  const caveat = t(lang, "retail.risingQueries.caveat");

  if (rising.isPending) {
    return (
      <ChartPanel lang={lang} title={title} caveat={caveat} isEmpty={false}>
        <p className="retail-dash__state">{t(lang, "retail.loading")}</p>
      </ChartPanel>
    );
  }

  if (rising.isError) {
    return (
      <ChartPanel lang={lang} title={title} caveat={caveat} isEmpty={false}>
        <p className="retail-dash__state retail-dash__state--error" role="alert">
          {t(lang, "retail.loadFailed")}
        </p>
      </ChartPanel>
    );
  }

  const clusters = groupRisingQueries(rising.data);

  return (
    <ChartPanel lang={lang} title={title} caveat={caveat} isEmpty={clusters.length === 0}>
      <ul className="rising-queries__list">
        {clusters.map((cluster) => (
          <li key={cluster.clusterId} className="rising-queries__row">
            <div className="rising-queries__row-main">
              <span className="rising-queries__query">{cluster.query}</span>
              <span className="rising-queries__parent">
                {t(lang, "retail.risingQueries.underParent", { parent: cluster.parentKeyword })}
              </span>
            </div>
            <div className="rising-queries__row-meta">
              {cluster.size > 1 && (
                <span className="rising-queries__count">
                  {t(lang, "retail.risingQueries.clusterSize", { n: cluster.size })}
                </span>
              )}
              {cluster.isBreakout || cluster.growthPct === null ? (
                <span className="rising-queries__growth rising-queries__growth--breakout">
                  {t(lang, "retail.risingQueries.breakout")}
                </span>
              ) : (
                <span className="rising-queries__growth">
                  {t(lang, "retail.risingQueries.growth", { pct: cluster.growthPct })}
                </span>
              )}
            </div>
          </li>
        ))}
      </ul>
    </ChartPanel>
  );
}
