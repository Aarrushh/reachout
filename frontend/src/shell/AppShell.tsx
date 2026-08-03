import type { ReactNode } from "react";

import { useLang } from "../hooks/useLang";
import { t } from "../i18n/strings";
import ModeToggle from "./ModeToggle";
import { useMode } from "./useMode";
import "./shell.css";

/**
 * The one shell both halves of the app live inside.
 *
 * Consumer mode renders the routes it wraps — the existing search and results
 * screens, unchanged. Retail mode renders its own surface instead, which as
 * of U0 is a placeholder: the chat pane arrives in U2, the charts in U3, the
 * disabled AI button in U6. The placeholder says so rather than showing an
 * empty frame that looks broken.
 *
 * The shell holds no mode state. `useMode` derives it from the URL on every
 * render (decision S2).
 */
export default function AppShell({ children }: { children: ReactNode }) {
  const [mode] = useMode();
  const [lang] = useLang();

  return (
    <div className="app-shell" data-mode={mode}>
      <header className="app-shell__bar">
        <span className="app-shell__brand">ReachOut</span>
        <ModeToggle />
      </header>
      <main className="app-shell__body">
        {mode === "retail" ? (
          <section className="retail-placeholder" aria-labelledby="retail-placeholder-title">
            <h1 id="retail-placeholder-title" className="retail-placeholder__title">
              {t(lang, "retail.title")}
            </h1>
            <p className="retail-placeholder__note">{t(lang, "retail.placeholder")}</p>
          </section>
        ) : (
          children
        )}
      </main>
    </div>
  );
}
