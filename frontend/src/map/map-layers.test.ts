import { describe, expect, it } from "vitest";

import { pingLinesFC, radiusRingFC } from "./map-layers";
import type { ShopMapGeoJSON } from "../types/MapGeojson";

const matched = {
  type: "FeatureCollection",
  metadata: { query: "x", generated_at: "", result_count: 1, center: { lat: 40.42, lng: -3.7 }, radius_km: 2 },
  features: [{
    type: "Feature",
    geometry: { type: "Point", coordinates: [-3.7035, 40.427] },
    properties: { shop_id: "osm:node:1", shop_name: "F", rank: 1, category: "pharmacy",
      address: null, distance_km: 0.4, item_name: "p", price: 1, currency: "EUR", stock_qty: 2 },
  }],
} as unknown as ShopMapGeoJSON;

describe("map-layers", () => {
  it("draws one line per pinged shop, user first", () => {
    const fc = pingLinesFC({ lat: 40.42, lng: -3.7 }, matched, new Set(["osm:node:1"]));
    expect(fc.features).toHaveLength(1);
    expect((fc.features[0].geometry as GeoJSON.LineString).coordinates[0]).toEqual([-3.7, 40.42]);
  });
  it("skips unpinged shops", () => {
    const fc = pingLinesFC({ lat: 40.42, lng: -3.7 }, matched, new Set());
    expect(fc.features).toHaveLength(0);
  });
  it("builds a closed 64-segment ring", () => {
    const fc = radiusRingFC({ lat: 40.42, lng: -3.7 }, 2);
    const coords = (fc.features[0].geometry as GeoJSON.LineString).coordinates;
    expect(coords).toHaveLength(65);
    expect(coords[0]).toEqual(coords[64]);
  });
});
