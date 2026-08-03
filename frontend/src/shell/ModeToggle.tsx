import { useLang } from "../hooks/useLang";
import { t } from "../i18n/strings";
import { useMode } from "./useMode";

/**
 * Top-right switch between the shopper half and the shopkeeper half.
 *
 * It writes `?mode=` and reads nothing else: the button's own appearance is
 * derived from the URL on every render, so the address bar can never disagree
 * with what is on screen.
 */
export default function ModeToggle() {
  const [mode, setMode] = useMode();
  const [lang] = useLang();
  const isRetail = mode === "retail";

  return (
    <button
      type="button"
      className="mode-toggle microcaps"
      // A switch, not a link: aria-pressed is what tells a screen reader
      // which half is currently showing.
      aria-pressed={isRetail}
      onClick={() => setMode(isRetail ? "consumer" : "retail")}
    >
      {t(lang, isRetail ? "mode.switchToConsumer" : "mode.switchToRetail")}
    </button>
  );
}
