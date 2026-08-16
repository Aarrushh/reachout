import { t } from "../../i18n/strings";
import type { Lang } from "../../i18n/strings";
import type { Timeframe } from "../../api/client";

const OPTIONS: { value: Timeframe; key: "retail.timeframe.3m" | "retail.timeframe.12m" }[] = [
  { value: "today 3-m", key: "retail.timeframe.3m" },
  { value: "today 12-m", key: "retail.timeframe.12m" },
];

/**
 * Requirement 2 (task-4): the 3-month / 12-month switch for the top movers
 * chart only.
 *
 * Selecting an option must never reslice numbers already in memory — Google
 * scales its interest index to the requested window and the ingest pipeline
 * rescales again on top of that, so `RetailDashboard` puts `timeframe` in
 * the TanStack Query `queryKey` and this component only ever reports the
 * chosen value up through `onChange`. It holds no fetch of its own.
 *
 * The caption underneath is not decoration: `category_mix` and
 * `stock_out_risk` are a census of inventory and do not move with this
 * control, and this component is also placed inside the movers column
 * (see `RetailDashboard.tsx`) rather than above the whole grid, so nothing
 * about its position suggests it touches the other two charts.
 */
export default function TimeframeToggle({
  lang,
  timeframe,
  onChange,
}: {
  lang: Lang;
  timeframe: Timeframe;
  onChange: (timeframe: Timeframe) => void;
}) {
  return (
    <div className="timeframe-toggle">
      <div
        className="timeframe-toggle__buttons"
        role="group"
        aria-label={t(lang, "retail.timeframe.label")}
      >
        {OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            className="timeframe-toggle__button"
            aria-pressed={timeframe === opt.value}
            onClick={() => onChange(opt.value)}
          >
            {t(lang, opt.key)}
          </button>
        ))}
      </div>
      <p className="timeframe-toggle__caption">{t(lang, "retail.timeframe.caption")}</p>
      <p className="retail-dash__explainer">{t(lang, "retail.timeframe.explainer")}</p>
      <p className="retail-dash__explainer">{t(lang, "retail.index.explainer")}</p>
    </div>
  );
}
