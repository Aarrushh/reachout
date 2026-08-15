/**
 * Pure grouping over `RisingQuery` rows for the discovery panel (task 4,
 * requirement 3). No arithmetic on `growth_pct` happens here — that field
 * is either printed verbatim or replaced by the Breakout label, never
 * derived — this file only decides which rows collapse into one card.
 */
import type { RisingQuery } from "../../types/RisingQuery";

export interface ClusteredQuery {
  clusterId: string;
  query: string;
  parentKeyword: string;
  /** Always `null` when `isBreakout` is true — see `groupRisingQueries`. */
  growthPct: number | null;
  isBreakout: boolean;
  /** Number of rows this card collapses, including the displayed one. */
  size: number;
}

/**
 * `demand/api/relevance.py:annotate()` assigns `cluster_id` to every row so
 * near-duplicate phrasings of one demand story (e.g. "gafas eclipse" and
 * "gafas para el eclipse") share a key. Grouping by that key here is what
 * turns a twelve-row cluster into one card.
 *
 * Rows are read in the order the endpoint returned them (already
 * deterministic — `id`-ordered, then annotated once over the full batch),
 * so the first `cluster_id` seen sets that cluster's position in the
 * output. Within a cluster, the shortest query text is shown as the
 * representative (ties broken alphabetically) since it is typically the
 * plainest phrasing of the shared demand story.
 *
 * **The honesty rule**: if ANY row in a cluster has `is_breakout: true`,
 * the collapsed card is a Breakout with no number — never a quantified
 * sibling's `growth_pct` standing in for a figure Google refused to give.
 */
export function groupRisingQueries(rows: RisingQuery[]): ClusteredQuery[] {
  const order: string[] = [];
  const byCluster = new Map<string, RisingQuery[]>();

  for (const row of rows) {
    const existing = byCluster.get(row.cluster_id);
    if (existing) {
      existing.push(row);
    } else {
      byCluster.set(row.cluster_id, [row]);
      order.push(row.cluster_id);
    }
  }

  return order.map((clusterId) => {
    const members = byCluster.get(clusterId)!;
    const representative = [...members].sort((a, b) => {
      if (a.query.length !== b.query.length) return a.query.length - b.query.length;
      return a.query.localeCompare(b.query);
    })[0];
    const isBreakout = members.some((m) => m.is_breakout);

    return {
      clusterId,
      query: representative.query,
      parentKeyword: representative.parent_keyword,
      growthPct: isBreakout ? null : representative.growth_pct,
      isBreakout,
      size: members.length,
    };
  });
}
