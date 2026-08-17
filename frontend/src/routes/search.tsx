/** Entry: Amazon-style landing — dark hero with search, category tiles,
 * how-it-works strip. Submits to /results; URL stays the state of record. */
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { fetchAllShops } from "../api/client";
import BarrioCombobox from "../components/consumer/BarrioCombobox";
import InstallPrompt from "../components/consumer/InstallPrompt";
import PicksRail from "../components/consumer/PicksRail";
import BlurText from "../components/consumer/reactbits/BlurText";
import SearchInput from "../components/consumer/SearchInput";
import { CATEGORY_ICONS } from "../components/consumer/ShopCard";
import { CATEGORIES } from "../components/consumer/TopBar";
import { useLang } from "../hooks/useLang";
import { t, type StringKey } from "../i18n/strings";
import "../components/consumer/entry.css";

type Loc = { kind: "barrio"; name: string } | { kind: "geo"; lat: number; lng: number };

/* The synthetic inventory is Spanish-named — English seed queries return empty. */
const CATEGORY_SEEDS: Record<(typeof CATEGORIES)[number], string> = {
  pharmacy: "paracetamol",
  grocery: "leche",
  hardware: "tornillos",
  electronics: "cargador",
  stationery: "cuaderno",
};

const HOW_STEPS: { glyph: string; key: StringKey }[] = [
  { glyph: "⌕", key: "landing.how1" },
  { glyph: "⚡", key: "landing.how2" },
  { glyph: "✓", key: "landing.how3" },
];

export default function SearchRoute() {
  const navigate = useNavigate();
  const [lang, setLang] = useLang();
  const [q, setQ] = useState("");
  const [loc, setLoc] = useState<Loc | null>(null);
  const [geoError, setGeoError] = useState(false);
  const [locating, setLocating] = useState(false);
  const [needLocation, setNeedLocation] = useState(false);
  const allShops = useQuery({ queryKey: ["all-shops"], queryFn: fetchAllShops, staleTime: Infinity });

  function locParams(target: Loc): URLSearchParams {
    const params = new URLSearchParams({ radius: "2" });
    if (target.kind === "barrio") params.set("near", target.name);
    else { params.set("lat", String(target.lat)); params.set("lng", String(target.lng)); }
    if (lang === "en") params.set("lang", "en");
    return params;
  }

  function submit() {
    if (!q.trim()) return;
    if (!loc) {
      // The Enter key reaches here even while the button is disabled.
      setNeedLocation(true);
      return;
    }
    const params = locParams(loc);
    params.set("q", q.trim());
    navigate(`/results?${params.toString()}`);
  }

  function goCategory(c: (typeof CATEGORIES)[number]) {
    if (!loc) {
      setNeedLocation(true);
      return;
    }
    const params = locParams(loc);
    params.set("q", CATEGORY_SEEDS[c]);
    params.set("category", c);
    navigate(`/results?${params.toString()}`);
  }

  // A pick is a shortcut into the same search the box performs, so it takes
  // the same location guard: results are ranked by distance, and there is no
  // sensible ranking from nowhere.
  function goPick(productName: string) {
    if (!loc) {
      setNeedLocation(true);
      return;
    }
    const params = locParams(loc);
    params.set("q", productName);
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
      <header className="entry-hero">
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
        <div className="entry-actions">
          <InstallPrompt lang={lang} />
        </div>
        <div className="entry-lang microcaps">
          <button className={lang === "es" ? "on" : ""} onClick={() => setLang("es")}>ES</button>
          <button className={lang === "en" ? "on" : ""} onClick={() => setLang("en")}>EN</button>
        </div>
        <div className="entry-hero-inner">
          <span className="entry-wordmark microcaps">ReachOut · Madrid</span>
          <h1>
            <BlurText
              text={t(lang, "landing.tagline")}
              animateBy="words"
              delay={80}
              stepDuration={0.3}
              className="entry-h1"
            />
          </h1>
          <div className="entry-search-cluster">
            <div className="entry-loc">
              <BarrioCombobox lang={lang} selected={loc?.kind === "barrio" ? loc.name : null}
                onSelect={(name) => { setLoc(name ? { kind: "barrio", name } : null); if (name) setNeedLocation(false); }} />
              <button className="entry-geo microcaps" onClick={useMyLocation} disabled={locating}>
                ◎ {t(lang, "entry.useLocation")}{loc?.kind === "geo" ? " ✓" : ""}
              </button>
            </div>
            <SearchInput value={q} onChange={setQ} onSubmit={submit} lang={lang} disabled={!loc} autoFocus />
          </div>
          {geoError && <p className="entry-geo-error">{t(lang, "entry.locationDenied")}</p>}
          {needLocation && !loc && <p className="entry-geo-error">{t(lang, "entry.needLocation")}</p>}
        </div>
      </header>
      <section className="entry-cats">
        <h2>{t(lang, "landing.categoriesTitle")}</h2>
        <div className="cat-tiles">
          {CATEGORIES.map((c) => (
            <button key={c} className={`cat-tile cat-${c}`} onClick={() => goCategory(c)}>
              <span className="cat-tile-glyph" aria-hidden="true">{CATEGORY_ICONS[c]}</span>
              <span className="cat-tile-label">{t(lang, `nav.cat.${c}` as StringKey)}</span>
            </button>
          ))}
        </div>
      </section>
      <section className="entry-how">
        {HOW_STEPS.map((s, i) => (
          <div key={s.key} className="how-step">
            <span className="how-num mono">{i + 1}</span>
            <span className="how-glyph" aria-hidden="true">{s.glyph}</span>
            <p>{t(lang, s.key)}</p>
          </div>
        ))}
      </section>
      <PicksRail
        lang={lang}
        neighbourhood={loc?.kind === "barrio" ? loc.name : null}
        onSelect={goPick}
      />
    </div>
  );
}
