# Moving ReachOut to another work computer

*Written 2026-08-17. Source machine: `~/Desktop/reachout`, macOS, Python 3.12.13,
Node 26.5.1. Verified against the live tree, not from memory.*

The reassuring part first: **a fresh `git clone` loses zero source code.** Working
tree clean, no stashes, `main` at `958080a` = `origin/main`. Two local-only branch
*names* (`redesign/bklit-reactbits-v3`, `serpapi-demand-ingest`) point at commits
already reachable from `origin/main`, so only the labels disappear.

What does *not* survive a clone is roughly **4 MB of hand-written context** plus
seven credential values. Everything else — 410 MB of `node_modules`, `.venv`,
`dist`, the SQLite DB, caches — rebuilds from commands in the README. Do not copy it.

## 1. The irreplaceable list

Ranked by the work each represents.

| # | What | Where | Size |
|---|---|---|---|
| 1 | SDD campaign ledgers — 4 campaigns of task briefs, per-task reports, progress ledgers (676 / 448 / 436 / 201 lines) | `.superpowers/` (git-ignored) | 1.0 MB of `.md` (98 files) |
| 2 | Plan "Demand dashboard: go live, add timeframe toggle, expose discovery" — exists nowhere in git | `~/.claude/plans/recursive-enchanting-snowflake.md` | 12.8 KB |
| 3 | Project memory — 5 hardened operational lessons + index | `~/.claude/projects/-Users-rajeshgupta-Desktop-reachout/memory/` | 24 KB, 6 files |
| 4 | Credentials — 7 key names across two files | `.env`, `reachout/.env` | 2 files |
| 5 | 214 permission-allow entries + `skillOverrides.verify` + a SessionStart hook | `.claude/settings.local.json` | 20 KB |
| 6 | Global Claude config: 11 plugins, 6 marketplaces, 3 hooks | `~/.claude/settings.json`, `~/.claude/RTK.md` | 3.5 KB |
| 7 | *Optional* — session transcripts | `~/.claude/projects/-Users-rajeshgupta-Desktop-reachout*/` | 78 MB |

**The 47 review `.diff` / `.txt` files in `.superpowers/` (2.4 MB) are NOT on this
list.** They are named for the commit ranges they cover (`review-b8dc220..0d77983.diff`),
and every one of those commits is on `origin/main`. Regenerate any of them with
`git diff b8dc220..0d77983`. Move the markdown only.

Two pairs are split across the git boundary and are easy to break:

- Item 2's plan lives outside the repo; its execution ledger is inside
  `.superpowers/sdd/recursive-enchanting-snowflake/`. Its two sibling plans *are*
  committed at `docs/superpowers/plans/`. Move the odd one out to join them.
- Item 1's V3 ledger tail holds **five post-merge follow-ups recorded nowhere else**.
  Those are being promoted to GitHub issues so they survive independently of the file.

`.claude/skills/verify/SKILL.md` is **tracked** — it arrives with the clone, nothing to do.

## 2. Getting the context across

The repo is **public** (`github.com/Aarrushh/reachout`). Items 1–3 are internal working
notes and personal memory: they contain no secrets (scanned), but committing them to a
public repo is permanent and world-readable. Pick a lane deliberately.

**Option A — private repo (recommended).** One command on the old machine, one on the new:

```bash
# old machine
gh repo create reachout-context --private
mkdir -p /tmp/ctx && cd /tmp/ctx && git init
rsync -a --include='*/' --include='*.md' --exclude='*' \
  ~/Desktop/reachout/.superpowers/ ./superpowers/
cp ~/.claude/plans/recursive-enchanting-snowflake.md ./
cp -R ~/.claude/projects/-Users-rajeshgupta-Desktop-reachout/memory ./memory
git add -A && git commit -m "context snapshot 2026-08-17"
git remote add origin https://github.com/Aarrushh/reachout-context.git
git push -u origin main
```

**Option B — commit into this public repo** under `docs/ledger/`. Cheapest to reach on
the new machine (already cloning it), permanent and public. Only if you are content for
the ledgers to be read by anyone.

**Option C — no network.** `tar czf reachout-context.tgz` the same three paths onto a
USB stick. Zero exposure, manual.

Credentials (item 4) go through **none** of these. Re-issue them on the new machine from
each provider's dashboard: `SUPABASE_URL`, `SUPABASE_KEY`, `SERPAPI_API_KEY` in
`reachout/.env`; `JULES_API_KEY`, `GEMINI_FLASH_LITE_API_KEY`, `STITCH_API_KEY` in the
root `.env`. Shapes are documented in the tracked `reachout/.env.example`.

## 3. New machine, from zero

```bash
# 1. code
git clone https://github.com/Aarrushh/reachout.git && cd reachout

# 2. runtimes — Python 3.10+ (3.12 here), Node 20+ (26.5.1 here)
python3 -m venv .venv
./.venv/bin/pip install -r reachout/requirements.txt -r demand/requirements.txt
cd frontend && npm install && cd ..

# 3. credentials, by hand
cp reachout/.env.example reachout/.env    # then fill in, values re-issued not copied

# 4. context payload — whichever option you chose in §2
git clone https://github.com/Aarrushh/reachout-context.git ../reachout-context
cp -R ../reachout-context/memory \
  ~/.claude/projects/-Users-rajeshgupta-Desktop-reachout/memory

# 5. tooling the Claude config assumes on PATH
#    `rtk` and `~/.local/bin/headroom` — without them every Bash call
#    and every session start errors. Install before opening Claude Code.

# 6. run it (three terminals) — see README.md §"Running it locally"
```

Then verify, in this order:

```bash
./.venv/bin/python -m pytest reachout/tests demand/tests   # expect 694 collected
cd frontend && npm run build > /tmp/build.log 2>&1          # NEVER foreground — it hangs
cd frontend && npm test
```

First search bootstraps `reachout/data/reachout.db` from the committed OSM cache:
3,328 shops, 60,513 synthetic inventory rows, 24 barrios, ~1 minute, once.

## 4. Traps that already cost time here

Each of these is a memory file on the old machine; they are repeated here because the
memory directory may not arrive before you first run something.

- **`npm run build` hangs forever in the foreground.** Redirect to a file and it
  finishes in ~5 s. A stalled build is not a broken build.
- **`REACHOUT_SIM=1` crashloops silently without `PYTHONPATH=..`.** Every HTTP endpoint
  still returns 200 while the 2-second simulator tick raises
  `ModuleNotFoundError: No module named 'reachout'` forever, visible only in the log.
- **Use `localhost`, never `127.0.0.1`.** Both APIs restrict CORS to
  `http://localhost:5173`; `vite preview` on `:4173` is blocked outright.
- **`DEMAND_ANALYTICS_SOURCE` fails safe, not loud.** Any value other than `live` —
  including a typo or an empty string — silently serves fixture data behind a "practice
  data" banner.
- **The retail dashboard is `?mode=retail`** on any route. There is no separate route.
- **Analytics params are `inventory_type` (not `category`)** and timeframes like
  `today 3-m`; anything else gives `422 Unsupported timeframe`.

## 5. Leaving the old machine

Three services are still up (ports 8001 / 8000 / 5173). Stop them when you are done:
`lsof -nP -iTCP -sTCP:LISTEN | grep -E '8000|8001|5173'`, then `kill` the PIDs.

Do not delete `~/Desktop/reachout` until the new machine has passed §3's verification
and the §2 payload is confirmed readable there. The 4 MB that matters exists in exactly
one place until then.
