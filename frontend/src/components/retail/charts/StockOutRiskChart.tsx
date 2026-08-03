import { t } from "../../../i18n/strings";
import type { Lang } from "../../../i18n/strings";
import ChartPanel from "./ChartPanel";
import EChart from "./EChart";
import { stockOutRiskOption } from "./options";
import type { StockOutRiskPoint } from "./options";

/** S1 metric 3 — the share of each category's products running low. */
export default function StockOutRiskChart({
  lang,
  confidence,
  caveat,
  points,
}: {
  lang: Lang;
  confidence: "low" | "medium" | "high";
  caveat: string;
  points: StockOutRiskPoint[];
}) {
  const title = t(lang, "retail.chart.stockOutRisk");
  return (
    <ChartPanel lang={lang} title={title} confidence={confidence} caveat={caveat} isEmpty={points.length === 0}>
      <EChart option={stockOutRiskOption(points)} ariaLabel={title} />
    </ChartPanel>
  );
}
