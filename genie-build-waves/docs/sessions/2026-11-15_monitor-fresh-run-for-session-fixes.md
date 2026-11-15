# 2026-11-15: Monitor fresh run for session-owned fixes (B1), secret scope note (B2), design note

## Problem

The test project's request file reported two mbp gaps after build 1:

* **B1:** at level 4 the monitor fixed a file the failed session owns, pushed, and repaired from `w<w>_sync`. The sync pulled the fix, but `w<w>_sessions` kept the session's SUCCESS iteration (a Genie Code iteration ends SUCCESS even when its status is `fail`), so nothing redeployed and the gate failed again. The monitor then hit "same failure after fix" and escalated. A fresh run with `only` from that wave passed.
* **B2:** the requirements doc said to scope the OAuth secret to `jobs` and `workspace` only, but reading the UC skill needs `files` in the secret, not only in the CLI profile.

## Changes

* `src/skills/genie-build-monitor/SKILL.md`: level 4 decision row for session-owned fixes now starts one fresh run from that wave instead of a repair; section 6 step 4 explains why; section 8 step 3-4: fresh run when the fix is in the failed session's files or a repair is refused (`only` = failed wave from `w<w>_sync`, later waves, `build_verdict`; counts against `max_repairs`), and a repeat only counts as "same failure after fix" if the session actually ran again after the push.
* `docs/plans/2026-11-03_devin-monitor-requirements.md`: secret scopes `jobs`, `workspace`, plus optional `files` (must be in the secret); level 4 row mentions the fresh run; open question links the design note.
* `docs/prompts/repair-failed-wave.md`: External monitor section matches.
* New `docs/plans/2026-11-15_failing-session-iterations-design.md`: Option A (per-session child job with a status check that fails on `fail`/`error`, so plain repairs re-run failed sessions) and Option B (continuation pass retries failed sessions after a pulled fix), with constraints, changes and checks. Not scheduled.
* `docs/plans/2026-11-15_agent-handoff-notifications-spike.md`: Genie Code job tasks inherit the owner's Genie Code settings and custom MCP connections (docs).

## Decisions (owner)

* B1 option 1 (skill change) now; option 2 written up only.
* All on the spike branch `mg-genie-build-waves-agent-handoff-spike`, merged to main together.

## Verification

* Tests and skill frontmatter test pass; no internal identifiers in added lines.
* Not yet exercised in a build: the next level 4 run with a session-owned fix should go straight to a fresh run.

## Files

`src/skills/genie-build-monitor/SKILL.md`, `docs/plans/2026-11-03_devin-monitor-requirements.md`, `docs/prompts/repair-failed-wave.md`, `docs/plans/2026-11-15_failing-session-iterations-design.md` (new), `docs/plans/2026-11-15_agent-handoff-notifications-spike.md`, `docs/sessions/INDEX.md`.
