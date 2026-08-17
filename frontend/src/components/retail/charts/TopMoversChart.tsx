import { t } from "../../../i18n/strings";
import type { Lang } from "../../../i18n/strings";
import ChartPanel from "./ChartPanel";
import BklitFrame from "./BklitFrame";
import { BarChart, Bar, BarYAxis, Grid, ChartTooltip } from "./bklit";
import { topMoversView } from "./options";
import type { TopMoverPoint } from "./options";

/**
 * S1 metric 1 — which Madrid search terms moved, and by how much.
 *
 * No fixed height on `BklitFrame` here (see BklitFrame.tsx): `BarChart`
 * sizes itself from `aspectRatio` against its own width, so the frame's
 * height comes from that, not from a wrapper style. `aspectRatio="5 / 4"` is
 * derived from `retail.css`'s `.retail-dash__grid { minmax(300px, 1fr) }` —
 * the one literal "known column width" in the frozen grid CSS — so at that
 * 300px floor the chart renders at exactly 240px tall, matching the
 * predecessor's fixed height. Wider columns render proportionally taller instead
 * of staying pinned at 240; that is the one visible behavioural difference.
 */
export default function TopMoversChart({
  lang, confidence, caveat, points,
}: {
  lang: Lang;
  confidence: "low" | "medium" | "high";
  caveat: string;
  points: TopMoverPoint[];
}) {
  const title = t(lang, "retail.chart.topMovers");
  const view = topMoversView(points);
  return (
    <ChartPanel lang={lang} title={title}
      confidence={confidence} caveat={caveat} isEmpty={points.length === 0}>
      <BklitFrame ariaLabel={title}>
        <BarChart data={view.data} xDataKey="keyword" orientation="horizontal" aspectRatio="5 / 4"
          margin={{ top: 8, right: 16, bottom: 8, left: 80 }} animationDuration={0}>
          <Grid horizontal={false} vertical fadeVertical />
          <Bar dataKey="delta_pct" animate={false} lineCap={4}
            colorAccessor={view.colorAccessor} />
          <BarYAxis showAllLabels />
          <ChartTooltip
            showCrosshair={false}
            rows={(point) => [
              {
                color: view.colorAccessor(point as { direction: TopMoverPoint["direction"] }),
                label: title,
                value: `${point.delta_pct as number}%`,
              },
            ]}
          />
        </BarChart>
      </BklitFrame>
    </ChartPanel>
  );
}
