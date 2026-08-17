import { t } from "../../../i18n/strings";
import type { Lang } from "../../../i18n/strings";
import ChartPanel from "./ChartPanel";
import BklitFrame from "./BklitFrame";
import { PieChart, PieSlice, Legend } from "./bklit";
// The top-level barrel (./bklit) re-exports `Legend` but not its item
// subcomponents (docs/IMPLEMENTATION_PLAN_V3.md §3's barrel list is A1's
// vendored index.ts, which this task does not edit) — `Legend` requires a
// single `LegendItem` child to clone per row, so those come from the
// (also vendored, also unedited) nested legend barrel instead.
import { LegendItem, LegendMarker, LegendLabel, LegendValue } from "./bklit/legend";
import { categoryMixView } from "./options";
import type { CategoryMixPoint } from "./options";

/**
 * S1 metric 2 — how the shelves split across categories.
 *
 * Donut geometry: wrapper height 240 → `size={200}`; the predecessor's radii
 * `["45%","70%"]` are a 0.64 inner/outer ratio, so `innerRadius={64}` against
 * the 100px outer radius — layout constants, not data arithmetic.
 * `PieChart`'s `size` prop is a fixed pixel box that never reads an
 * ancestor's height, so `BklitFrame`'s fixed `height={240}` (see
 * BklitFrame.tsx) has nothing to conflict with here, unlike the two
 * `BarChart`-based charts beside this file.
 */
export default function CategoryMixChart({
  lang, confidence, caveat, points,
}: {
  lang: Lang;
  confidence: "low" | "medium" | "high";
  caveat: string;
  points: CategoryMixPoint[];
}) {
  const title = t(lang, "retail.chart.categoryMix");
  const view = categoryMixView(points);
  return (
    <ChartPanel lang={lang} title={title}
      confidence={confidence} caveat={caveat} isEmpty={points.length === 0}>
      <BklitFrame ariaLabel={title} height={240}>
        {/* No PieCenter on purpose: the predecessor's donut had labels off and
            no centre figure, and inventing a "Total" of share percentages would
            be browser arithmetic. */}
        <PieChart data={view.data} size={200} innerRadius={64}>
          {view.data.map((item, index) => (
            <PieSlice key={item.label} index={index} animate={false} />
          ))}
        </PieChart>
      </BklitFrame>
      {/* Legend below the chart, as before. Bklit's Legend takes a single
          LegendItem child that it clones per item — the swatch, label and
          server's share_pct value are the item's own already-validated
          fields, nothing recomputed. */}
      <Legend items={view.data} className="chart-legend">
        <LegendItem>
          <LegendMarker />
          <LegendLabel />
          <LegendValue formatValue={(v) => `${v}%`} />
        </LegendItem>
      </Legend>
    </ChartPanel>
  );
}
