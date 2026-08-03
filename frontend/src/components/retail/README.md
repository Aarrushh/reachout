# `components/retail/` — the shopkeeper half

Declared by task **U0**. **U2 and U6 have landed**: `RetailView` is the
two-column surface behind `?mode=retail`, with `RetailChatPane` on the left
and `AiAnalystButton` heading the right. U3 (charts) fills the rest.

**`AiAnalystButton` is wired to nothing on purpose** (U6). It is `disabled`
*and* `aria-disabled`, has no `onClick`, and this file imports no fetcher —
if a future edit gives it a handler, it stops being the thing the plan asked
for. Its "not available yet" reason is a caption bound by `aria-describedby`,
not a `title`: a shopkeeper on a phone cannot hover, and a greyed button with
no reachable explanation reads as a broken app rather than an unbuilt feature.

**What belongs here:** everything reachable only at `?mode=retail` — the chat
pane (U2, reusing the existing `ChatPanel` and its client-side mock), the
three analytics charts under `retail/charts/` (U3), and the disabled "ask AI
about my analytics" button (U6).

**Two rules this tree carries that the consumer tree does not:**

1. **The frontend draws; it does not compute.** Every number rendered by a
   chart is computed server-side by `GET /demand/api/analytics`. No
   arithmetic here beyond axis formatting — a percentage the browser worked
   out is a number nobody validated against a schema.
2. **Confidence and caveat are always visible**, as a chip and a caption, not
   a tooltip. A number whose honesty label is one hover away is a number
   presented as more certain than it is.

**U5 note:** the service worker's precache must exclude everything in this
tree. An offline shell must never serve a stale dashboard.

## The chat pane's sample data — read before touching it

`RetailChatPane` quotes a stock level ("12 units right now"). Retail mode has
no store picker and no inventory sync, so that number comes from
`SAMPLE_CONTEXT`, a constant. The pane therefore carries an always-visible
notice saying the shop and stock are samples, and a test asserts that notice
in both languages.

That test is not ceremony. A chat that quotes an invented stock figure to a
shopkeeper about their **own** shop is indistinguishable, to them, from their
real till. When inventory sync lands, replace the constant and delete the
notice together — never one without the other.

The pane reuses `components/ChatPanel.tsx` through its `variant="pane"` prop
rather than reimplementing it. Two copies of one chat are two chats that
drift.
