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
  onClose: () => void;
}

const SUGGESTIONS: StringKey[] = ["chat.suggestStock", "chat.suggestPrice", "chat.suggestReserve"];

export default function ChatPanel({ ctx, lang, onClose }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [typing, setTyping] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

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

  return (
    <div className="chat-scrim" onClick={onClose}>
      <aside className="chat-panel" role="dialog" aria-label={t(lang, "chat.title", { shop: ctx.shopName })}
        onClick={(e) => e.stopPropagation()}>
        <header className="chat-header">
          <div>
            <h3>{ctx.shopName}</h3>
            <p className="microcaps chat-sub">
              <span className="chat-open-dot" aria-hidden="true" /> {t(lang, "chat.openNow")} · {ctx.itemName}
            </p>
          </div>
          <button className="chat-close" onClick={onClose} aria-label={t(lang, "chat.close")}>✕</button>
        </header>
        <div className="chat-log" ref={logRef}>
          <p className="chat-notice microcaps">{t(lang, "chat.mockNotice")}</p>
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
    </div>
  );
}
