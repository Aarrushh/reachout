import { useEffect, useState } from "react";

import { t } from "../../i18n/strings";
import type { Lang } from "../../i18n/strings";

/**
 * The "install this app" button (U5), consumer mode only.
 *
 * The browser fires `beforeinstallprompt` when it judges the app installable.
 * That event is the ONLY way to show this button honestly: without it there
 * is no prompt to open, so a button rendered anyway would be a control that
 * does nothing when pressed. It therefore starts absent and appears only once
 * the event arrives — and disappears for good once the app is installed.
 *
 * Retail mode never renders it. A shopkeeper installing an offline-capable
 * shell around a dashboard is precisely the outcome U5 exists to prevent.
 */
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export default function InstallPrompt({ lang }: { lang: Lang }) {
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null);

  useEffect(() => {
    function onPrompt(event: Event) {
      event.preventDefault();
      setDeferred(event as BeforeInstallPromptEvent);
    }
    function onInstalled() {
      setDeferred(null);
    }

    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  if (!deferred) return null;

  return (
    <button
      type="button"
      className="install-prompt microcaps"
      onClick={() => {
        // One shot: the browser will not replay a deferred prompt, so the
        // button goes whether they accept or dismiss.
        void deferred.prompt();
        setDeferred(null);
      }}
    >
      ⤓ {t(lang, "pwa.install")}
    </button>
  );
}
