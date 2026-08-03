import { formatDistance, formatPrice } from "../../lib/format";
import { monoNums } from "../../lib/monoNums";
import { t, type Lang, type StringKey } from "../../i18n/strings";
import type { RankedResult } from "../../routes/results";

export const CATEGORY_ICONS: Record<string, string> = {
  pharmacy: "⚕", grocery: "⛁", hardware: "⚒", electronics: "⚡", stationery: "✎",
};

/* rating/review_count ship from the backend later (schema-first); optional
 * locally until gen-types includes them. Never fabricated client-side. */
type MaybeRated = RankedResult & { rating?: number; review_count?: number };

interface Props {
  result: RankedResult;
  pinged: boolean;
  selected: boolean;
  onSelect: (shopId: string | null) => void;
  onChat: (result: RankedResult) => void;
  lang: Lang;
}

const STAR_PATH =
  "M12 2l2.9 6.3 6.9.8-5.1 4.7 1.4 6.8L12 17.2 5.9 20.6l1.4-6.8L2.2 9.1l6.9-.8z";

function Stars({ rating }: { rating: number }) {
  const pct = Math.max(0, Math.min(100, (rating / 5) * 100));
  const row = (filled: boolean) =>
    Array.from({ length: 5 }, (_, i) => (
      <svg key={i} viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
        <path d={STAR_PATH} fill={filled ? "var(--star-gold)" : "none"}
          stroke="var(--star-gold)" strokeWidth="1.5" />
      </svg>
    ));
  return (
    <span className="stars" role="img" aria-label={`${rating.toFixed(1)} / 5`}>
      <span className="stars-empty">{row(false)}</span>
      <span className="stars-filled" style={{ width: `${pct}%` }}>{row(true)}</span>
    </span>
  );
}

function SplitPrice({ price }: { price: number }) {
  const [int, dec] = price.toFixed(2).split(".");
  return (
    <span className="mono split-price" aria-label={formatPrice(price)}>
      <sup className="price-sym">€</sup>
      <span className="price-int">{int}</span>
      <sup className="price-dec">{dec}</sup>
    </span>
  );
}

export default function ShopCard({ result, pinged, selected, onSelect, onChat, lang }: Props) {
  const r = result as MaybeRated;
  const stockKey: StringKey =
    r.stock_qty > 5 ? "results.inStock" : r.stock_qty >= 1 ? "results.onlyNLeft" : "results.outOfStock";
  const stockClass = r.stock_qty > 5 ? "in" : r.stock_qty >= 1 ? "low" : "out";
  return (
    <article
      className={`shop-card cat-${r.category}${selected ? " selected" : ""}${pinged ? " pinged" : ""}`}
      onClick={() => onSelect(r.shop_id)}
      onMouseEnter={() => onSelect(r.shop_id)}
      onMouseLeave={() => onSelect(null)}
    >
      <div className="card-tile">
        <span className="mono rank">#{r.rank}</span>
        <span className="cat-icon" aria-label={r.category}>{CATEGORY_ICONS[r.category]}</span>
      </div>
      <div className="card-body">
        <h3 className="item-title">{r.item_name}</h3>
        <p className="trust-row">
          {r.rating !== undefined ? (
            <>
              <Stars rating={r.rating} />
              <span className="mono rating-value">{r.rating.toFixed(1)}</span>
              {r.review_count !== undefined && (
                <span className="mono review-count">({r.review_count})</span>
              )}
            </>
          ) : (
            <span className="no-rating">{t(lang, "results.noRating")}</span>
          )}
        </p>
        <p className="price-row"><SplitPrice price={r.price} /></p>
        <p className={`stock-badge ${stockClass}`}>
          {monoNums(t(lang, stockKey, { n: r.stock_qty }))}
        </p>
        <p className="meta-row microcaps">
          {r.shop_name} · <span className="mono">{formatDistance(r.distance_km, lang)}</span>
          {r.address && <> · {r.address}</>}
        </p>
        <button className="chat-ask microcaps"
          onClick={(e) => { e.stopPropagation(); onChat(result); }}>
          💬 {t(lang, "chat.ask")}
        </button>
      </div>
      {pinged && (
        <span className="ping-badge microcaps">
          <span className="ping-dot" /> {t(lang, "results.ping")}
        </span>
      )}
    </article>
  );
}
