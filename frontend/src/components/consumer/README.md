# `components/consumer/` — the shopper half

Declared by task **U0**, populated by **U1** (2026-08-03). The boundary was
drawn before anything crossed it, so U1 was a pure re-home: `git mv` plus one
level of `../` on the imports, no behaviour change and no logic touched.

**What belongs here:** every component reachable when `?mode=` is absent —
search entry, results list, the map, shop cards, the picks rail (U4).

**What does not:** anything the retail dashboard renders. If a component is
needed by both halves it stays in `components/` proper and is imported by
each; it does not get copied into both trees.

Here now: `SearchInput`, `BarrioCombobox`, `TopBar`, `ResultsPanel`,
`ShopCard`, `MapPanel`, `MapOverlay` (all unchanged from U1), `PicksRail`
(U4), plus the two stylesheets only these screens import — `entry.css` and
`results.css`.

**`PicksRail` disappears instead of complaining.** Loading, a failed fetch
and an empty list all render `null` — no heading, no skeleton, no reserved
space. It sits on the landing page beside the search box, and an error
banner there would tell a shopper the site is broken while the thing they
came for still works. Its heading is *"popular near you"*, not *"for you"*:
`GET /api/picks` ranks by store rating and round-robins categories with no
per-shopper signal at all (`generated_by: "deterministic"`), so copy
implying personalisation would be a claim the backend cannot support.

**`InstallPrompt` (U5) is consumer-only, and that is a rule, not a layout
choice.** It renders `null` until the browser fires `beforeinstallprompt`,
because without that event there is no prompt to open and the button would do
nothing when pressed. Retail mode never mounts it: an offline-capable shell
installed around a shopkeeper's dashboard is the exact outcome U5 exists to
prevent. The cache rule itself lives in `public/sw.js`, which is the only
place it can be enforced — see that file's header.

`ChatPanel.tsx` and `chat.css` stayed in `components/` proper on purpose:
retail mode reuses that exact component from U2, and a component both halves
need belongs to neither tree.
