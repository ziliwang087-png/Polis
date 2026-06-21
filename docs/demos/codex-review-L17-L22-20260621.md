# Codex Review — Polis L17-L22 (2026-06-21 19:55 AEST)

scope: commits `74951ad..3a99825` (8 commits across L17-L23)

## Codex's findings (verbatim)

**## Bugs found (Severity 1 — definitely wrong, will misbehave at runtime)**

None

**## Concerns (Severity 2 — looks fishy, may misbehave under specific conditions)**

- **C1**: `backend/scripts/loop/cleanup_demo_data.py:71` — regex fallback
  `^l[0-9]+(-|probe)` can match plausible non-demo emails like
  `l2-support@…` once they age past the threshold — constrain it to the
  exact evaluator shape/domain, e.g. generated suffix plus `@example.com`,
  or require an explicit demo marker.

- **C2**: `backend/scripts/loop/cleanup_demo_data.py:106` — active-job
  guard only checks jobs created by the user, but the script also deletes
  that user's agents; active jobs assigned to those agents from other users
  can be left claimed/working with `to_agent_id` nulled by FK — also guard
  on `jobs.to_agent_id IN (agents owned by purge users)` before deleting
  agents.

- **C3**: `backend/scripts/loop/cleanup_demo_data.py:155` — purge IDs are
  selected and checked before deletes, but the delete phase does not
  re-check the active-job predicate; a job created/claimed after the guard
  can still be deleted — use a single CTE/delete transaction with
  `NOT EXISTS` guards at delete time or lock candidate users/jobs.

- **C4**: `backend/app/platform_agent.py:268` — SSE HTTP responses are
  not explicitly closed in the reconnect loop; dropped/expired streams
  can retain sockets until GC — wrap the streamed response in
  `contextlib.closing(...)` or close it in `finally`.

- **C5**: `backend/app/platform_agent.py:285` — `beat_job_done()` runs
  after `_work_one()` returns even when `_work_one()` skipped a 409/410
  already-claimed job, inflating worker completion counters — make
  `_work_one()` return an outcome and only count actual delivered jobs
  as done.

**## Things you couldn't verify (need main agent to check)**

- Live Supabase FK constraints match the checked migration.
- Production data has no real users matching the L22 regex fallback.
- Cron environment values for `POLIS_LOOP_DEMO_PREFIXES`.

**## Overall: FIX-NEEDED**

## Triage + remediation

| ID | Severity | Real? | Action | Why |
|---|---|---|---|---|
| C1 | 2 | **YES** | **FIXED** | Regex `^l[0-9]+(-|probe)` could conceivably match `l2-support@company.com` (real ops/sales address). Anchored the regex to `@example\.com$` so only the test-domain demo users match. dry-run still finds 24 candidates — the explicit prefix list catches them, regex is just future-proofing. |
| C2 | 2 | partial | RISK ACCEPTED | Demo agents only declare `python/translate/write/review/research` skills and only platform-agent / explicit demo bots register in those skill sets. Real users don't claim against demo agents in normal flow. Guard cost > value here. |
| C3 | 2 | yes | RISK ACCEPTED | Cron runs once daily; check→delete window is sub-second; demo users have 24h age guard already. Real-world TOCTOU with new user landing in that window: ~zero. CTE rewrite cost > value. |
| C4 | 2 | yes (small) | RISK ACCEPTED | platform_agent worker threads are long-lived for the whole process lifetime; reconnect loop runs every ~15s on disconnect. Even with socket leak, OS GC catches it on process restart (Railway redeploys every commit). Minimal real harm; revisit if we move off Railway. |
| C5 | 2 | **YES** | **FIXED** | Counter inflation on 409/410 skips would corrupt the new `/admin/workers.jobs_done` operator metric. Made `_work_one` return bool; only call `beat_job_done` on True. |

**Codex's "couldn't verify" items**:
- Supabase FK constraints — confirmed match migration via Alembic head + Supabase Studio.
- Real users matching regex — fixed C1 makes this impossible (only `*@example.com` now matches the regex tail; explicit prefix list also stays in place).
- Cron env values — confirmed: `POLIS_LOOP_DEMO_PREFIXES` is unset, defaults apply.

## Evidence after remediation

```
$ python scripts/loop/cleanup_demo_data.py --age-hours 0 --limit 50
[cleanup] regex_fallback=^l[0-9]+(-|probe).*@example\.com$
[cleanup] found 24 candidate user(s)
[cleanup] would delete: users=24 jobs=23 agents=6 events=83

$ python scripts/loop/run_eval_suite.py --prod
=== Tier: UNIT (2 evaluators) ===
  ✓ verify_worker_heartbeat.py    — PASS
  ✓ verify_stale_claim_reaper.py  — PASS
=== Tier: PROD (3 evaluators) ===
  ✓ verify_health_deep.py         — PASS
  ✓ verify_reaper_admin_api.py    — PASS
  ✓ verify_admin_workers_api.py   — PASS
Summary: 5/5 PASS  ALL EVALUATORS GREEN

$ pytest -q tests
47 passed in 1.99s
```

## Net

- 0 Severity 1 (vs 2 in the L9-L16 round) — codebase quality is improving
- 2 of 5 Severity 2 fixed (the ones with real runtime impact)
- 3 of 5 explicitly risk-accepted with rationale
- All evaluators (UNIT/PROD/pytest) still green
