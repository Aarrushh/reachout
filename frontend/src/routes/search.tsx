/** Entry: full-screen location prompt + bilingual search. Submits to /results. */
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { fetchAllShops } from "../api/client";
import BarrioCombobox from "../components/BarrioCombobox";
import SearchInput from "../components/SearchInput";
import { useLang } from "../hooks/useLang";
import { t } from "../i18n/strings";
import "../components/entry.css";

type Loc = { kind: "barrio"; name: string } | { kind: "geo"; lat: number; lng: number };

export default function SearchRoute() {
  const navigate = useNavigate();
  const [lang, setLang] = useLang();
  const [q, setQ] = useState("");
  const [loc, setLoc] = useState<Loc | null>(null);
  const [geoError, setGeoError] = useState(false);
  const [locating, setLocating] = useState(false);
  const [needLocation, setNeedLocation] = useState(false);
  const allShops = useQuery({ queryKey: ["all-shops"], queryFn: fetchAllShops, staleTime: Infinity });

  function submit() {
    if (!q.trim()) return;
    if (!loc) {
      // The Enter key reaches here even while the button is disabled.
      setNeedLocation(true);
      return;
    }
    const params = new URLSearchParams({ q: q.trim(), radius: "2" });
    if (loc.kind === "barrio") params.set("near", loc.name);
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

  // A decorative backdrop doesn't need all ~3300 shops — sample to ≤600 so
  // the compositor isn't animating thousands of nodes behind a form.
  const netDots = useMemo(() => {
    const feats = allShops.data?.features ?? [];
    const stride = Math.max(1, Math.ceil(feats.length / 600));
    return feats.filter((_, i) => i % stride === 0);
  }, [allShops.data]);

  return (
    <div className="entry">
      {netDots.length > 0 && (
        <svg className="entry-net" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice" aria-hidden>
          {netDots.map((f, i) => {
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
          <BarrioCombobox lang={lang} selected={loc?.kind === "barrio" ? loc.name : null}
            onSelect={(name) => { setLoc(name ? { kind: "barrio", name } : null); if (name) setNeedLocation(false); }} />
          <button className="entry-geo microcaps" onClick={useMyLocation} disabled={locating}>
            ◎ {t(lang, "entry.useLocation")}{loc?.kind === "geo" ? " ✓" : ""}
          </button>
        </div>
        {geoError && <p className="entry-geo-error">{t(lang, "entry.locationDenied")}</p>}
        {needLocation && !loc && <p className="entry-geo-error">{t(lang, "entry.needLocation")}</p>}
        <SearchInput value={q} onChange={setQ} onSubmit={submit} lang={lang} disabled={!loc} autoFocus />
      </main>
    </div>
  );
}
