/** Results: split view. URL stays the state of record; this file only adds
 * presentation state (selection, ping sequence) on top of the two queries. */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Navigate, useSearchParams } from "react-router-dom";

import { fetchAllShops, fetchRankedShops, fetchShopsGeoJSON, type SearchParams } from "../api/client";
import MapPanel from "../components/MapPanel";
import ResultsPanel, { type SortMode } from "../components/ResultsPanel";
import TopBar from "../components/TopBar";
import { useLang } from "../hooks/useLang";
import { usePingSequence } from "../hooks/usePingSequence";
import type { RankedShops } from "../types/RankedShops";
import "../components/results.css";

export type RankedResult = NonNullable<RankedShops["results"]>[number];

const SORT_MODES: SortMode[] = ["relevance", "price_asc", "price_desc", "distance"];

// Filter changes reset pagination: stale page numbers point at slices that no
// longer exist after the visible set shrinks.
const PAGE_RESETTERS = new Set(["category", "stock", "sort"]);

function paramsFromUrl(searchParams: URLSearchParams): SearchParams {
  const lat = searchParams.get("lat");
  const lng = searchParams.get("lng");
  const radius = searchParams.get("radius");
  return {
    q: searchParams.get("q") ?? "",
    near: searchParams.get("near") ?? undefined,
    lat: lat !== null ? Number(lat) : undefined,
    lng: lng !== null ? Number(lng) : undefined,
    radius: radius !== null ? Number(radius) : undefined,
  };
}

export default function ResultsRoute() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [lang, setLang] = useLang();
  const [selectedShopId, setSelectedShopId] = useState<string | null>(null);
  const params = paramsFromUrl(searchParams);
  const radiusKm = params.radius ?? 2;
  const enabled = params.q.length > 0;

  // Presentation-only URL params (never join queryKeys or the ping searchKey).
  const rawSort = searchParams.get("sort");
  const sort: SortMode = SORT_MODES.includes(rawSort as SortMode) ? (rawSort as SortMode) : "relevance";
  const category = searchParams.get("category");
  const inStockOnly = searchParams.get("stock") === "1";
  const page = Math.max(1, Number(searchParams.get("page")) || 1);
  const region = searchParams.get("region");

  const rankedShops = useQuery({
    // sort/category/stock/page/region are client-side presentation state and
    // stay OUT of this key; region would join it only if the API ever gains a
    // region param.
    queryKey: ["ranked-shops", params],
    queryFn: () => fetchRankedShops(params),
    enabled,
  });

  const shopsGeoJSON = useQuery({
    queryKey: ["shops-geojson", params],
    queryFn: () => fetchShopsGeoJSON(params),
    enabled,
  });

  const allShops = useQuery({
    queryKey: ["all-shops"],
    queryFn: fetchAllShops,
    staleTime: Infinity,
  });

  function setParam(key: string, value: string) {
    const next = new URLSearchParams(searchParams);
    next.set(key, value);
    if (PAGE_RESETTERS.has(key)) next.delete("page");
    setSearchParams(next);
  }

  function deleteParam(key: string) {
    const next = new URLSearchParams(searchParams);
    next.delete(key);
    if (PAGE_RESETTERS.has(key)) next.delete("page");
    setSearchParams(next);
  }

  // Only the data-bearing params: a lang toggle must not replay the pings.
  const searchKey = [params.q, params.near, params.lat, params.lng, params.radius].join("|");
  const pingedIds = usePingSequence(
    rankedShops.data?.status === "ok" ? rankedShops.data.results : undefined,
    searchKey,
  );

  // Without a query both searches are disabled and would skeleton forever.
  // (After all hooks so the hook order stays stable.)
  if (!enabled) return <Navigate to={lang === "en" ? "/?lang=en" : "/"} replace />;

  return (
    <div className="results-screen">
      <TopBar q={params.q} near={params.near ?? null} radiusKm={radiusKm} lang={lang}
        onSearch={(q) => setParam("q", q)}
        onRadius={(km) => setParam("radius", String(km))}
        onLang={setLang}
        category={category}
        onCategory={(c) => (c ? setParam("category", c) : deleteParam("category"))} />
      <div className="split">
        <ResultsPanel query={rankedShops} pingedIds={pingedIds}
          selectedShopId={selectedShopId} onSelect={setSelectedShopId}
          lang={lang} radiusKm={radiusKm}
          onWiden={() => setParam("radius", "5")}
          onRetry={() => { void rankedShops.refetch(); void shopsGeoJSON.refetch(); void allShops.refetch(); }}
          sort={sort} onSort={(s) => setParam("sort", s)}
          category={category}
          onCategory={(c) => (c ? setParam("category", c) : deleteParam("category"))}
          inStockOnly={inStockOnly}
          onInStockOnly={(v) => (v ? setParam("stock", "1") : deleteParam("stock"))}
          page={page} onPage={(p) => setParam("page", String(p))} />
        <MapPanel matched={shopsGeoJSON.data} network={allShops.data}
          pingedIds={pingedIds} selectedShopId={selectedShopId} onSelect={setSelectedShopId} lang={lang}
          region={region}
          onRegion={(r) => (r ? setParam("region", r) : deleteParam("region"))}
          networkCount={allShops.data?.metadata.shop_count ?? 0} />
      </div>
    </div>
  );
}
