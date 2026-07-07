/* eslint-disable */
/**
 * Generated from reachout/shared/schemas/shops_geojson.schema.json — do not hand-edit.
 * Run `npm run gen-types` to regenerate.
 */

/**
 * RFC 7946 FeatureCollection of ALL known shops (no inventory, no ranking) for the map's always-on network layer. Facts only: id, name, category, position. Same coordinate-order guard as map_geojson.schema.json.
 */
export interface ShopsGeoJSON {
  type: "FeatureCollection";
  metadata: {
    shop_count: number;
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
      category: "pharmacy" | "grocery" | "hardware" | "electronics" | "stationery";
    };
  }[];
}
