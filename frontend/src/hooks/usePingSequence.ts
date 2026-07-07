/** Ping timing is presentation, not data (spec D1): every matched shop IS
 * pinged; this hook only staggers when each one lights up. */
import { useEffect, useMemo, useState } from "react";

import type { RankedResult } from "../routes/results";

const STEP_MS = 120;
const TOTAL_CAP_MS = 2500;

export function usePingSequence(results: RankedResult[] | undefined, searchKey: string): Set<string> {
  const ids = useMemo(() => (results ?? []).map((r) => r.shop_id), [results]);
  const idsKey = ids.join(",");
  // Rank order is fixed, so "how many have pinged" is the only state needed.
  const [count, setCount] = useState(0);

  useEffect(() => {
    setCount(0);
    const n = idsKey ? idsKey.split(",").length : 0;
    if (n === 0) return;

    const reduced = typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      setCount(n);
      return;
    }

    const step = Math.min(STEP_MS, TOTAL_CAP_MS / n);
    const timers = Array.from({ length: n }, (_, i) =>
      window.setTimeout(() => setCount((c) => Math.max(c, i + 1)), Math.round(step * (i + 1))),
    );
    return () => timers.forEach(clearTimeout);
  }, [searchKey, idsKey]);

  return useMemo(() => new Set(ids.slice(0, count)), [ids, count]);
}
