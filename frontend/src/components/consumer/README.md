# `components/consumer/` — the shopper half

Declared by task **U0**, populated by **U1** (2026-08-03). The boundary was
drawn before anything crossed it, so U1 was a pure re-home: `git mv` plus one
level of `../` on the imports, no behaviour change and no logic touched.

**What belongs here:** every component reachable when `?mode=` is absent —
search entry, results list, the map, shop cards, the picks rail (U4).

**What does not:** anything the retail dashboard renders. If a component is
needed by both halves it stays in `components/` proper and is imported by
each; it does not get copied into both trees.

Here now, unchanged: `SearchInput`, `BarrioCombobox`, `TopBar`,
`ResultsPanel`, `ShopCard`, `MapPanel`, `MapOverlay`, plus the two
stylesheets only these screens import — `entry.css` and `results.css`.

`ChatPanel.tsx` and `chat.css` stayed in `components/` proper on purpose:
retail mode reuses that exact component from U2, and a component both halves
need belongs to neither tree.
