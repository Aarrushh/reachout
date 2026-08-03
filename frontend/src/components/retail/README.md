# `components/retail/` — the shopkeeper half

Declared by task **U0**, populated by **U2**, **U3** and **U6**. Empty on
purpose right now.

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
