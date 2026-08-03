/**
 * The typed fetchers over the two backends and the ApiError they throw.
 * Nothing else lives here — no caching, no retries (TanStack Query owns
 * that, using ApiError.status to skip retrying permanent 4xx), no visuals.
 */
import type { AnalyticsResponse } from "../types/AnalyticsResponse";
import type { PicksResponse } from "../types/PicksResponse";
import type { RankedShops } from "../types/RankedShops";
import type { ShopMapGeoJSON } from "../types/MapGeojson";
import type { ShopsGeoJSON } from "../types/ShopsGeojson";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

// The demand service is a separate FastAPI app on its own port (D2), not a
// path under the shopper API. Two bases, because they are two deployments.
const DEMAND_API_BASE = import.meta.env.VITE_DEMAND_API_BASE ?? "http://localhost:8001";

/** Fetch error carrying the HTTP status so callers can skip retries on 4xx. */
export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

export interface SearchParams {
  q: string;
  near?: string;
  lat?: number;
  lng?: number;
  radius?: number;
}

function buildQueryString(params: SearchParams): string {
  const usp = new URLSearchParams();
  usp.set("q", params.q);
  if (params.near) usp.set("near", params.near);
  if (params.lat !== undefined) usp.set("lat", String(params.lat));
  if (params.lng !== undefined) usp.set("lng", String(params.lng));
  if (params.radius !== undefined) usp.set("radius", String(params.radius));
  return usp.toString();
}

export async function fetchRankedShops(params: SearchParams): Promise<RankedShops> {
  const res = await fetch(`${API_BASE}/api/search?${buildQueryString(params)}`);
  if (!res.ok) throw new ApiError(`GET /api/search failed: ${res.status}`, res.status);
  return res.json();
}

export async function fetchShopsGeoJSON(params: SearchParams): Promise<ShopMapGeoJSON> {
  const res = await fetch(`${API_BASE}/api/search.geojson?${buildQueryString(params)}`);
  if (!res.ok) throw new ApiError(`GET /api/search.geojson failed: ${res.status}`, res.status);
  return res.json();
}

export async function fetchAllShops(): Promise<ShopsGeoJSON> {
  const res = await fetch(`${API_BASE}/api/shops.geojson`);
  if (!res.ok) throw new ApiError(`GET /api/shops.geojson failed: ${res.status}`, res.status);
  return res.json();
}

/**
 * The consumer landing page's "picks for you" rail (U4). `generated_by` is a
 * const `"deterministic"` in the schema — these are ranked by store rating
 * and round-robined across categories in pure Python, not recommended by a
 * model, and nothing in the UI may imply otherwise.
 */
export async function fetchPicks(neighbourhood?: string | null): Promise<PicksResponse> {
  const usp = new URLSearchParams();
  if (neighbourhood) usp.set("neighbourhood", neighbourhood);
  const qs = usp.toString();
  const res = await fetch(`${API_BASE}/api/picks${qs ? `?${qs}` : ""}`);
  if (!res.ok) throw new ApiError(`GET /api/picks failed: ${res.status}`, res.status);
  return res.json();
}

/**
 * The retail dashboard's one fetch (U3). Everything the three charts draw
 * arrives here already computed — including each segment's confidence label
 * and the caveat — because the browser is not allowed to derive either.
 */
export async function fetchAnalytics(storeId?: string): Promise<AnalyticsResponse> {
  const usp = new URLSearchParams({ inventory_type: "convenience_store" });
  if (storeId) usp.set("store_id", storeId);
  const res = await fetch(`${DEMAND_API_BASE}/demand/api/analytics?${usp.toString()}`);
  if (!res.ok) {
    throw new ApiError(`GET /demand/api/analytics failed: ${res.status}`, res.status);
  }
  return res.json();
}
