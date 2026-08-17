# Leaning the folder out for a Google Drive handoff

*Measured 2026-08-17 on the source machine. Companion to
`docs/MIGRATION_NEW_MACHINE.md`, which covers the other end — setting the new
machine up. This file covers what to delete first and what actually belongs in Drive.*

> **Status: Phases 1–3 were executed on 2026-08-18.** The folder went **452 MB → 16 MB**
> and the handoff archive is built at `~/reachout-handoff-20260818.tgz` (324 KB, 116
> files). The credential files were deliberately **left out** of the archive — see Phase 3.
> **This machine can no longer run the app** until `npm install` and the venv are
> recreated (Phase 1's table has both commands). That is the intended trade, not a fault.

## The number that decides everything

```
452 MB total
├── 277 MB  frontend/          (274 MB of it is node_modules — 16,498 files)
├── 136 MB  .venv/             (6,319 files)
├──  25 MB  reachout/          (13 MB of it is the SQLite DB)
├── 8.2 MB  .git/
├── 3.5 MB  .superpowers/      (git-ignored ledgers)
└── 1.8 MB  demand/
```

**410 MB of that — 22,817 files — is rebuildable from two commands.** Uploading it to
Drive costs you an hour and buys nothing.

## Phase 1 — delete the regenerable bulk (safe, local)

| Delete | Frees | How it comes back |
|---|---|---|
| `frontend/node_modules/` | 274 MB, 16,498 files | `cd frontend && npm install` (`package-lock.json` is committed) |
| `.venv/` | 136 MB, 6,319 files | `python3 -m venv .venv && ./.venv/bin/pip install -r reachout/requirements.txt -r demand/requirements.txt` |
| `frontend/dist/` | 1.6 MB | `npm run build` — **redirect to a file, it hangs in the foreground** |
| `reachout/.serena/`, `.serena/` | 1.9 MB | Serena MCP symbol cache; rebuilt on first use |
| 12 × `__pycache__/`, 4 × `.pytest_cache/` | ~130 KB | Automatic |
| 6 × `.DS_Store` | 16 KB | Finder recreates them; never wanted |

```bash
cd ~/Desktop/reachout
rm -rf frontend/node_modules .venv frontend/dist .serena reachout/.serena
find . -name __pycache__ -type d -prune -exec rm -rf {} +
find . -name .pytest_cache -type d -prune -exec rm -rf {} +
find . -name .DS_Store -delete
```

**452 MB → ~38 MB.**

## Phase 2 — the regenerable-but-slower data

Judgement call, all three are safe to drop:

| Delete | Frees | How it comes back |
|---|---|---|
| `reachout/data/reachout.db` | 13 MB | Bootstraps itself on the first search from the committed OSM cache: 3,328 shops, 60,513 rows, 24 barrios, ~1 minute |
| `reachout/data/notifications/` | 3.3 MB, 803 files | Per-shop ping inboxes written on every run. Historical pings are lost; nothing reads them across machines |
| `reachout/data/events.jsonl` | 2.5 MB | Simulator event log, recreated on next run |

**~38 MB → 16 MB measured**, of which 8.2 MB is `.git`. (Better than the ~19 MB estimate;
the Serena caches and `__pycache__` dirs were larger than counted.)

Two things that made this safe and are easy to get wrong if you repeat it elsewhere:

- **Stop the three services first.** The two Python APIs hold `reachout.db` open and Vite
  holds `node_modules`; deleting underneath them leaves a half-deleted tree and a
  recreated DB. `lsof -nP -iTCP -sTCP:LISTEN | grep -E '8000|8001|5173'`, then `kill`.
- **`reachout/data/notifications/.gitkeep` is tracked** while the 803 files beside it are
  not. Delete the contents, keep the `.gitkeep`, or `git status` reports a deletion:
  `find reachout/data/notifications -type f ! -name .gitkeep -delete`.

## Phase 3 — what actually belongs in Drive

Here is the thing worth being precise about: **the code should not travel through Drive
at all.** It is already on GitHub, pushed and clean. Drive's job is the ~4 MB that
*cannot* go to GitHub, because `github.com/Aarrushh/reachout` is a **public** repo.

That makes Drive the answer to the question the migration runbook left open.

| Goes to Drive | Why not GitHub |
|---|---|
| `.superpowers/**/*.md` — 1.0 MB, 98 files: four SDD campaigns of briefs, reports and progress ledgers | Internal working notes. Public repo. |
| `.env` and `reachout/.env` — 7 keys | **Never** commit credentials, least of all to a public repo |
| `~/.claude/plans/recursive-enchanting-snowflake.md` | Exists nowhere in git; pairs with its ledger above |
| `~/.claude/projects/-Users-rajeshgupta-Desktop-reachout/memory/` — 6 files | Personal memory |
| `.claude/settings.local.json` — 214 permission entries | Machine config; rebuilding means re-approving 214 prompts |

**Do not include the 47 review `.diff` / `.txt` files (2.4 MB).** They are named for commit
ranges that are all on `origin/main` — `git diff b8dc220..0d77983` regenerates any of them.

```bash
cd ~ && mkdir -p handoff
rsync -a --include='*/' --include='*.md' --exclude='*' \
  Desktop/reachout/.superpowers/ handoff/superpowers/
cp Desktop/reachout/.claude/settings.local.json handoff/
cp .claude/plans/recursive-enchanting-snowflake.md handoff/
cp -R .claude/projects/-Users-rajeshgupta-Desktop-reachout/memory handoff/memory
cp Desktop/reachout/docs/MIGRATION_NEW_MACHINE.md \
   Desktop/reachout/docs/DRIVE_HANDOFF.md handoff/
tar czf reachout-handoff-20260818.tgz handoff && du -h reachout-handoff-20260818.tgz
```

**Built: `~/reachout-handoff-20260818.tgz`, 324 KB, 116 files** — 98 `.superpowers`
markdown files, 6 memory files, the plan, `settings.local.json`, and both runbooks.
Upload that one file.

**The `.env` files are deliberately not in it.** Re-issue those seven values on the new
machine from each provider's dashboard — the shapes are in the tracked
`reachout/.env.example`, and re-issuing beats carrying secrets through cloud storage even
when the drive is private. If you would rather carry them, copy the two files into the
archive by hand; that is your call to make knowingly, not a step to automate.

## Phase 4 — do not work inside a Drive-synced folder

Worth stating plainly, because it is the failure mode this plan exists to avoid: if the
working clone lives inside Drive and you run `npm install`, Drive begins syncing 16,498
files, continuously, forever — and it will fight `node_modules` writes, `.git` locks and
the SQLite WAL file. Symptoms look like random build corruption.

**On the new machine:**

```bash
git clone https://github.com/Aarrushh/reachout.git ~/Desktop/reachout   # outside Drive
# then unpack the handoff tarball from Drive into place
```

Credentials: re-issue from each provider's dashboard where you can, rather than carrying
values across. Drive is private, so carrying them is acceptable — re-issuing is better.

## Phase 5 — verify before deleting the old machine's copy

```bash
./.venv/bin/python -m pytest reachout/tests demand/tests   # 694 collected
cd frontend && npm run build > /tmp/build.log 2>&1          # exit 0, never foreground
cd frontend && npm test
```

Plus the three services answering on 5173 / 8000 / 8001 — `README.md` has the recipe, and
`docs/MIGRATION_NEW_MACHINE.md` §4 lists the traps that have already cost time here.

Do not delete `~/Desktop/reachout` until that passes and the handoff tarball has been
opened successfully on the other side.
