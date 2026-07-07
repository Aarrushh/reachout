import maplibregl, { Map as MLMap, Popup } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState } from "react";

import { pingLinesFC, radiusRingFC } from "../map/map-layers";
import { formatDistance, formatPrice } from "../lib/format";
import { CATEGORY_ICONS } from "./ShopCard";
import { t, type Lang } from "../i18n/strings";
import type { ShopMapGeoJSON } from "../types/MapGeojson";
import type { ShopsGeoJSON } from "../types/ShopsGeojson";

const STYLE_URL = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";
const MADRID: [number, number] = [-3.7038, 40.4168];
const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

/** Single source of truth for colors is tokens.css; the MapLibre paint
 * expressions read the same custom properties instead of duplicating hexes. */
function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function catColorExpression(): maplibregl.ExpressionSpecification {
  return [
    "match", ["get", "category"],
    "pharmacy", cssVar("--cat-pharmacy"),
    "grocery", cssVar("--cat-grocery"),
    "hardware", cssVar("--cat-hardware"),
    "electronics", cssVar("--cat-electronics"),
    "stationery", cssVar("--cat-stationery"),
    cssVar("--terracotta"),
  ];
}

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

/** MapLibre feature-state needs a numeric id per feature. OSM node/way/
 * relation numeric ids overlap, so index into the current result set and keep
 * a shop_id → index map alongside — collision-free by construction. */
function withIndexIds(matched: ShopMapGeoJSON): { fc: GeoJSON.FeatureCollection; idMap: Map<string, number> } {
  const idMap = new Map<string, number>();
  const features = matched.features.map((f, i) => {
    idMap.set(f.properties.shop_id, i);
    return { ...(f as unknown as GeoJSON.Feature), id: i };
  });
  return { fc: { type: "FeatureCollection", features }, idMap };
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
  const idMapRef = useRef<Map<string, number>>(new Map());
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
        paint: { "circle-radius": 3, "circle-color": cssVar("--navy-line"), "circle-opacity": 0.55 } });
      map.addLayer({ id: "radius-ring", source: "ring", type: "line",
        paint: { "line-color": cssVar("--terracotta"), "line-opacity": 0.25, "line-width": 1.5, "line-dasharray": [2, 3] } });
      map.addLayer({ id: "ping-lines", source: "lines", type: "line",
        paint: { "line-color": cssVar("--terracotta"), "line-opacity": 0.4, "line-width": 1 } });
      map.addLayer({ id: "matched-shops", source: "matched", type: "circle",
        paint: {
          "circle-radius": ["+", 6, ["*", 2, ["sqrt", ["get", "stock_qty"]]]],
          "circle-color": catColorExpression(),
          "circle-stroke-width": ["case", ["boolean", ["feature-state", "selected"], false], 3, 1.5],
          "circle-stroke-color": ["case", ["boolean", ["feature-state", "selected"], false],
            cssVar("--terracotta-hot"), cssVar("--sand")],
          // Unpinged dots stay faintly visible: a shop present on the map but
          // missing from the ranked set must never be invisible forever.
          "circle-opacity": ["case", ["boolean", ["feature-state", "pinged"], false], 1, 0.25],
          "circle-stroke-opacity": ["case", ["boolean", ["feature-state", "pinged"], false], 1, 0.3],
        } });
      map.addLayer({ id: "rank-labels", source: "matched", type: "symbol",
        filter: ["<=", ["get", "rank"], 10],
        layout: { "text-field": ["concat", "#", ["to-string", ["get", "rank"]]],
          "text-size": 11, "text-offset": [0, -1.6], "text-font": ["Open Sans Bold"] },
        paint: { "text-color": cssVar("--sand"),
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

  // Network layer (static).
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded || !network) return;
    setData(map, "network", network as unknown as GeoJSON.FeatureCollection);
  }, [loaded, network]);

  // Matched shops + ring + user dot + camera, when a new result set arrives.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded || !matched) return;
    const center = matched.metadata.center;
    const { fc, idMap } = withIndexIds(matched);
    idMapRef.current = idMap;
    map.removeFeatureState({ source: "matched" });
    setData(map, "matched", fc);
    setData(map, "ring", radiusRingFC(center, matched.metadata.radius_km));

    userMarkerRef.current?.remove();
    const el = document.createElement("div");
    el.className = "user-dot";
    userMarkerRef.current = new maplibregl.Marker({ element: el }).setLngLat([center.lng, center.lat]).addTo(map);

    const bounds = new maplibregl.LngLatBounds([center.lng, center.lat], [center.lng, center.lat]);
    for (const f of matched.features) bounds.extend(f.geometry.coordinates as [number, number]);
    map.fitBounds(bounds, { padding: 60, duration: 600, maxZoom: 16 });
  }, [loaded, matched]);

  // The user-dot tooltip is the only lang-dependent bit of the map chrome.
  useEffect(() => {
    userMarkerRef.current?.getElement().setAttribute("title", t(lang, "map.you"));
  }, [loaded, matched, lang]);

  // Ping state → feature-state + lines.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded || !matched) return;
    for (const f of matched.features) {
      const id = idMapRef.current.get(f.properties.shop_id);
      if (id === undefined) continue;
      map.setFeatureState({ source: "matched", id },
        { pinged: pingedIds.has(f.properties.shop_id), selected: f.properties.shop_id === selectedShopId });
    }
    setData(map, "lines", pingLinesFC(matched.metadata.center, matched, pingedIds));
  }, [loaded, matched, pingedIds, selectedShopId]);

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
  }, [loaded, matched, selectedShopId, lang]);

  return <div ref={container} className="map-panel" />;
}
