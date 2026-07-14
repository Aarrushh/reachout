"""Submit the 52 backend tasks in docs/JULES_BACKEND.md to Jules, sequentially.

Each task becomes one Jules session. Sessions start from the integration
branch (jules-integration); when a session completes, its output branch is
merged into that branch via a dedicated git worktree (no gh CLI needed) and
pushed, so the next task builds on the previous one. After each task lands on
jules-integration, that branch is also merged into main and pushed, so main
always carries every completed task.

In-flight sessions are persisted in the state file ("pending"); if the runner
dies or times out, rerunning it reattaches to the existing session instead of
creating a duplicate.

Usage:
  python tools/jules_runner.py --dry-run     # parse tasks, print count, exit
  python tools/jules_runner.py --check       # verify API key + source + git
  python tools/jules_runner.py               # run all remaining tasks
  python tools/jules_runner.py --from 07     # resume from TASK 07
  python tools/jules_runner.py --only 14     # run a single task
  python tools/jules_runner.py --max 5       # stop after 5 tasks this run

Reads JULES_API_KEY from the environment or the repo-root .env file.
State (completed tasks, session ids) persists in tools/.jules_runner_state.json.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://jules.googleapis.com/v1alpha"
SOURCE = "sources/github/Aarrushh/reachout"
REPO = "Aarrushh/reachout"
BRANCH = "jules-integration"
TASKS_FILE = os.path.join(ROOT, "docs", "JULES_BACKEND.md")
STATE_FILE = os.path.join(ROOT, "tools", ".jules_runner_state.json")
WORKTREE = os.path.join(ROOT, "tools", ".jules-wt")
MAIN_WORKTREE = os.path.join(ROOT, "tools", ".jules-wt-main")

POLL_INTERVAL = 30          # seconds between session polls
SESSION_TIMEOUT = 3 * 60 * 60  # heavy tasks (SSE tests) can exceed an hour
QUOTA_WAIT = 30 * 60        # wait between retries when quota is exhausted

if sys.stdout.reconfigure:  # Windows console: task titles contain em-dashes
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def load_env():
    path = os.path.join(ROOT, ".env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


class ApiError(Exception):
    def __init__(self, code, detail):
        super().__init__(f"HTTP {code}: {detail[:500]}")
        self.code = code
        self.detail = detail


def api(method, path, body=None):
    req = urllib.request.Request(
        BASE + path, method=method,
        headers={"X-Goog-Api-Key": os.environ["JULES_API_KEY"],
                 "Content-Type": "application/json"},
        data=json.dumps(body).encode() if body is not None else None,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise ApiError(e.code, e.read().decode(errors="replace")) from e


def api_retry(method, path, body=None):
    """api() with backoff: quota errors wait QUOTA_WAIT, 5xx wait 60s."""
    while True:
        try:
            return api(method, path, body)
        except ApiError as e:
            if e.code == 429 or "RESOURCE_EXHAUSTED" in e.detail:
                log(f"quota exhausted ({e.code}); waiting {QUOTA_WAIT // 60} min…")
                time.sleep(QUOTA_WAIT)
            elif e.code >= 500:
                log(f"server error {e.code}; retrying in 60s…")
                time.sleep(60)
            else:
                raise


def git(*args, cwd=ROOT, check=True):
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{p.stderr}")
    return p.stdout.strip()


# ---------------------------------------------------------------- task parsing

def parse_tasks():
    text = open(TASKS_FILE, encoding="utf-8").read()
    m = re.search(r"\n```\n(.*?)\n```\n", text, re.S)
    if not m:
        raise SystemExit("master context block not found in " + TASKS_FILE)
    master = m.group(1)
    tasks = []
    for t in re.finditer(
        r"\*\*TASK (\d{2}) — (.*?)\*\*\n(.*?)(?=\n\*\*TASK \d{2} — |\n### |\n## |\Z)",
        text, re.S,
    ):
        tasks.append({"nn": t.group(1), "title": t.group(2).rstrip("."),
                      "body": t.group(3).strip()})
    return master, tasks


def build_prompt(master, task):
    return (
        master
        + f"\n\nYou are working on branch {BRANCH} of {REPO}. Base all work on "
        f"that branch and publish your result as a branch/PR off {BRANCH} "
        "(a runner merges it automatically before the next task).\n\n"
        + f"TASK {task['nn']} — {task['title']}\n{task['body']}\n\n"
        "Work ONLY this task — nothing from any other task. Before finishing, "
        "run the backend suite (cd reachout/tests && python -m pytest) and "
        "make it fully green."
    )


# ---------------------------------------------------------------- state

def load_state():
    if os.path.exists(STATE_FILE):
        state = json.load(open(STATE_FILE, encoding="utf-8"))
        state.setdefault("pending", {})
        return state
    return {"done": [], "sessions": {}, "pending": {}}


def save_state(state):
    json.dump(state, open(STATE_FILE, "w", encoding="utf-8"), indent=2)


# ---------------------------------------------------------------- git plumbing

def remote_heads():
    out = git("ls-remote", "--heads", "origin")
    return {line.split("refs/heads/")[1] for line in out.splitlines() if line}


def ensure_worktree():
    git("fetch", "origin")
    if BRANCH not in remote_heads():
        log(f"creating origin/{BRANCH} from origin/main")
        git("push", "origin", "origin/main:refs/heads/" + BRANCH)
        git("fetch", "origin")
    if not os.path.exists(WORKTREE):
        git("worktree", "add", "-B", BRANCH, WORKTREE, "origin/" + BRANCH)
    if not os.path.exists(MAIN_WORKTREE):
        git("worktree", "add", "-B", "main", MAIN_WORKTREE, "origin/main")


def find_output_branch(session, before):
    """Prefer branch names in the session resource; fall back to a ls-remote diff."""
    found = []

    def scan(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if "branch" in k.lower() and isinstance(v, str):
                    found.append(v)
                else:
                    scan(v)
        elif isinstance(node, list):
            for v in node:
                scan(v)

    scan(session)
    heads = remote_heads()
    for b in found:
        b = b.removeprefix("refs/heads/")
        if b in heads and b not in (BRANCH, "main"):
            return b
    new = heads - before - {BRANCH, "main"}
    if len(new) == 1:
        return new.pop()
    if len(new) > 1:
        raise RuntimeError(f"ambiguous new branches: {sorted(new)}")
    return None


def apply_changeset(session, nn, title):
    """Jules v1alpha returns completed work as a git patch in outputs[], not
    as a pushed branch: apply it to the integration branch ourselves."""
    patches = [o["changeSet"]["gitPatch"]
               for o in session.get("outputs", [])
               if "unidiffPatch" in o.get("changeSet", {}).get("gitPatch", {})]
    if not patches:
        return False
    gp = patches[-1]  # the final artifact is the finished state
    msg = gp.get("suggestedCommitMessage") or title
    git("fetch", "origin", cwd=WORKTREE)
    git("reset", "--hard", "origin/" + BRANCH, cwd=WORKTREE)
    git("clean", "-fd", cwd=WORKTREE)
    pfile = os.path.join(WORKTREE, ".jules_patch.diff")
    patch = gp["unidiffPatch"]
    with open(pfile, "w", encoding="utf-8", newline="\n") as f:
        f.write(patch if patch.endswith("\n") else patch + "\n")
    try:
        git("apply", "--3way", "--whitespace=nowarn", ".jules_patch.diff",
            cwd=WORKTREE)
    finally:
        os.remove(pfile)
    git("add", "-A", cwd=WORKTREE)
    git("commit", "-m",
        f"TASK {nn}: {msg}\n\n(applied from Jules {session['name']})",
        cwd=WORKTREE)
    git("push", "origin", BRANCH, cwd=WORKTREE)
    log(f"TASK {nn}: patch applied and pushed to {BRANCH}")
    return True


def merge_into_integration(branch, nn, title):
    git("fetch", "origin", cwd=WORKTREE)
    git("reset", "--hard", "origin/" + BRANCH, cwd=WORKTREE)
    p = subprocess.run(
        ["git", "merge", "--no-edit", "-m",
         f"merge TASK {nn}: {title} (jules branch {branch})", "origin/" + branch],
        cwd=WORKTREE, capture_output=True, text=True,
    )
    if p.returncode != 0:
        git("merge", "--abort", cwd=WORKTREE, check=False)
        raise RuntimeError(f"merge conflict on {branch}:\n{p.stdout}\n{p.stderr}")
    git("push", "origin", BRANCH, cwd=WORKTREE)
    log(f"merged {branch} -> {BRANCH} and pushed")


def merge_integration_into_main(nn, title):
    git("fetch", "origin", cwd=MAIN_WORKTREE)
    git("reset", "--hard", "origin/main", cwd=MAIN_WORKTREE)
    p = subprocess.run(
        ["git", "merge", "--no-edit", "-m",
         f"merge {BRANCH} into main after TASK {nn}: {title}",
         "origin/" + BRANCH],
        cwd=MAIN_WORKTREE, capture_output=True, text=True,
    )
    if p.returncode != 0:
        git("merge", "--abort", cwd=MAIN_WORKTREE, check=False)
        raise RuntimeError(
            f"merge conflict {BRANCH} -> main:\n{p.stdout}\n{p.stderr}")
    git("push", "origin", "main", cwd=MAIN_WORKTREE)
    log(f"merged {BRANCH} -> main and pushed (through TASK {nn})")


# ---------------------------------------------------------------- sessions

def create_session(master, task):
    nn, title = task["nn"], task["title"]
    body = {
        "prompt": build_prompt(master, task),
        "sourceContext": {"source": SOURCE,
                          "githubRepoContext": {"startingBranch": BRANCH}},
        "title": f"TASK {nn}: {title}",
        "requirePlanApproval": False,
    }
    session = api_retry("POST", "/sessions", body)
    name = session["name"]
    log(f"TASK {nn} session created: {name} — {title}")
    return name


def poll_session(name, nn, title, before):
    nudges = 0
    polls_since_nudge = 0
    deadline = time.time() + SESSION_TIMEOUT
    while time.time() < deadline:
        session = api_retry("GET", "/" + name)
        state = session.get("state", "?")
        if state == "COMPLETED":
            log(f"TASK {nn} completed")
            if not session.get("outputs"):
                # outputs can lag the state change by a little
                time.sleep(30)
                session = api_retry("GET", "/" + name)
            if apply_changeset(session, nn, title):
                return name
            branch = find_output_branch(session, before)
            if branch is None:
                # Jules may not have pushed yet; give it a moment and retry once.
                time.sleep(30)
                branch = find_output_branch(session, before)
            if branch is None:
                raise RuntimeError(
                    f"TASK {nn}: no output branch found — review {name} manually")
            merge_into_integration(branch, nn, title)
            return name
        if state == "FAILED":
            raise RuntimeError(f"TASK {nn} FAILED — inspect {name} activities")
        if state == "AWAITING_PLAN_APPROVAL":
            log(f"TASK {nn}: approving plan")
            api_retry("POST", f"/{name}:approvePlan", {})
        elif state == "AWAITING_USER_FEEDBACK":
            # Jules pauses here both to ask questions AND after announcing it
            # finished. Either way the standing answer is the same: proceed
            # within the spec and finalize. Repeat every ~5 min — one message
            # is sometimes ignored (observed on TASK 35).
            polls_since_nudge += 1
            if polls_since_nudge >= 10 or nudges == 0:
                polls_since_nudge = 0
                nudges += 1
                log(f"TASK {nn}: sending proceed/finalize message (#{nudges})")
                api_retry("POST", f"/{name}:sendMessage",
                          {"prompt": "Proceed with your best judgment strictly "
                                     "within the task spec — do not expand scope "
                                     "and do not wait for further feedback. If "
                                     "the work is done, finalize the session and "
                                     "submit your completed change set now."})
        else:
            log(f"TASK {nn}: {state}")
        time.sleep(POLL_INTERVAL)
    raise RuntimeError(f"TASK {nn} timed out after {SESSION_TIMEOUT}s — {name}")


# ---------------------------------------------------------------- entry

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--from", dest="from_nn")
    ap.add_argument("--only")
    ap.add_argument("--max", type=int, default=0)
    args = ap.parse_args()

    load_env()
    master, tasks = parse_tasks()
    log(f"parsed {len(tasks)} tasks from {os.path.relpath(TASKS_FILE, ROOT)}")

    if args.dry_run:
        for t in tasks:
            print(f"  TASK {t['nn']} — {t['title']}")
        return

    if "JULES_API_KEY" not in os.environ:
        raise SystemExit("JULES_API_KEY missing (set it in .env)")

    if args.check:
        sources = api("GET", "/sources").get("sources", [])
        names = [s.get("name") for s in sources]
        ok = SOURCE in names
        print(f"API key valid; {len(names)} source(s); {SOURCE} "
              + ("FOUND" if ok else f"NOT FOUND — available: {names}"))
        print("git remote:", git("remote", "get-url", "origin"))
        return

    state = load_state()
    todo = [t for t in tasks if t["nn"] not in state["done"]]
    if args.only:
        todo = [t for t in tasks if t["nn"] == args.only.zfill(2)]
    elif args.from_nn:
        todo = [t for t in todo if t["nn"] >= args.from_nn.zfill(2)]
    if args.max:
        todo = todo[: args.max]
    if not todo:
        log("nothing to do")
        return

    ensure_worktree()
    log(f"starting run: {len(todo)} task(s), first = TASK {todo[0]['nn']}")
    for task in todo:
        nn, title = task["nn"], task["title"]
        before = remote_heads()
        session_name = state["pending"].get(nn)
        if session_name:
            log(f"TASK {nn}: reattaching to existing session {session_name}")
        else:
            session_name = create_session(master, task)
            state["pending"][nn] = session_name
            save_state(state)
        poll_session(session_name, nn, title, before)
        merge_integration_into_main(nn, title)
        state["done"].append(nn)
        state["sessions"][nn] = session_name
        state["pending"].pop(nn, None)
        save_state(state)
        log(f"progress: {len(state['done'])}/{len(tasks)} tasks done")
    log("run finished")


if __name__ == "__main__":
    main()
