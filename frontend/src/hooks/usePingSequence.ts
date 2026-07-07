/** Ping timing is presentation, not data (spec D1): every matched shop IS
 * pinged; this hook only staggers when each one lights up. */
import { useEffect, useRef, useState } from "react";

import type { RankedResult } from "../routes/results";

const STEP_MS = 120;
const TOTAL_CAP_MS = 2500;

export function usePingSequence(results: RankedResult[] | undefined, searchKey: string): Set<string> {
  const [pinged, setPinged] = useState<Set<string>>(new Set());
  const ids = (results ?? []).map((r) => r.shop_id).join(",");
  const idsRef = useRef(ids);
  idsRef.current = ids;

  useEffect(() => {
    setPinged(new Set());
    const shopIds = idsRef.current ? idsRef.current.split(",") : [];
    if (shopIds.length === 0) return;

    const reduced = typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      setPinged(new Set(shopIds));
      return;
    }

    const step = Math.min(STEP_MS, TOTAL_CAP_MS / shopIds.length);
    const timers = shopIds.map((id, i) =>
      window.setTimeout(() => setPinged((prev) => new Set(prev).add(id)), Math.round(step * (i + 1))),
    );
    return () => timers.forEach(clearTimeout);
  }, [searchKey, ids]);

  return pinged;
}
