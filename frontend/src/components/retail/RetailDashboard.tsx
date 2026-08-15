import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { fetchAnalytics } from "../../api/client";
import type { Timeframe } from "../../api/client";
import { t } from "../../i18n/strings";
import type { Lang } from "../../i18n/strings";
import CategoryMixChart from "./charts/CategoryMixChart";
import StockOutRiskChart from "./charts/StockOutRiskChart";
import TopMoversChart from "./charts/TopMoversChart";
import RisingQueriesPanel from "./RisingQueriesPanel";
import TimeframeToggle from "./TimeframeToggle";

/**
 * The three charts and the one fetch that feeds them (U3), plus the
 * timeframe toggle and discovery panel added in task 4.
 *
 * Loading, error and empty are all first-class states, because
 * empty-but-shaped is the NORMAL response under D10 — the demand service
 * serves a valid document with zero points until a live ingest lands, and a
 * dashboard that treats that as a failure would be crying wolf every day.
 *
 * `generated_from` is surfaced, not swallowed. A fixture response is practice
 * data; showing it unlabelled beside the word "analytics" would be presenting
 * canned numbers as this shop's own.
 *
 * `timeframe` lives in `queryKey`, not in a client-side reslice: Google
 * scales its interest index to the requested window and the ingest pipeline
 * rescales again on top of that, so a 3-month reading and a 12-month reading
 * of the same keyword are different numbers on different scales. Switching
 * the toggle must always be a new fetch.
 *
 * `placeholderData: keepPreviousData` matters as much as the queryKey does:
 * without it, a new `timeframe` means a brand new query with no cached
 * data, `analytics.isPending` goes true, and the early-return loading text
 * below would unmount `CategoryMixChart`, `StockOutRiskChart` and
 * `RisingQueriesPanel` too — a full-page blank-and-reload that reads as
 * "everything changed" far louder than the toggle's own caption reads as
 * "nothing changed." With it, `category_mix` and `stock_out_risk` (which
 * the server does not filter by timeframe at all) stay on screen showing
 * their last-known values while only the movers column indicates a fetch
 * is in flight, and the loading text is reserved for the one case it
 * actually describes: no data has ever arrived yet.
 */
export default function RetailDashboard({ lang }: { lang: Lang }) {
  const [timeframe, setTimeframe] = useState<Timeframe>("today 3-m");

  const analytics = useQuery({
    queryKey: ["analytics", "convenience_store", timeframe],
    queryFn: () => fetchAnalytics({ timeframe }),
    placeholderData: keepPreviousData,
  });

  if (analytics.isFetching && !analytics.data) {
    return <p className="retail-dash__state">{t(lang, "retail.loading")}</p>;
  }

  if (analytics.isError) {
    return (
      <p className="retail-dash__state retail-dash__state--error" role="alert">
        {t(lang, "retail.loadFailed")}
      </p>
    );
  }

  if (!analytics.data) {
    // Unreachable in practice (isFetching-with-no-data and isError are both
    // handled above), but keeps the destructure below from widening
    // `analytics.data` back to possibly-undefined.
    return null;
  }

  const { caveat, generated_from: source, segments } = analytics.data;

  return (
    <>
      {source === "fixture" && (
        <p className="retail-dash__practice">{t(lang, "retail.practiceData")}</p>
      )}
      <div className="retail-dash__grid">
        {/*
          The toggle sits inside the movers column, above that one chart,
          rather than above the whole grid: category_mix and stock_out_risk
          are a census of inventory and are timeframe-independent, and a
          toggle floating above all three would make it look like it
          rescales them too.
        */}
        <div className="retail-dash__movers-col">
          <TimeframeToggle lang={lang} timeframe={timeframe} onChange={setTimeframe} />
          {analytics.isFetching && (
            <p className="timeframe-toggle__updating" role="status">
              {t(lang, "retail.timeframe.updating")}
            </p>
          )}
          <TopMoversChart
            lang={lang}
            confidence={segments.top_movers.confidence}
            caveat={caveat}
            points={segments.top_movers.points}
          />
        </div>
        <CategoryMixChart
          lang={lang}
          confidence={segments.category_mix.confidence}
          caveat={caveat}
          points={segments.category_mix.points}
        />
        <StockOutRiskChart
          lang={lang}
          confidence={segments.stock_out_risk.confidence}
          caveat={caveat}
          points={segments.stock_out_risk.points}
        />
        <RisingQueriesPanel lang={lang} />
      </div>
    </>
  );
}
