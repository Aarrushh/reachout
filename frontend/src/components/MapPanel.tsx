import maplibregl, { Map as MLMap, Popup } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState } from "react";

import { pingLinesFC, radiusRingFC, type Center } from "../map/map-layers";
import { formatDistance, formatPrice } from "../lib/format";
import { CATEGORY_ICONS } from "./ShopCard";
import { t, type Lang } from "../i18n/strings";
import type { ShopMapGeoJSON } from "../types/MapGeojson";
import type { ShopsGeoJSON } from "../types/ShopsGeojson";

const STYLE_URL = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";
const MADRID: [number, number] = [-3.7038, 40.4168];
const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };
const CAT_COLOR: maplibregl.ExpressionSpecification = [
  "match", ["get", "category"],
  "pharmacy", "#7fb069", "grocery", "#b8d97e", "hardware", "#f4a259",
  "electronics", "#5bc0eb", "stationery", "#c77dff", "#e2725b",
];

interface Props {
  matched: ShopMapGeoJSON | undefined;
  network: ShopsGeoJSON | undefined;
  pingedIds: Set<string>;
  selectedShopId: string | null;
  onSelect: (id: string | null) => void;
  lang: Lang;
}

function setData(map: MLMap, id: string, fc: GeoJSON.FeatureCollection) {
  const src = map.getSource(id) as maplibregl.GeoJSONSource | undefined;
  src?.setData(fc);
}

/** Numeric feature ids are required for setFeatureState; derive from osm id. */
function fid(shopId: string): number {
  return Number(shopId.split(":")[2]);
}

function withIds(matched: ShopMapGeoJSON): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: matched.features.map((f) => ({ ...(f as unknown as GeoJSON.Feature), id: fid(f.properties.shop_id) })),
  };
}

function esc(s: string): string {
  return s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

export default function MapPanel({ matched, network, pingedIds, selectedShopId, onSelect, lang }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  const [loaded, setLoaded] = useState(false);
  const popupRef = useRef<Popup | null>(null);
  const userMarkerRef = useRef<maplibregl.Marker | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  useEffect(() => {
    const map = new maplibregl.Map({
      container: container.current!,
      style: STYLE_URL,
      center: MADRID,
      zoom: 13,
      attributionControl: { compact: true },
    });
    mapRef.current = map;

    map.on("load", () => {
      for (const id of ["network", "ring", "lines", "matched"]) {
        map.addSource(id, { type: "geojson", data: EMPTY });
      }
      map.addLayer({ id: "network-shops", source: "network", type: "circle",
        paint: { "circle-radius": 3, "circle-color": "#3a4e78", "circle-opacity": 0.55 } });
      map.addLayer({ id: "radius-ring", source: "ring", type: "line",
        paint: { "line-color": "#e2725b", "line-opacity": 0.25, "line-width": 1.5, "line-dasharray": [2, 3] } });
      map.addLayer({ id: "ping-lines", source: "lines", type: "line",
        paint: { "line-color": "#e2725b", "line-opacity": 0.4, "line-width": 1 } });
      map.addLayer({ id: "matched-shops", source: "matched", type: "circle",
        paint: {
          "circle-radius": ["+", 6, ["*", 2, ["sqrt", ["get", "stock_qty"]]]],
          "circle-color": CAT_COLOR,
          "circle-stroke-width": ["case", ["boolean", ["feature-state", "selected"], false], 3, 1.5],
          "circle-stroke-color": ["case", ["boolean", ["feature-state", "selected"], false], "#ff8a66", "#ead9bd"],
          "circle-opacity": ["case", ["boolean", ["feature-state", "pinged"], false], 1, 0],
          "circle-stroke-opacity": ["case", ["boolean", ["feature-state", "pinged"], false], 1, 0],
        } });
      map.addLayer({ id: "rank-labels", source: "matched", type: "symbol",
        filter: ["<=", ["get", "rank"], 10],
        layout: { "text-field": ["concat", "#", ["to-string", ["get", "rank"]]],
          "text-size": 11, "text-offset": [0, -1.6], "text-font": ["Open Sans Bold"] },
        paint: { "text-color": "#ead9bd",
          "text-opacity": ["case", ["boolean", ["feature-state", "pinged"], false], 1, 0] } });

      map.on("mouseenter", "matched-shops", () => { map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", "matched-shops", () => { map.getCanvas().style.cursor = ""; });
      map.on("click", "matched-shops", (e) => {
        const f = e.features?.[0];
        if (f?.properties) onSelectRef.current(String(f.properties.shop_id));
      });

      setLoaded(true);
    });

    return () => {
      setLoaded(false);
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // The effects below intentionally have no dependency arrays: they run every
  // render, early-return until the map is loaded, and each is idempotent.

  // Network layer (static).
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded || !network) return;
    setData(map, "network", network as unknown as GeoJSON.FeatureCollection);
  });

  // Matched shops + ring + user dot + camera, when a new result set arrives.
  const lastMatchedRef = useRef<ShopMapGeoJSON | null>(null);
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded || !matched || lastMatchedRef.current === matched) return;
    lastMatchedRef.current = matched;
    const center: Center = matched.metadata.center;
    setData(map, "matched", withIds(matched));
    setData(map, "ring", radiusRingFC(center, matched.metadata.radius_km));

    userMarkerRef.current?.remove();
    const el = document.createElement("div");
    el.className = "user-dot";
    el.title = t(lang, "map.you");
    userMarkerRef.current = new maplibregl.Marker({ element: el }).setLngLat([center.lng, center.lat]).addTo(map);

    const bounds = new maplibregl.LngLatBounds([center.lng, center.lat], [center.lng, center.lat]);
    for (const f of matched.features) bounds.extend(f.geometry.coordinates as [number, number]);
    map.fitBounds(bounds, { padding: 60, duration: 600, maxZoom: 16 });
  });

  // Ping state → feature-state + lines.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded || !matched) return;
    for (const f of matched.features) {
      map.setFeatureState({ source: "matched", id: fid(f.properties.shop_id) },
        { pinged: pingedIds.has(f.properties.shop_id), selected: f.properties.shop_id === selectedShopId });
    }
    setData(map, "lines", pingLinesFC(matched.metadata.center, matched, pingedIds));
  });

  // Popup follows selection.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded) return;
    popupRef.current?.remove();
    popupRef.current = null;
    const f = matched?.features.find((x) => x.properties.shop_id === selectedShopId);
    if (!f) return;
    const p = f.properties;
    popupRef.current = new Popup({ closeButton: false, offset: 14, className: "shop-popup" })
      .setLngLat(f.geometry.coordinates as [number, number])
      .setHTML(
        `<strong>${CATEGORY_ICONS[p.category]} ${esc(p.shop_name)}</strong>` +
        `<div>${esc(p.item_name)}</div>` +
        `<div class="mono">${formatPrice(p.price)} · ${t(lang, "results.stock")} ${p.stock_qty} · ${formatDistance(p.distance_km, lang)}</div>`,
      )
      .addTo(map);
  });

  return <div ref={container} className="map-panel" />;
}
