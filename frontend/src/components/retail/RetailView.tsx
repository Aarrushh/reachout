import { useLang } from "../../hooks/useLang";
import { t } from "../../i18n/strings";
import RetailChatPane from "./RetailChatPane";
import "./retail.css";

/**
 * Everything behind `?mode=retail`: chat on the left, dashboard on the right.
 *
 * The right column is a placeholder until U3 brings the three charts and U6
 * the disabled AI button. It says what is missing rather than showing an
 * empty frame — an unexplained blank panel reads as a broken dashboard, and
 * a shopkeeper cannot tell those two apart.
 */
export default function RetailView() {
  const [lang] = useLang();

  return (
    <div className="retail-split">
      <div className="retail-split__chat">
        <RetailChatPane lang={lang} />
      </div>
      <section className="retail-split__dash" aria-labelledby="retail-dash-title">
        <h1 id="retail-dash-title" className="retail-dash__title">{t(lang, "retail.title")}</h1>
        <p className="retail-dash__note">{t(lang, "retail.placeholder")}</p>
      </section>
    </div>
  );
}
