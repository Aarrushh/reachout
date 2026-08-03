import type { ReactNode } from "react";

import RetailView from "../components/retail/RetailView";
import ModeToggle from "./ModeToggle";
import { useMode } from "./useMode";
import "./shell.css";

/**
 * The one shell both halves of the app live inside.
 *
 * Consumer mode renders the routes it wraps — the existing search and results
 * screens, unchanged. Retail mode renders `RetailView` INSTEAD of them: chat
 * pane left (U2), dashboard right (charts in U3, the disabled AI button in
 * U6). "Instead of", not "on top of" — a consumer tree that is merely hidden
 * is still reachable by a screen reader and, from U5, by the offline cache.
 *
 * The shell holds no mode state. `useMode` derives it from the URL on every
 * render (decision S2).
 */
export default function AppShell({ children }: { children: ReactNode }) {
  const [mode] = useMode();

  return (
    <div className="app-shell" data-mode={mode}>
      <header className="app-shell__bar">
        <span className="app-shell__brand">ReachOut</span>
        <ModeToggle />
      </header>
      <main className="app-shell__body">
        {mode === "retail" ? <RetailView /> : children}
      </main>
    </div>
  );
}
