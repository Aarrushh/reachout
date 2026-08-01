> **SUPERSEDED by docs/PLAN_V2_PROMPT.md (2026-08-01)** — tick-scheduler micro-plan; the work already shipped (see STATUS.md).

1. Modify `reachout/api/server.py` to add `lifespan` manager:
   - Import `asynccontextmanager` from `contextlib`.
   - Import `asyncio`.
   - Add a context manager `lifespan(app: FastAPI)` that checks `os.environ.get("REACHOUT_SIM") == "1"`.
   - If true, create an instance of `AsyncIOScheduler` (needs `from apscheduler.schedulers.asyncio import AsyncIOScheduler`).
   - Add a job `tick_once` to run on interval (every 2s, jitter 1s).
   - Start the scheduler, `yield`, then shut it down on exit.
   - Attach `lifespan` to `app = FastAPI(title="ReachOut API", lifespan=lifespan)`.

2. Add `tick_once` logic in `reachout/api/server.py`:
   - Define async func `tick_once()` which calls `await asyncio.to_thread(_sync_tick)`.
   - Define `_sync_tick()` that does:
     - `conn = db.connect(DB_PATH)`
     - try:
         - `event = scripts.inventory_simulator._tick(conn)`
         - `conn.commit()`
         - if `event`:
           - Look up `region_id` using `conn.execute("SELECT region_id FROM shops WHERE shop_id=?", (event["shop_id"],)).fetchone()[0]`
           - Call `reachout.api.event_bus.BUS.publish(reachout.api.event_bus.to_stock_event(event, region_id))`
     - finally:
         - `conn.close()`

3. Add Tests in `reachout/tests/test_api.py`:
   - Test 1: `test_scheduler_unset_by_default`: Verify without `REACHOUT_SIM=1`, `lifespan` doesn't start a scheduler.
   - Test 2: `test_tick_once_publishes_valid_event`: Call `_sync_tick()` directly on a seeded DB (using the `_client` fixture), verify it publishes a schema-valid event to the BUS. Check `BUS._subscribers` receives the event.

4. Run all backend tests to ensure fully green.
