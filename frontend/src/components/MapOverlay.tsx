import { BARRIOS } from "../data/barrios";
import { t, type Lang } from "../i18n/strings";

interface Props {
  region: string | null;
  onRegion: (r: string | null) => void;
  networkCount: number;
  lang: Lang;
}

/** Chrome overlaid on the map's top edge. Pure presentation: pointer-events
 * pass through the wrapper so pan/zoom keeps working between the controls. */
export default function MapOverlay({ region, onRegion, networkCount, lang }: Props) {
  return (
    <div className="map-overlay">
      <label className="region-select">
        <span className="microcaps">{t(lang, "map.region")}</span>
        <select value={region ?? ""} onChange={(e) => onRegion(e.target.value || null)}>
          <option value="">{t(lang, "map.allCity")}</option>
          {BARRIOS.map((b) => (
            <option key={b.name} value={b.name}>{b.name}</option>
          ))}
        </select>
      </label>
      <div className="live-indicator">
        <span className="live-dot" />
        <span className="microcaps">{t(lang, "map.live")}</span>
        <span className="mono">{t(lang, "map.liveShops", { n: networkCount })}</span>
      </div>
    </div>
  );
}
