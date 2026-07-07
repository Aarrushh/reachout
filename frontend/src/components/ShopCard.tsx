import { formatDistance, formatPrice } from "../lib/format";
import { t, type Lang } from "../i18n/strings";
import type { RankedResult } from "../routes/results";

export const CATEGORY_ICONS: Record<string, string> = {
  pharmacy: "⚕", grocery: "⛁", hardware: "⚒", electronics: "⚡", stationery: "✎",
};

interface Props {
  result: RankedResult;
  pinged: boolean;
  selected: boolean;
  onSelect: (shopId: string | null) => void;
  lang: Lang;
}

export default function ShopCard({ result: r, pinged, selected, onSelect, lang }: Props) {
  const lowStock = r.stock_qty <= 3;
  return (
    <article
      className={`shop-card cat-${r.category}${selected ? " selected" : ""}${pinged ? " pinged" : ""}`}
      onClick={() => onSelect(r.shop_id)}
      onMouseEnter={() => onSelect(r.shop_id)}
      onMouseLeave={() => onSelect(null)}
    >
      <header>
        <span className="mono rank">#{r.rank}</span>
        <span className="cat-icon" aria-label={r.category}>{CATEGORY_ICONS[r.category]}</span>
        <h3>{r.shop_name}</h3>
        {pinged && <span className="ping-badge microcaps"><span className="ping-dot" /> {t(lang, "results.ping")}</span>}
        <span className="mono distance">{formatDistance(r.distance_km, lang)}</span>
      </header>
      <p className="item-name">{r.item_name}</p>
      <p className="data-row">
        <span className="mono price">{formatPrice(r.price)}</span>
        <span className="dot-sep">·</span>
        <span className={`mono stock${lowStock ? " low" : ""}`}>
          {lowStock ? t(lang, "results.lowStock", { n: r.stock_qty }) : `${t(lang, "results.stock")} ${r.stock_qty}`}
        </span>
        {r.address && (<><span className="dot-sep">·</span><span className="address">{r.address}</span></>)}
      </p>
    </article>
  );
}
