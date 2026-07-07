/**
 * Route module: fires the two search queries keyed on URL params. No
 * visuals, no layout. Visual design is a separate future phase.
 */
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { fetchRankedShops, fetchShopsGeoJSON, type SearchParams } from "../api/client";

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
  const [searchParams] = useSearchParams();
  const params = paramsFromUrl(searchParams);
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

  return (
    <pre>
      {JSON.stringify({ rankedShops: rankedShops.data, shopsGeoJSON: shopsGeoJSON.data }, null, 2)}
    </pre>
  );
}
