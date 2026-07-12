import { useEffect, useRef, useState } from "react";

import SearchInput from "./SearchInput";
import { CATEGORY_ICONS } from "./ShopCard";
import { t, type Lang, type StringKey } from "../i18n/strings";

export const CATEGORIES = ["pharmacy", "grocery", "hardware", "electronics", "stationery"] as const;

interface Props {
  q: string;
  near: string | null;
  radiusKm: number;
  lang: Lang;
  onSearch: (q: string) => void;
  onRadius: (km: number) => void;
  onLang: (l: Lang) => void;
  category?: string | null;
  onCategory?: (c: string | null) => void;
}

export default function TopBar({ q, near, radiusKm, lang, onSearch, onRadius, onLang, category, onCategory }: Props) {
  const [draft, setDraft] = useState(q);
  const [radiusDraft, setRadiusDraft] = useState(radiusKm);
  const timer = useRef<number>(undefined);
  useEffect(() => setDraft(q), [q]);
  useEffect(() => setRadiusDraft(radiusKm), [radiusKm]);

  function handleRadius(km: number) {
    setRadiusDraft(km);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => onRadius(km), 400);
  }

  return (
    <header className="top-bar">
      <div className="top-bar-main">
        <a className="wordmark" href="/">Reach<span>Out</span></a>
        <div className="deliver-to">
          <span className="microcaps deliver-to-label">{t(lang, "nav.deliverTo")}</span>
          <span className="deliver-to-value"><span aria-hidden="true">◎</span> {near ?? "Madrid"}</span>
        </div>
        <div className="search-wrap">
          <SearchInput value={draft} onChange={setDraft} onSubmit={() => onSearch(draft)} lang={lang} />
        </div>
        <label className="radius-slider microcaps">
          {t(lang, "topbar.radius")}
          <input type="range" min={0.5} max={5} step={0.5} value={radiusDraft}
            onChange={(e) => handleRadius(Number(e.target.value))} />
          <span className="mono">{radiusDraft.toFixed(1)} km</span>
        </label>
        <div className="lang-toggle microcaps">
          <button className={lang === "es" ? "on" : ""} onClick={() => onLang("es")}>ES</button>
          <button className={lang === "en" ? "on" : ""} onClick={() => onLang("en")}>EN</button>
        </div>
      </div>
      <nav className={`cat-strip${onCategory ? "" : " inert"}`} aria-label={t(lang, "filter.category")}>
        <button
          className={`cat-pill${category == null ? " active" : ""}`}
          disabled={!onCategory}
          onClick={() => onCategory?.(null)}
        >
          {t(lang, "nav.categories.all")}
        </button>
        {CATEGORIES.map((c) => (
          <button
            key={c}
            className={`cat-pill${category === c ? " active" : ""}`}
            disabled={!onCategory}
            onClick={() => onCategory?.(category === c ? null : c)}
          >
            <span aria-hidden="true">{CATEGORY_ICONS[c]}</span> {t(lang, `nav.cat.${c}` as StringKey)}
          </button>
        ))}
      </nav>
    </header>
  );
}
