/** Entry: full-screen location prompt + bilingual search. Submits to /results. */
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import BarrioCombobox from "../components/BarrioCombobox";
import SearchInput from "../components/SearchInput";
import { type Barrio } from "../data/barrios";
import { useLang } from "../hooks/useLang";
import { t } from "../i18n/strings";
import "../components/entry.css";

type Loc = { kind: "barrio"; barrio: Barrio } | { kind: "geo"; lat: number; lng: number };

export default function SearchRoute() {
  const navigate = useNavigate();
  const [lang, setLang] = useLang();
  const [q, setQ] = useState("");
  const [loc, setLoc] = useState<Loc | null>(null);
  const [geoError, setGeoError] = useState(false);
  const [locating, setLocating] = useState(false);

  function submit() {
    if (!loc || !q.trim()) return;
    const params = new URLSearchParams({ q: q.trim(), radius: "2" });
    if (loc.kind === "barrio") params.set("near", loc.barrio.name);
    else { params.set("lat", String(loc.lat)); params.set("lng", String(loc.lng)); }
    if (lang === "en") params.set("lang", "en");
    navigate(`/results?${params.toString()}`);
  }

  function useMyLocation() {
    setLocating(true);
    setGeoError(false);
    navigator.geolocation.getCurrentPosition(
      (pos) => { setLoc({ kind: "geo", lat: pos.coords.latitude, lng: pos.coords.longitude }); setLocating(false); },
      () => { setGeoError(true); setLocating(false); },
      { timeout: 8000 },
    );
  }

  return (
    <div className="entry">
      <div className="entry-lang microcaps">
        <button className={lang === "es" ? "on" : ""} onClick={() => setLang("es")}>ES</button>
        <button className={lang === "en" ? "on" : ""} onClick={() => setLang("en")}>EN</button>
      </div>
      <main className="entry-card">
        <span className="entry-wordmark microcaps">ReachOut · Madrid</span>
        <h1>{t(lang, "entry.headline")}</h1>
        <div className="entry-loc">
          <BarrioCombobox lang={lang} selected={loc?.kind === "barrio" ? loc.barrio : null}
            onSelect={(b) => setLoc(b ? { kind: "barrio", barrio: b } : null)} />
          <button className="entry-geo microcaps" onClick={useMyLocation} disabled={locating}>
            ◎ {t(lang, "entry.useLocation")}{loc?.kind === "geo" ? " ✓" : ""}
          </button>
        </div>
        {geoError && <p className="entry-geo-error">{t(lang, "entry.locationDenied")}</p>}
        <SearchInput value={q} onChange={setQ} onSubmit={submit} lang={lang} disabled={!loc} autoFocus />
      </main>
    </div>
  );
}
