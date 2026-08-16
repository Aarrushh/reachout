/**
 * The typed fetchers over the two backends and the ApiError they throw.
 * Nothing else lives here — no caching, no retries (TanStack Query owns
 * that, using ApiError.status to skip retrying permanent 4xx), no visuals.
 */
import type { AnalyticsResponse } from "../types/AnalyticsResponse";
import type { PicksResponse } from "../types/PicksResponse";
import type { RankedShops } from "../types/RankedShops";
import type { RisingQuery } from "../types/RisingQuery";
import type { ShopMapGeoJSON } from "../types/MapGeojson";
import type { ShopsGeoJSON } from "../types/ShopsGeojson";

/**
 * The two windows `/demand/api/analytics` (and `/signals`, `/trends`) accept,
 * exactly as `ALLOWED_TIMEFRAMES` in `demand/api/app.py`. Google scales its
 * 0-100 interest index to the requested window, and the ingest pipeline
 * rescales again on top of that — a 3-month reading and a 12-month reading
 * of the same keyword in the same week are different numbers on different
 * scales, never convertible by browser arithmetic. That is why switching
 * this value must always be a new fetch, never a client-side reslice.
 */
export type Timeframe = "today 3-m" | "today 12-m";

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

export interface AnalyticsParams {
  storeId?: string;
  /** Defaults to `"today 3-m"`, matching the server's own default. */
  timeframe?: Timeframe;
}

/**
 * The retail dashboard's one fetch (U3). Everything the three charts draw
 * arrives here already computed — including each segment's confidence label
 * and the caveat — because the browser is not allowed to derive either.
 *
 * `timeframe` only moves `top_movers`: the server deliberately does not
 * apply it to `category_mix` or `stock_out_risk`, which are a census of
 * `public.products` inventory, not a read of search signals.
 */
export async function fetchAnalytics({
  storeId,
  timeframe = "today 3-m",
}: AnalyticsParams = {}): Promise<AnalyticsResponse> {
  const usp = new URLSearchParams({ inventory_type: "convenience_store", timeframe });
  if (storeId) usp.set("store_id", storeId);
  const res = await fetch(`${DEMAND_API_BASE}/demand/api/analytics?${usp.toString()}`);
  if (!res.ok) {
    throw new ApiError(`GET /demand/api/analytics failed: ${res.status}`, res.status);
  }
  return res.json();
}

export interface RisingQueriesParams {
  parentKeyword?: string;
  /** `"commercial"` (server default) or `"all"`, for auditing the tiering heuristic. */
  include?: "commercial" | "all";
  limit?: number;
  /** Row offset for paging; cluster ids are stable across pages. */
  offset?: number;
}

export interface RisingQueriesPage {
  rows: RisingQuery[];
  /**
   * `X-Total-Count`: how many rows survived the server's tier filter,
   * before `offset`/`limit`. Larger than `rows.length` means the panel is
   * holding one page, not the whole set. Falls back to `rows.length` when
   * the header is absent or unparseable — an under-count is safe (the UI
   * simply omits the "of N"), an invented larger number would not be.
   */
  total: number;
}

/**
 * The discovery panel's fetch (U3 follow-up). Unlike `/analytics`, this
 * endpoint's response is a bare array, not an envelope with `segments` — do
 * not assume the two share a shape.
 */
export async function fetchRisingQueries(
  params: RisingQueriesParams = {},
): Promise<RisingQueriesPage> {
  const usp = new URLSearchParams();
  if (params.parentKeyword) usp.set("parent_keyword", params.parentKeyword);
  if (params.include) usp.set("include", params.include);
  if (params.limit !== undefined) usp.set("limit", String(params.limit));
  if (params.offset !== undefined) usp.set("offset", String(params.offset));
  const qs = usp.toString();
  const res = await fetch(`${DEMAND_API_BASE}/demand/api/rising-queries${qs ? `?${qs}` : ""}`);
  if (!res.ok) {
    throw new ApiError(`GET /demand/api/rising-queries failed: ${res.status}`, res.status);
  }
  const rows: RisingQuery[] = await res.json();
  const header = Number(res.headers.get("X-Total-Count"));
  return { rows, total: Number.isFinite(header) && header >= rows.length ? header : rows.length };
}
