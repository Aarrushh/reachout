/* eslint-disable */
/**
 * Generated from reachout/shared/schemas/map_geojson.schema.json — do not hand-edit.
 * Run `npm run gen-types` to regenerate.
 */

/**
 * Producer: stage 05. Consumer: /api/search.geojson (map matched layer). additionalProperties:false is the hallucination gate. RFC 7946 FeatureCollection of matched shops. 'metadata' is a GeoJSON foreign member (allowed by RFC 7946 §6.1). Coordinates are [longitude, latitude] — the per-position bounds below make a lat/lng swap fail validation. Errors never appear in this file: on bad input, stage 05 writes output/error.json (status envelope) instead and no .geojson. Script invariant: features.length == metadata.result_count.
 */
export interface ShopMapGeoJSON {
  type: "FeatureCollection";
  metadata: {
    query: string;
    generated_at: string;
    result_count: number;
    center: {
      lat: number;
      lng: number;
    };
    radius_km: number;
  };
  features: {
    type: "Feature";
    geometry: {
      type: "Point";
      /**
       * @minItems 2
       * @maxItems 2
       */
      coordinates: [number, number];
    };
    properties: {
      shop_id: string;
      shop_name: string;
      rank: number;
      category: "pharmacy" | "grocery" | "hardware" | "electronics" | "stationery";
      address: string | null;
      distance_km: number;
      item_name: string;
      price: number;
      currency: "EUR";
      stock_qty: number;
    };
  }[];
}
