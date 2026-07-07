import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";

import type { Lang } from "../i18n/strings";

/** Language rides in the URL (`lang=en`; absent means Spanish) so views stay
 * shareable — the URL is the state of record. */
export function useLang(): [Lang, (l: Lang) => void] {
  const [searchParams, setSearchParams] = useSearchParams();
  const lang: Lang = searchParams.get("lang") === "en" ? "en" : "es";
  // Keep screen readers / translators honest about the UI language.
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);
  const setLang = (l: Lang) => {
    const next = new URLSearchParams(searchParams);
    if (l === "es") next.delete("lang");
    else next.set("lang", l);
    setSearchParams(next, { replace: true });
  };
  return [lang, setLang];
}
