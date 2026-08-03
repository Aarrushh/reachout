import ChatPanel from "../ChatPanel";
import type { ShopContext } from "../../chat/shopkeeper";
import { t, type Lang } from "../../i18n/strings";

/**
 * The sample shop the preview answers about.
 *
 * These numbers are invented, and that is exactly why the pane says so on
 * screen: retail mode has no store picker and no inventory sync yet, so
 * there is no real stock level to answer from. A chat that quoted a made-up
 * "7 units" to a shopkeeper about their OWN shop would be the worst kind of
 * fabrication this product can ship — the reader has no way to tell it apart
 * from their real till.
 *
 * When inventory sync lands, this constant is what gets replaced by the
 * shopkeeper's real context, and the sample-data notice goes with it.
 */
const SAMPLE_CONTEXT: ShopContext = {
  shopId: "sample",
  shopName: "Alimentación Lavapiés",
  itemName: "agua mineral 1,5 L",
  price: 0.89,
  stockQty: 12,
};

/**
 * Retail mode's left column: the same chat a shopper sees, so the shopkeeper
 * can read what their customers get. Client-side mock only — no backend, no
 * `POST /api/chat`, no AI (`chat/shopkeeper.ts` composes every reply from the
 * context above with plain string templates).
 */
export default function RetailChatPane({ lang }: { lang: Lang }) {
  return (
    <ChatPanel
      ctx={SAMPLE_CONTEXT}
      lang={lang}
      variant="pane"
      notice={t(lang, "retail.chatSampleNotice")}
    />
  );
}
