import { describe, expect, it } from "vitest";

import { groupRisingQueries } from "./risingQueries";
import type { RisingQuery } from "../../types/RisingQuery";

function row(overrides: Partial<RisingQuery>): RisingQuery {
  return {
    id: "id-1",
    parent_keyword: "gafas de sol",
    query: "gafas eclipse",
    growth_pct: 120,
    is_breakout: false,
    geo: "ES-MD",
    gprop: "",
    captured_at: "2026-08-01T00:00:00Z",
    captured_date: "2026-08-01",
    relevance_score: 5,
    relevance_tier: "commercial",
    relevance_reasons: ["contains_parent_keyword"],
    cluster_id: "eclipse gafas",
    ...overrides,
  };
}

describe("groupRisingQueries", () => {
  it("collapses rows sharing a cluster_id into one entry", () => {
    const rows: RisingQuery[] = [
      row({ id: "1", query: "gafas eclipse", cluster_id: "eclipse gafas" }),
      row({ id: "2", query: "gafas para el eclipse", cluster_id: "eclipse gafas" }),
      row({ id: "3", query: "gafas eclipse solar", cluster_id: "eclipse gafas" }),
    ];

    const clusters = groupRisingQueries(rows);

    expect(clusters).toHaveLength(1);
    expect(clusters[0].size).toBe(3);
  });

  it("keeps rows in different clusters as separate entries", () => {
    const rows: RisingQuery[] = [
      row({ id: "1", query: "gafas eclipse", cluster_id: "eclipse gafas" }),
      row({ id: "2", query: "protector solar", cluster_id: "protector solar" }),
    ];

    expect(groupRisingQueries(rows)).toHaveLength(2);
  });

  it("shows Breakout with a null growth_pct when the whole cluster is quantified except one row", () => {
    // The load-bearing case: a cluster whose OTHER members have real
    // percentages must still collapse to Breakout with no number the
    // moment any one member is a refusal — never let a quantified
    // sibling's percentage stand in for the figure Google declined to give.
    const rows: RisingQuery[] = [
      row({ id: "1", query: "gafas eclipse", growth_pct: 250, is_breakout: false }),
      row({ id: "2", query: "gafas para el eclipse", growth_pct: null, is_breakout: true }),
    ];

    const [cluster] = groupRisingQueries(rows);

    expect(cluster.isBreakout).toBe(true);
    expect(cluster.growthPct).toBeNull();
  });

  it("passes a quantified growth_pct through verbatim when no member is a breakout", () => {
    const rows: RisingQuery[] = [row({ growth_pct: 87.5, is_breakout: false })];

    const [cluster] = groupRisingQueries(rows);

    expect(cluster.isBreakout).toBe(false);
    expect(cluster.growthPct).toBe(87.5);
  });

  it("picks the shortest query text as the cluster's representative, deterministically", () => {
    const rows: RisingQuery[] = [
      row({ id: "1", query: "gafas para el eclipse solar", cluster_id: "eclipse gafas" }),
      row({ id: "2", query: "gafas eclipse", cluster_id: "eclipse gafas" }),
    ];

    const [cluster] = groupRisingQueries(rows);

    expect(cluster.query).toBe("gafas eclipse");
  });

  it("returns an empty list for an empty input", () => {
    expect(groupRisingQueries([])).toEqual([]);
  });
});
