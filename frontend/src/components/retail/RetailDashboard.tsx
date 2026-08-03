import { useQuery } from "@tanstack/react-query";

import { fetchAnalytics } from "../../api/client";
import { t } from "../../i18n/strings";
import type { Lang } from "../../i18n/strings";
import CategoryMixChart from "./charts/CategoryMixChart";
import StockOutRiskChart from "./charts/StockOutRiskChart";
import TopMoversChart from "./charts/TopMoversChart";

/**
 * The three charts and the one fetch that feeds them (U3).
 *
 * Loading, error and empty are all first-class states, because
 * empty-but-shaped is the NORMAL response under D10 — the demand service
 * serves a valid document with zero points until a live ingest lands, and a
 * dashboard that treats that as a failure would be crying wolf every day.
 *
 * `generated_from` is surfaced, not swallowed. A fixture response is practice
 * data; showing it unlabelled beside the word "analytics" would be presenting
 * canned numbers as this shop's own.
 */
export default function RetailDashboard({ lang }: { lang: Lang }) {
  const analytics = useQuery({
    queryKey: ["analytics", "convenience_store"],
    queryFn: () => fetchAnalytics(),
  });

  if (analytics.isPending) {
    return <p className="retail-dash__state">{t(lang, "retail.loading")}</p>;
  }

  if (analytics.isError) {
    return (
      <p className="retail-dash__state retail-dash__state--error" role="alert">
        {t(lang, "retail.loadFailed")}
      </p>
    );
  }

  const { caveat, generated_from: source, segments } = analytics.data;

  return (
    <>
      {source === "fixture" && (
        <p className="retail-dash__practice">{t(lang, "retail.practiceData")}</p>
      )}
      <div className="retail-dash__grid">
        <TopMoversChart
          lang={lang}
          confidence={segments.top_movers.confidence}
          caveat={caveat}
          points={segments.top_movers.points}
        />
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
      </div>
    </>
  );
}
