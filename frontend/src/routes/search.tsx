/** Entry: full-screen location prompt + bilingual search. Submits to /results. */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { fetchAllShops } from "../api/client";
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
  const allShops = useQuery({ queryKey: ["all-shops"], queryFn: fetchAllShops, staleTime: Infinity });

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
      {allShops.data && (
        <svg className="entry-net" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice" aria-hidden>
          {allShops.data.features.map((f, i) => {
            const [lng, lat] = f.geometry.coordinates;
            const x = ((lng - -3.78) / 0.16) * 100;
            const y = ((40.48 - lat) / 0.12) * 100;
            return <circle key={f.properties.shop_id} cx={x} cy={y} r={0.35}
              style={{ animationDelay: `${(i % 20) * 0.3}s` }} />;
          })}
        </svg>
      )}
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
