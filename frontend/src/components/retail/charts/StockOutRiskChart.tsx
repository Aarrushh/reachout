import { t } from "../../../i18n/strings";
import type { Lang } from "../../../i18n/strings";
import ChartPanel from "./ChartPanel";
import BklitFrame from "./BklitFrame";
import { BarChart, Bar, BarXAxis, Grid, ChartTooltip } from "./bklit";
import { stockOutRiskView } from "./options";
import type { StockOutRiskPoint } from "./options";

/**
 * S1 metric 3 — the share of each category's products running low.
 *
 * Flat fill per decision 4 — the §3.2 snippet's `LinearGradient` is
 * deliberately not used. Vertical orientation, so `domainMax={100}` travels
 * through the patched `buildYScalesForLines` in `y-axis-scales.ts` (A1's
 * third P2 file) rather than `BarChart`'s top-level `valueScale` — verified
 * against `bklit-patches.test.tsx`'s P2 acceptance tests, which pin a
 * `risk_pct=40` datum to a 48px-tall bar (40/100 of the 120px inner height)
 * instead of the un-pinned `40/(40*1.1)≈109px` a `.nice()`-derived axis top
 * would give.
 *
 * No fixed height on `BklitFrame` here, for the same reason as
 * `TopMoversChart`: see BklitFrame.tsx and its `aspectRatio="5 / 4"` note.
 */
export default function StockOutRiskChart({
  lang, confidence, caveat, points,
}: {
  lang: Lang;
  confidence: "low" | "medium" | "high";
  caveat: string;
  points: StockOutRiskPoint[];
}) {
  const title = t(lang, "retail.chart.stockOutRisk");
  const view = stockOutRiskView(points);
  return (
    <ChartPanel lang={lang} title={title} eyebrow={t(lang, "retail.provenance.inventory")}
      confidence={confidence} caveat={caveat} isEmpty={points.length === 0}>
      <BklitFrame ariaLabel={title}>
        <BarChart data={view.data} xDataKey="category" domainMax={view.domainMax} aspectRatio="5 / 4"
          margin={{ top: 16, right: 16, bottom: 8, left: 8 }} animationDuration={0}>
          <Grid horizontal />
          <Bar dataKey="risk_pct" animate={false} fill={view.fill} lineCap={4} />
          <BarXAxis showAllLabels />
          <ChartTooltip
            rows={(point) => [
              { color: view.fill, label: title, value: `${point.risk_pct as number}%` },
            ]}
          />
        </BarChart>
      </BklitFrame>
    </ChartPanel>
  );
}
