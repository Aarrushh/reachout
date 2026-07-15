/**
 * Shopkeeper chat: types match SHARED_CONTRACT.md's POST /api/chat so the
 * backend can slot in later — today `sendChatMessage` is a local mock because
 * the endpoint doesn't exist yet (PHASE_3_CHAT_READY unset). The mock only
 * speaks from real search-result data (item, price, stock, shop) passed in;
 * it never invents inventory.
 */
import type { Lang } from "../i18n/strings";
import { formatPrice } from "../lib/format";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

/** The real-result context the mock answers from. */
export interface ShopContext {
  shopId: string;
  shopName: string;
  itemName: string;
  price: number;
  stockQty: number;
}

const RE_STOCK = /stock|quedan|hay|tienes|tenéis|available|left|disponible/i;
const RE_PRICE = /precio|cuesta|cuánto|cuanto|price|cost|how much|vale/i;
const RE_RESERVE = /reserva|guarda|aparta|apártame|hold|reserve|keep/i;
const RE_HOURS = /horario|abierto|cierra|abre|open|close|hours/i;
const RE_GREET = /^(hola|buenas|hey|hi|hello|good|buenos)/i;

/** Pure reply composer — exported for unit tests. */
export function composeReply(ctx: ShopContext, message: string, lang: Lang): string {
  const price = formatPrice(ctx.price);
  const es = lang === "es";
  if (RE_RESERVE.test(message)) {
    if (ctx.stockQty < 1)
      return es
        ? `Ahora mismo no me queda ${ctx.itemName}, lo siento. Pregúntame en un rato por si entra reposición.`
        : `I'm out of ${ctx.itemName} right now, sorry. Check back soon in case we restock.`;
    return es
      ? `Hecho — te guardo 1 unidad de ${ctx.itemName} durante una hora a nombre tuyo. Son ${price} al recogerlo.`
      : `Done — I'll hold 1 × ${ctx.itemName} for you for one hour. It's ${price} when you pick it up.`;
  }
  if (RE_STOCK.test(message)) {
    if (ctx.stockQty > 5)
      return es
        ? `Sí, tenemos ${ctx.itemName} en stock (${ctx.stockQty} unidades ahora mismo).`
        : `Yes, ${ctx.itemName} is in stock (${ctx.stockQty} units right now).`;
    if (ctx.stockQty >= 1)
      return es
        ? `Quedan solo ${ctx.stockQty} de ${ctx.itemName} — si lo quieres te lo puedo apartar.`
        : `Only ${ctx.stockQty} of ${ctx.itemName} left — I can hold one for you if you want.`;
    return es
      ? `Se nos ha agotado ${ctx.itemName} hace un rato, lo siento.`
      : `We just sold out of ${ctx.itemName}, sorry.`;
  }
  if (RE_PRICE.test(message)) {
    return es
      ? `${ctx.itemName} está a ${price}.`
      : `${ctx.itemName} is ${price}.`;
  }
  if (RE_HOURS.test(message)) {
    return es
      ? `Estamos abiertos ahora — de lunes a sábado, 9:30 a 21:00.`
      : `We're open now — Monday to Saturday, 9:30 to 21:00.`;
  }
  if (RE_GREET.test(message)) {
    return es
      ? `¡Hola! Soy de ${ctx.shopName}. ¿Te ayudo con ${ctx.itemName} o buscas otra cosa?`
      : `Hi! This is ${ctx.shopName}. Can I help you with ${ctx.itemName}, or are you after something else?`;
  }
  return es
    ? `Te leo — sobre ${ctx.itemName} puedo decirte precio (${price}) y stock, o apartártelo. ¿Qué necesitas?`
    : `I hear you — for ${ctx.itemName} I can tell you the price (${price}) and stock, or hold one for you. What do you need?`;
}

/**
 * SHARED_CONTRACT shape: { store_id, message, history } → { reply }.
 * Swap this body for a fetch to POST /api/chat when the backend ships it.
 */
export function sendChatMessage(
  ctx: ShopContext,
  message: string,
  _history: ChatMessage[],
  lang: Lang,
): Promise<{ reply: string }> {
  const text = composeReply(ctx, message, lang);
  // 600–1400ms scaled by length: long enough that the typing dots register.
  const delay = 600 + Math.min(800, text.length * 8);
  return new Promise((resolve) => setTimeout(() => resolve({ reply: text }), delay));
}
