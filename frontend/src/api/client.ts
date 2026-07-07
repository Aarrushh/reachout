/**
 * Two typed fetchers over reachout/api/server.py. Nothing else lives here —
 * no caching, no retries (TanStack Query owns that), no visual concerns.
 */
import type { RankedShops } from "../types/RankedShops";
import type { ShopMapGeoJSON } from "../types/MapGeojson";
import type { ShopsGeoJSON } from "../types/ShopsGeojson";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

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
