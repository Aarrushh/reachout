import { t } from "../../i18n/strings";
import type { Lang } from "../../i18n/strings";

/**
 * Task U6: the "ask AI about my analytics" button, deliberately dead.
 *
 * It exists to mark a planned feature, so it must be impossible to mistake
 * for a working one: `disabled` (so no pointer, keyboard, or programmatic
 * click reaches anything), `aria-disabled` alongside it (so a screen reader
 * announces the state even where a toolkit strips the native attribute),
 * no `onClick`, and no fetcher imported anywhere in this file.
 *
 * The reason it is unavailable is a caption, not a `title` tooltip. A
 * shopkeeper on a phone has no hover, and a tooltip they cannot open leaves
 * a greyed-out button with no explanation — which reads as a bug in the app
 * rather than a feature that has not shipped.
 */
export default function AiAnalystButton({ lang }: { lang: Lang }) {
  return (
    <div className="retail-askai">
      <button
        type="button"
        className="retail-askai__button"
        disabled
        aria-disabled="true"
        aria-describedby="retail-askai-why"
      >
        {t(lang, "retail.askAi")}
      </button>
      <p id="retail-askai-why" className="retail-askai__why">
        {t(lang, "retail.askAiUnavailable")}
      </p>
    </div>
  );
}
