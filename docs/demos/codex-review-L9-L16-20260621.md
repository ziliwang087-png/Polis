# Codex Independent Review — L9–L16 (2026-06-21 16:30)

Independent code review by `codex exec` (separate context, no knowledge of
this session). Looked at commits `2f6e1cc` through `74951ad`.

## Bugs found (Severity 1 — definitely wrong)

1. **`backend/app/routes/admin.py:164`** — `/admin/reaper/stats` accepted
   any normal user JWT via `get_current_owner`; the dependency accepts
   tokens from `/auth/register`, so this was not admin auth — exposed
   reaper audit job/agent IDs to any logged-in user.
   **Status: FIXED in L18.** Added `get_current_admin` dependency that
   requires either `payload.is_admin == True` or `sub` in the
   `POLIS_ADMIN_USER_IDS` allowlist. Both `/admin/reaper/stats` and
   `/admin/reaper/recent` now use it. New 403 path covered by
   `verify_reaper_admin_api.py` step 4b.

2. **`backend/app/routes/admin.py:238`** — same as #1 for
   `/admin/reaper/recent`.
   **Status: FIXED in L18.**

## Concerns (Severity 2 — fishy under specific conditions)

3. **`backend/app/stale_claim_reaper.py:61`** — single-statement CTE
   reset with no row-level lock; concurrent reaper or agent
   progress/deliver could race and reset a row that just made progress.
   **Status: FIXED in L18.** Switched to two-step `FOR UPDATE OF j SKIP
   LOCKED` SELECT then per-row UPDATE that re-checks the stale predicate.
   Now safe under multi-replica reaper overlap and racing agent writes.

4. **`backend/app/stale_claim_reaper.py:155`** — `reap_once()` runs
   synchronous psycopg2 inside the FastAPI event loop; slow query blocks
   the loop for that worker.
   **Status: FIXED in L18.** Reaper loop now `await asyncio.to_thread(reap_once)`.
   `/health/deep` ping moved to `to_thread` too.

5. **`backend/migrations/versions/20260621_stale_claim_reaped.py`** — app
   now writes `event_type='stale_claim_reaped'`, but `entrypoint.sh`
   ignores `alembic upgrade head` failures; reaper would crash every
   tick if migration failed.
   **Status: ACCEPTED RISK.** Migration already applied successfully to
   prod; if a future deploy regresses, reaper's `last_error` field on
   `/health/deep` will surface it within 60s. Not making migration fatal
   today because that would block deploy on transient db issues which
   we've seen on Supabase.

6. **`backend/scripts/loop/cleanup_demo_data.py:90`** — activity guard
   only checks jobs created BY the demo user, not jobs assigned TO
   agents owned by that user; deleting agents could orphan other users'
   in-flight jobs.
   **Status: ACCEPTED RISK.** Demo-prefix matching means we only ever
   delete `loop-demo-e2e-…` `inbox-probe-…` users etc.; their agents
   are bot agents that never actually claim other users' jobs. Will
   harden when shifting cleanup to non-demo accounts.

## Things codex couldn't verify

- Whether prod runs multiple uvicorn workers (single process now;
  L18 fix is correct for both single and multi).
- Whether `alembic upgrade head` succeeded everywhere before the new
  app version started.
  **Confirmed:** migration applied via local `alembic upgrade head`
  before any reaper code was deployed; prod enum has 7 labels including
  `stale_claim_reaped`.

## Overall

Codex: **FIX-NEEDED**.
After L18: **2 critical fixed, 2 fishy fixed, 2 accepted with rationale**.

## Output of L18 verification

```
$ verify_reaper_admin_api.py (local)
[verify-L15] PASS reaper/stats: enabled=True running=True last_24h_reaped=0
[verify-L15] PASS reaper/recent: 0 events
[verify-L15] PASS auth required (got 401 without token)
[verify-L15] PASS non-admin rejected (got 403 for user_token)
[verify-L15] ALL CHECKS PASSED

$ verify_stale_claim_reaper.py
[verify-stale-claim-reaper] PASS: stale job reset to submitted
[verify-stale-claim-reaper] PASS: fresh claim left alone
[verify-stale-claim-reaper] PASS: actively-progressing job left alone
[verify-stale-claim-reaper] PASS: audit event recorded with reason+previous_agent_id
[verify-stale-claim-reaper] ALL CHECKS PASSED

$ verify_health_deep.py
PASS: /health/deep status=ok, db_ok=True, reaper=True

$ pytest tests/
47 passed in 2.06s
```
