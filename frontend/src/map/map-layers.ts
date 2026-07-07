/** Pure GeoJSON builders for the map's derived layers. No maplibre imports —
 * unit-testable in jsdom. */
import type { ShopMapGeoJSON } from "../types/MapGeojson";

export interface Center { lat: number; lng: number }

export function pingLinesFC(center: Center, matched: ShopMapGeoJSON, pingedIds: Set<string>): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: matched.features
      .filter((f) => pingedIds.has(f.properties.shop_id))
      .map((f) => ({
        type: "Feature" as const,
        geometry: {
          type: "LineString" as const,
          coordinates: [[center.lng, center.lat], f.geometry.coordinates as [number, number]],
        },
        properties: { shop_id: f.properties.shop_id },
      })),
  };
}

export function radiusRingFC(center: Center, radiusKm: number): GeoJSON.FeatureCollection {
  const R = 6371;
  const dLat = (radiusKm / R) * (180 / Math.PI);
  const dLng = dLat / Math.cos((center.lat * Math.PI) / 180);
  const coords: [number, number][] = Array.from({ length: 65 }, (_, i) => {
    const a = (i % 64) * ((2 * Math.PI) / 64);
    return [center.lng + dLng * Math.cos(a), center.lat + dLat * Math.sin(a)];
  });
  return {
    type: "FeatureCollection",
    features: [{ type: "Feature", geometry: { type: "LineString", coordinates: coords }, properties: {} }],
  };
}
