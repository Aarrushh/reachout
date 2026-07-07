import { useEffect, useRef, useState } from "react";

import SearchInput from "./SearchInput";
import { t, type Lang } from "../i18n/strings";

interface Props {
  q: string;
  near: string | null;
  radiusKm: number;
  lang: Lang;
  onSearch: (q: string) => void;
  onRadius: (km: number) => void;
  onLang: (l: Lang) => void;
}

export default function TopBar({ q, near, radiusKm, lang, onSearch, onRadius, onLang }: Props) {
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
      <a className="wordmark" href="/">Reach<span>Out</span></a>
      {near && <span className="barrio-chip microcaps">{near}</span>}
      <SearchInput value={draft} onChange={setDraft} onSubmit={() => onSearch(draft)} lang={lang} />
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
    </header>
  );
}
