import { useSearchParams } from "react-router-dom";

/** The two halves of the app. There is no third value. */
export type Mode = "consumer" | "retail";

/** The only string that selects retail mode. */
export const RETAIL_PARAM_VALUE = "retail";

/**
 * Read `?mode=` and turn it into a `Mode`.
 *
 * Anything that is not exactly `retail` — absent, empty, `RETAIL`, `shop`,
 * `retail; drop table` — is consumer. Consumer is the safe default: it is the
 * half a stranger following a link should land in, and an unrecognised value
 * is not a reason to show someone a shopkeeper's dashboard.
 *
 * Exported separately from the hook so the parsing rule can be tested
 * without mounting a router.
 */
export function parseMode(raw: string | null): Mode {
  return raw === RETAIL_PARAM_VALUE ? "retail" : "consumer";
}

/**
 * Mode rides in the URL and nowhere else — no store, no context, no
 * `localStorage` (decision S2). The URL is the state of record, exactly as it
 * already is for `lang` (see `useLang`), which keeps every view shareable and
 * means a reload cannot disagree with the address bar.
 */
export function useMode(): [Mode, (m: Mode) => void] {
  const [searchParams, setSearchParams] = useSearchParams();
  const mode = parseMode(searchParams.get("mode"));

  const setMode = (m: Mode) => {
    const next = new URLSearchParams(searchParams);
    // Consumer is the default, so it is the ABSENCE of the param rather than
    // `mode=consumer`. One canonical URL per mode.
    if (m === "consumer") next.delete("mode");
    else next.set("mode", RETAIL_PARAM_VALUE);
    setSearchParams(next, { replace: true });
  };

  return [mode, setMode];
}
