/** Slide-over shopkeeper chat. History lives here and dies on unmount
 * (closing the panel clears the session by design). Lazy-loaded from
 * results.tsx so the chat code stays out of the initial bundle. */
import { useEffect, useRef, useState } from "react";

import { sendChatMessage, type ChatMessage, type ShopContext } from "../chat/shopkeeper";
import { t, type Lang, type StringKey } from "../i18n/strings";
import "./chat.css";

interface Props {
  ctx: ShopContext;
  lang: Lang;
  /** Required in `overlay`; meaningless in `pane`, which has nothing to close. */
  onClose?: () => void;
  /**
   * How the same chat is presented.
   *
   * `overlay` (default) is the consumer slide-over: scrim, dialog role,
   * Escape to close. `pane` is retail mode's permanent left column: no scrim,
   * no dialog role, no close button — a pane that is always there is not a
   * dialog, and announcing it as one would make a screen reader wait for it
   * to be dismissed.
   *
   * A variant rather than a second component on purpose: the conversation
   * logic, the mock engine and the suggestion chips are the same in both
   * halves, and two copies of a chat are two chats that drift.
   */
  variant?: "overlay" | "pane";
  /** Extra line under the header. Retail uses it to say the figures are samples. */
  notice?: string;
}

const SUGGESTIONS: StringKey[] = ["chat.suggestStock", "chat.suggestPrice", "chat.suggestReserve"];

export default function ChatPanel({ ctx, lang, onClose, variant = "overlay", notice }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [typing, setTyping] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const isOverlay = variant === "overlay";

  useEffect(() => {
    // A pane does not steal focus: it is one of two columns on the screen,
    // and grabbing the caret on load would fight whatever the shopkeeper is
    // actually reading.
    if (isOverlay) inputRef.current?.focus();
    if (!isOverlay || !onClose) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, isOverlay]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [messages, typing]);

  function send(text: string) {
    const content = text.trim();
    if (!content || typing) return;
    const history = [...messages, { role: "user", content } as const];
    setMessages(history);
    setDraft("");
    setTyping(true);
    void sendChatMessage(ctx, content, history, lang).then(({ reply }) => {
      setTyping(false);
      setMessages((m) => [...m, { role: "assistant", content: reply }]);
    });
  }

  const body = (
    <aside
      className={isOverlay ? "chat-panel" : "chat-panel chat-panel--pane"}
      {...(isOverlay ? { role: "dialog", "aria-label": t(lang, "chat.title", { shop: ctx.shopName }) } : {})}
      onClick={isOverlay ? (e) => e.stopPropagation() : undefined}
    >
        <header className="chat-header">
          <div>
            <h3>{ctx.shopName}</h3>
            <p className="microcaps chat-sub">
              <span className="chat-open-dot" aria-hidden="true" /> {t(lang, "chat.openNow")} · {ctx.itemName}
            </p>
          </div>
          {isOverlay && onClose && (
            <button className="chat-close" onClick={onClose} aria-label={t(lang, "chat.close")}>✕</button>
          )}
        </header>
        <div className="chat-log" ref={logRef}>
          <p className="chat-notice microcaps">{t(lang, "chat.mockNotice")}</p>
          {notice && <p className="chat-notice microcaps">{notice}</p>}
          {messages.length === 0 && (
            <div className="chat-suggestions">
              {SUGGESTIONS.map((k) => (
                <button key={k} className="chat-chip" onClick={() => send(t(lang, k))}>
                  {t(lang, k)}
                </button>
              ))}
            </div>
          )}
          {messages.map((m, i) => (
            <p key={i} className={`chat-bubble ${m.role}`}>{m.content}</p>
          ))}
          {typing && (
            <p className="chat-bubble assistant chat-typing" aria-label={t(lang, "chat.typing")}>
              <span /><span /><span />
            </p>
          )}
        </div>
        <form className="chat-input-row" onSubmit={(e) => { e.preventDefault(); send(draft); }}>
          <input ref={inputRef} value={draft} onChange={(e) => setDraft(e.target.value)}
            placeholder={t(lang, "chat.placeholder")} />
          <button type="submit" className="chat-send" disabled={!draft.trim() || typing}>
            {t(lang, "chat.send")}
          </button>
        </form>
    </aside>
  );

  if (!isOverlay) return body;
  return (
    <div className="chat-scrim" onClick={onClose}>
      {body}
    </div>
  );
}
