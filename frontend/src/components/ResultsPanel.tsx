import type { UseQueryResult } from "@tanstack/react-query";

import ShopCard from "./ShopCard";
import { t, type Lang } from "../i18n/strings";
import type { RankedShops } from "../types/RankedShops";
import type { RankedResult } from "../routes/results";

interface Props {
  query: UseQueryResult<RankedShops>;
  pingedIds: Set<string>;
  selectedShopId: string | null;
  onSelect: (id: string | null) => void;
  lang: Lang;
  radiusKm: number;
  onWiden: () => void;
  onRetry: () => void;
}

export default function ResultsPanel({ query, pingedIds, selectedShopId, onSelect, lang, radiusKm, onWiden, onRetry }: Props) {
  const { data, isPending, isError, error } = query;

  if (isPending) {
    return (
      <div className="results-panel">
        <p className="results-meta microcaps">{t(lang, "results.loading")}</p>
        {Array.from({ length: 5 }, (_, i) => <div key={i} className="skeleton-card" />)}
      </div>
    );
  }

  if (isError || data.status !== "ok") {
    const detail = isError ? (error as Error).message : JSON.stringify(data.error ?? data.missing_fields);
    return (
      <div className="results-panel state">
        <p>{t(lang, "results.error")}</p>
        <p className="mono error-detail">{detail}</p>
        <button className="cta" onClick={onRetry}>{t(lang, "results.retry")}</button>
      </div>
    );
  }

  const results: RankedResult[] = data.results ?? [];
  if (results.length === 0) {
    return (
      <div className="results-panel state">
        <p>{t(lang, "results.empty", { r: radiusKm })}</p>
        {radiusKm < 5 && <button className="cta" onClick={onWiden}>{t(lang, "results.widen")}</button>}
      </div>
    );
  }

  const generatedAt = data.generated_at ? new Date(data.generated_at).toLocaleTimeString("es-ES") : "";
  return (
    <div className="results-panel">
      <p className="results-meta microcaps">
        {results.length} {t(lang, results.length === 1 ? "results.shop" : "results.shops")} · {radiusKm} km · <span className="mono">{generatedAt}</span>
      </p>
      {results.map((r) => (
        <ShopCard key={r.shop_id} result={r} lang={lang}
          pinged={pingedIds.has(r.shop_id)}
          selected={selectedShopId === r.shop_id}
          onSelect={onSelect} />
      ))}
    </div>
  );
}
