/**
 * Adapter exposing the stage-05 FeatureCollection as a MapLibre GL JS
 * geojson source spec. No rendering code lives here — the future UI phase
 * wires this into an actual <Map>/<Source> component.
 */
import type { GeoJSONSourceSpecification } from "maplibre-gl";

import type { ShopMapGeoJSON } from "../types/MapGeojson";

export function toGeoJSONSource(featureCollection: ShopMapGeoJSON): GeoJSONSourceSpecification {
  return {
    type: "geojson",
    data: featureCollection,
  };
}
