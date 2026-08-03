import { useEffect, useMemo, useRef } from "react";
import type { UseQueryResult } from "@tanstack/react-query";

import ShopCard, { CATEGORY_ICONS } from "./ShopCard";
import { monoNums } from "../../lib/monoNums";
import { CATEGORIES } from "./TopBar";
import { t, type Lang, type StringKey } from "../../i18n/strings";
import type { RankedShops } from "../../types/RankedShops";
import type { RankedResult } from "../../routes/results";

export type SortMode = "relevance" | "price_asc" | "price_desc" | "distance";

const PAGE_SIZE = 10;
const SORT_KEYS: Record<SortMode, StringKey> = {
  relevance: "sort.relevance",
  price_asc: "sort.priceAsc",
  price_desc: "sort.priceDesc",
  distance: "sort.distance",
};

interface Props {
  query: UseQueryResult<RankedShops>;
  pingedIds: Set<string>;
  selectedShopId: string | null;
  onSelect: (id: string | null) => void;
  lang: Lang;
  radiusKm: number;
  onWiden: () => void;
  onRetry: () => void;
  sort: SortMode;
  onSort: (s: SortMode) => void;
  category: string | null;
  onCategory: (c: string | null) => void;
  inStockOnly: boolean;
  onInStockOnly: (v: boolean) => void;
  page: number;
  onPage: (p: number) => void;
  onChat: (r: RankedResult) => void;
}

export default function ResultsPanel({
  query, pingedIds, selectedShopId, onSelect, lang, radiusKm, onWiden, onRetry,
  sort, onSort, category, onCategory, inStockOnly, onInStockOnly, page, onPage, onChat,
}: Props) {
  const { data, isPending, isError, error } = query;
  const panelRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    panelRef.current?.scrollTo({ top: 0 });
  }, [page]);

  const results: RankedResult[] = useMemo(
    () => (data?.status === "ok" ? data.results ?? [] : []),
    [data],
  );

  // Client-side is correct here: the API returns the full ranked set for the
  // radius, so sort/filter/page never refetch.
  const filtered = useMemo(() => {
    let out = results;
    if (category) out = out.filter((r) => r.category === category);
    if (inStockOnly) out = out.filter((r) => r.stock_qty > 5);
    switch (sort) {
      case "price_asc": out = [...out].sort((a, b) => a.price - b.price); break;
      case "price_desc": out = [...out].sort((a, b) => b.price - a.price); break;
      case "distance": out = [...out].sort((a, b) => a.distance_km - b.distance_km); break;
      case "relevance": out = [...out].sort((a, b) => a.rank - b.rank); break;
    }
    return out;
  }, [results, category, inStockOnly, sort]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(Math.max(1, page), totalPages);
  const pageSlice = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

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

  if (results.length === 0) {
    return (
      <div className="results-panel state">
        <p>{monoNums(t(lang, "results.empty", { r: radiusKm }))}</p>
        {radiusKm < 5 && <button className="cta" onClick={onWiden}>{t(lang, "results.widen")}</button>}
      </div>
    );
  }

  const generatedAt = data.generated_at ? new Date(data.generated_at).toLocaleTimeString("es-ES") : "";
  return (
    <div className="results-panel" ref={panelRef}>
      <div className="results-header">
        <h2 className="results-count">
          {monoNums(t(lang, "results.count", { n: filtered.length, q: data.query ?? "" }))}
        </h2>
        <label className="sort-select">
          <span className="microcaps">{t(lang, "sort.label")}</span>
          <select value={sort} onChange={(e) => onSort(e.target.value as SortMode)}>
            {(Object.keys(SORT_KEYS) as SortMode[]).map((s) => (
              <option key={s} value={s}>{t(lang, SORT_KEYS[s])}</option>
            ))}
          </select>
        </label>
      </div>
      <p className="results-meta microcaps">
        <span className="mono">{radiusKm} km</span> · <span className="mono">{generatedAt}</span>
      </p>
      <div className="results-body">
        <aside className="filter-rail">
          <p className="microcaps filter-title">{t(lang, "filter.title")}</p>
          <p className="microcaps filter-sub">{t(lang, "filter.category")}</p>
          <ul className="filter-cats">
            {CATEGORIES.map((c) => (
              <li key={c}>
                <label>
                  <input type="checkbox" checked={category === c}
                    onChange={() => onCategory(category === c ? null : c)} />
                  <span aria-hidden="true">{CATEGORY_ICONS[c]}</span> {t(lang, `nav.cat.${c}` as StringKey)}
                </label>
              </li>
            ))}
          </ul>
          <label className="filter-stock">
            <input type="checkbox" checked={inStockOnly}
              onChange={(e) => onInStockOnly(e.target.checked)} />
            {t(lang, "filter.inStockOnly")}
          </label>
        </aside>
        <div className="card-column">
          {pageSlice.map((r) => (
            <ShopCard key={r.shop_id} result={r} lang={lang}
              pinged={pingedIds.has(r.shop_id)}
              selected={selectedShopId === r.shop_id}
              onSelect={onSelect} onChat={onChat} />
          ))}
          <nav className="pagination" aria-label={t(lang, "page.of", { p: safePage, total: totalPages })}>
            <button disabled={safePage <= 1} onClick={() => onPage(safePage - 1)}>
              {t(lang, "page.prev")}
            </button>
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
              <button key={p} className={`mono${p === safePage ? " current" : ""}`}
                disabled={p === safePage} onClick={() => onPage(p)}>
                {p}
              </button>
            ))}
            <button disabled={safePage >= totalPages} onClick={() => onPage(safePage + 1)}>
              {t(lang, "page.next")}
            </button>
          </nav>
        </div>
      </div>
    </div>
  );
}
