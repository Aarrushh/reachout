/** Results: split view. URL stays the state of record; this file only adds
 * presentation state (selection, ping sequence) on top of the two queries. */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { fetchAllShops, fetchRankedShops, fetchShopsGeoJSON, type SearchParams } from "../api/client";
import ResultsPanel from "../components/ResultsPanel";
import TopBar from "../components/TopBar";
import { useLang } from "../hooks/useLang";
import type { RankedShops } from "../types/RankedShops";
import "../components/results.css";

export type RankedResult = NonNullable<RankedShops["results"]>[number];

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

  const rankedShops = useQuery({
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
    setSearchParams(next);
  }

  const results = rankedShops.data?.status === "ok" ? rankedShops.data.results ?? [] : [];
  const pingedIds = new Set(results.map((r) => r.shop_id)); // Task 5 replaces with usePingSequence

  return (
    <div className="results-screen">
      <TopBar q={params.q} near={params.near ?? null} radiusKm={radiusKm} lang={lang}
        onSearch={(q) => setParam("q", q)}
        onRadius={(km) => setParam("radius", String(km))}
        onLang={setLang} />
      <div className="split">
        <ResultsPanel query={rankedShops} pingedIds={pingedIds}
          selectedShopId={selectedShopId} onSelect={setSelectedShopId}
          lang={lang} radiusKm={radiusKm}
          onWiden={() => setParam("radius", "5")}
          onRetry={() => { void rankedShops.refetch(); void shopsGeoJSON.refetch(); }} />
        <div className="map-panel" data-allshops={allShops.status} />
      </div>
    </div>
  );
}
