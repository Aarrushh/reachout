import { t } from "../../../i18n/strings";
import type { Lang } from "../../../i18n/strings";
import ChartPanel from "./ChartPanel";
import EChart from "./EChart";
import { topMoversOption } from "./options";
import type { TopMoverPoint } from "./options";

/** S1 metric 1 — which Madrid search terms moved, and by how much. */
export default function TopMoversChart({
  lang,
  confidence,
  caveat,
  points,
}: {
  lang: Lang;
  confidence: "low" | "medium" | "high";
  caveat: string;
  points: TopMoverPoint[];
}) {
  const title = t(lang, "retail.chart.topMovers");
  return (
    <ChartPanel lang={lang} title={title} confidence={confidence} caveat={caveat} isEmpty={points.length === 0}>
      <EChart option={topMoversOption(points)} ariaLabel={title} />
    </ChartPanel>
  );
}
