import { useQuery } from "@tanstack/react-query";

import { fetchRisingQueries } from "../../api/client";
import { t } from "../../i18n/strings";
import type { Lang } from "../../i18n/strings";
import ChartPanel from "./charts/ChartPanel";
import { groupRisingQueries } from "./risingQueries";

/**
 * Mirrors `RISING_QUERIES_MAX_LIMIT` in `demand/api/app.py` — this route's
 * own ceiling, deliberately above the shared `MAX_PAGE_SIZE = 500` the
 * other list endpoints use. 580 of the 658 live rows tier `commercial`
 * (measured 2026-08-16), so the old 500 hid 80 of them. When the table
 * outgrows 1000, the server's
 * `X-Total-Count` says so and the caption below reports it honestly
 * instead of implying completeness.
 */
const RISING_QUERIES_LIMIT = 1000;

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
    queryFn: () => fetchRisingQueries({ limit: RISING_QUERIES_LIMIT }),
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

  const rowCount = rising.data.rows.length;
  const total = rising.data.total;
  const partial = total > rowCount;
  const clusters = groupRisingQueries(rising.data.rows);

  return (
    <ChartPanel lang={lang} title={title} caveat={caveat} isEmpty={clusters.length === 0}>
      {/*
        Never let this panel imply it shows every rising query in Madrid —
        state the exact count, and when the server's `X-Total-Count` says it
        holds more than this page carries, say "of N" instead of a bare
        number that would read like a complete list.
      */}
      <p className="rising-queries__count-line">
        {partial
          ? t(lang, "retail.risingQueries.shownPartial", { count: rowCount, total })
          : t(lang, "retail.risingQueries.shown", { count: rowCount })}
      </p>
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
              {/*
                `growthPct === null` is redundant with `isBreakout` today —
                `groupRisingQueries` sets one from the other — but it stays
                as a deliberate belt-and-suspenders check: if that function
                ever changes, this is the line that stops a null from
                silently reaching the non-breakout branch below and
                rendering as a fabricated number. Do not simplify to just
                `cluster.isBreakout`.
              */}
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
