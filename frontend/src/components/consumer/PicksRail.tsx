import { useQuery } from "@tanstack/react-query";

import { fetchPicks } from "../../api/client";
import { t } from "../../i18n/strings";
import type { Lang } from "../../i18n/strings";
import type { PicksResponse } from "../../types/PicksResponse";

type Pick = PicksResponse["picks"][number];

/**
 * The "picks for you" rail on the consumer landing page (U4).
 *
 * **It disappears rather than complains.** Loading, a failed fetch and an
 * empty list all render nothing at all. This is a decoration on a page whose
 * job is the search box: an error banner here would tell a shopper that
 * something is broken when the thing they came for still works perfectly.
 * The rail is the one surface where silence is the honest response.
 *
 * The heading says the picks are popular nearby, not that they were chosen
 * *for you*: `/api/picks` ranks by store rating and round-robins categories
 * in pure Python (`generated_by: "deterministic"`), with no per-shopper
 * signal of any kind. Copy implying personalisation would be a claim the
 * backend cannot support.
 */
export default function PicksRail({
  lang,
  neighbourhood,
  onSelect,
}: {
  lang: Lang;
  /** Scopes the picks. Null means Madrid-wide, which is a valid request. */
  neighbourhood: string | null;
  onSelect: (productName: string) => void;
}) {
  const picks = useQuery({
    queryKey: ["picks", neighbourhood],
    queryFn: () => fetchPicks(neighbourhood),
  });

  const items: Pick[] = picks.data?.picks ?? [];
  if (items.length === 0) return null;

  return (
    <section className="picks" aria-labelledby="picks-title">
      <h2 id="picks-title">{t(lang, "picks.title")}</h2>
      <p className="picks__note">{t(lang, "picks.note")}</p>
      <ul className="picks__rail">
        {items.map((p) => (
          <li key={p.id}>
            <button type="button" className="pick-card" onClick={() => onSelect(p.name)}>
              {/* Product names, categories and neighbourhoods are data: shown
                  as the API returns them, never translated. */}
              <span className="pick-card__name">{p.name}</span>
              <span className="pick-card__meta">
                {p.category} · {p.neighbourhood}
              </span>
              <span className="pick-card__price">
                {p.price.toFixed(2)} €
              </span>
              <span className="pick-card__stock">
                {t(lang, "results.stock")}: {p.stock_qty}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
