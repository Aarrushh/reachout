# `components/consumer/` — the shopper half

Declared by task **U0**, populated by **U1**. Empty on purpose right now: the
boundary is drawn before anything moves across it, so the move in U1 is a
pure re-home with no design decisions left in it.

**What belongs here:** every component reachable when `?mode=` is absent —
search entry, results list, the map, shop cards, the picks rail (U4).

**What does not:** anything the retail dashboard renders. If a component is
needed by both halves it stays in `components/` proper and is imported by
each; it does not get copied into both trees.

U1 moves these in, unchanged: `SearchInput`, `BarrioCombobox`, `TopBar`,
`ResultsPanel`, `ShopCard`, `MapPanel`, `MapOverlay`.
