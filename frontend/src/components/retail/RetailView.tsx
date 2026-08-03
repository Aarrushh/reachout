import { useLang } from "../../hooks/useLang";
import { t } from "../../i18n/strings";
import AiAnalystButton from "./AiAnalystButton";
import RetailChatPane from "./RetailChatPane";
import RetailDashboard from "./RetailDashboard";
import "./retail.css";

/**
 * Everything behind `?mode=retail`: chat on the left, dashboard on the right.
 */
export default function RetailView() {
  const [lang] = useLang();

  return (
    <div className="retail-split">
      <div className="retail-split__chat">
        <RetailChatPane lang={lang} />
      </div>
      <section className="retail-split__dash" aria-labelledby="retail-dash-title">
        <header className="retail-dash__head">
          <h1 id="retail-dash-title" className="retail-dash__title">{t(lang, "retail.title")}</h1>
          <AiAnalystButton lang={lang} />
        </header>
        <RetailDashboard lang={lang} />
      </section>
    </div>
  );
}
