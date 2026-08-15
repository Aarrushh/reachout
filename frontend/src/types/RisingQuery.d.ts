/* eslint-disable */
/**
 * Generated from demand/shared/schemas/rising_query.schema.json — do not hand-edit.
 * Run `npm run gen-types` to regenerate.
 */

/**
 * Producer: demand/api/relevance.py annotate() over demand.rising_queries rows (demand/data/schema.sql:146-160). Consumer: the rising-queries HTTP endpoint (task after this one) and its frontend caller. additionalProperties:false is the hallucination gate. Represents one discovered Google Trends 'rising query' under a tracked parent keyword, tiered for commercial relevance by pure Python -- no AI ever assigns relevance_score/relevance_tier/relevance_reasons/cluster_id. growth_pct is nullable by design: Google answers 'Breakout' for ~447 of 658 rows and refuses to quantify growth, so null here is a fact Google reported, never a gap this service is allowed to fill in.
 */
export interface RisingQuery {
  id: string;
  /**
   * Tracked seed keyword this query was discovered under (e.g. 'gafas de sol', 'café'). Not necessarily a substring of `query` -- see relevance_reasons for why containment is a signal, not a filter.
   */
  parent_keyword: string;
  /**
   * The raw discovered search text, exactly as Google Trends returned it. Never rewritten or truncated: relevance_score/tier/reasons are derived FROM this value, so mutating it here would silently invalidate them.
   */
  query: string;
  /**
   * Google-reported growth percentage, or null when Google answered 'Breakout' and declined to quantify it (~447 of 658 rows on the live table). A number here is always a number Google gave; this service never estimates one to fill a null.
   */
  growth_pct: number | null;
  /**
   * True when Google reported 'Breakout' growth instead of a percentage. Mirrors growth_pct's nullability: is_breakout true implies growth_pct is null, and this schema does not enforce that pairing itself so a stored row can never fail validation over a Google-side inconsistency.
   */
  is_breakout: boolean;
  /**
   * Madrid community scope only, e.g. ES-MD. Matches demand_signal.schema.json's geo field: this service never resolves to barrio granularity.
   */
  geo: string;
  /**
   * Google property the discovery came from: 'froogle' for Shopping, or the empty string for Web -- '' is the real value run_ingest.py's DISCOVERY_GPROP stores for Web rows (demand/scripts/run_ingest.py:62), not a placeholder for a missing value, so this field intentionally has no minLength. Stored, not assumed constant: a Shopping-derived row and a Web-derived row can carry the same query text but mean different search intent.
   */
  gprop: string;
  captured_at: string;
  /**
   * Calendar date `captured_at` falls on, stored separately for date-only indexing/filtering (see rising_queries_captured_date_idx in demand/data/schema.sql). Derived from captured_at at write time, not recomputed here.
   */
  captured_date: string;
  /**
   * Computed at read time by demand/api/relevance.py:score_query() -- not a column in demand.rising_queries, so a stale value can never be read back from the table. Signed point total: positive signals (parent-keyword containment, retail modifiers, variant/spec tokens, token-count band) add; negative signals (blocklist match, informational-intent phrase, single bare token) subtract. Deterministic and re-derivable from query + parent_keyword alone -- never hand-edited, never AI-assigned. Exposed mainly for debugging/audit; consumers should sort/filter on relevance_tier, not on this raw magnitude, since the weights are internal and may be retuned.
   */
  relevance_score: number;
  /**
   * Computed at read time by demand/api/relevance.py:score_query() -- not a column in demand.rising_queries. Label, not a filter: every row keeps its tier but no row is ever dropped by this service. 'noise' still means 'we scored this low', not 'this row does not exist' -- a caller may still choose to show it.
   */
  relevance_tier: "commercial" | "ambiguous" | "noise";
  /**
   * Computed at read time by demand/api/relevance.py:score_query() -- not a column in demand.rising_queries. Names of every signal that fired for this row, e.g. 'contains_parent_keyword', 'blocklist_exact_match', 'retail_modifier:mercadona'. Required and non-empty (falls back to 'no_signals_detected') because an unauditable heuristic is worse than no heuristic at all -- a human must always be able to see WHY a query was tiered the way it was.
   *
   * @minItems 1
   */
  relevance_reasons: [string, ...string[]];
  /**
   * Computed at read time by demand/api/relevance.py:cluster_key(query) -- not a column in demand.rising_queries. Accent/case-folded, stopwords dropped, remaining tokens sorted and joined. Groups near-duplicate queries (e.g. 'gafas eclipse' and 'gafas para el eclipse') so a consumer can surface one card instead of many almost-identical rows. Can be an empty string when `query` is entirely stopwords; still a valid, non-null key.
   */
  cluster_id: string;
}
