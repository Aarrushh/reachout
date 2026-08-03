import { t } from "../../../i18n/strings";
import type { Lang } from "../../../i18n/strings";
import ChartPanel from "./ChartPanel";
import EChart from "./EChart";
import { categoryMixOption } from "./options";
import type { CategoryMixPoint } from "./options";

/** S1 metric 2 — how the shelves split across categories. */
export default function CategoryMixChart({
  lang,
  confidence,
  caveat,
  points,
}: {
  lang: Lang;
  confidence: "low" | "medium" | "high";
  caveat: string;
  points: CategoryMixPoint[];
}) {
  const title = t(lang, "retail.chart.categoryMix");
  return (
    <ChartPanel lang={lang} title={title} confidence={confidence} caveat={caveat} isEmpty={points.length === 0}>
      <EChart option={categoryMixOption(points)} ariaLabel={title} />
    </ChartPanel>
  );
}
