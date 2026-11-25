# Monitor: owner fixes outside Git, goal over mechanism

Date: 2026-11-25 | Branch: `mg-genie-build-waves-monitor-owner-fixes` | File: `src/skills/genie-build-monitor/SKILL.md`

## Problem
In a level 4 build, a session ended `blocked` because a gitignored `variable-overrides.json` named a schema that did not exist. The owner fixed the file (outside Git) and told the monitor to repair from `w<w>_sessions`. The skill already says a repair keeps a session's SUCCESS iteration, so that repair would not rerun the session. The monitor correctly refused to act and asked again, which cost an extra round trip with the owner. Two gaps caused it:

1. The decision table had a row for the monitor's own fix in a failed session's files (fresh run), but none for **the owner's fix outside Git** (gitignored file, workspace setting, grant), so the monitor had to escalate even though the right action was clear.
2. Guardrail 10 says "act only on the option they chose", with no rule for an owner answer whose **mechanism contradicts the skill** while its goal is clear.

## Changes
* **Guardrail 10, new "Goal over mechanism" bullet.** At level 4, when the owner's answer names a mechanism the skill says will not achieve the owner's stated goal, the monitor takes the action that does, if it stays within the same guardrails, `max_repairs` budget, waves and scope, and reports what it did instead and why. Below level 4, or when the alternative needs more permission, more repairs, other waves, another stop condition or an excluded action, it reports the conflict and waits.
* **Section 4, new row.** After an escalation, when the owner (or an agent acting for the owner) reports a fix outside Git for the failed session's cause and names what changed: level 4 re-reads the run state and branch head, checks the change addresses the quoted cause, and starts one fresh run from `w<w>_sync` without asking. A status-file-only fix (no session needs to rerun) is repaired from `w<w>_integrate`. Levels 1-3 report that a fresh run is needed.
* **Section 5.** The repair note now names the fresh run as the way to rerun a `blocked` / `fail` session (level 4), instead of "needs a person".
* **Section 8 step 4.** The owner-reported fix is a third trigger for a fresh run; the "did the session run again" check covers owner fixes too.

## Decisions
* Fresh runs still count against `max_repairs`, and every stop condition still applies; the monitor still never writes workspace files (the owner makes the fix).
* Not changed here: making a `blocked` / `fail` session's iteration end FAILED so a plain repair reruns it (see the 2026-11-15 design note); that removes the repair-vs-fresh-run distinction at the framework level and is tracked separately.

## Files modified
* `src/skills/genie-build-monitor/SKILL.md`
* this summary, `docs/sessions/INDEX.md`

Monitors that read the skill from the repository see the change once it is merged (no redeploy). The Unity Catalog copy of the monitor skill updates on the next setup run of each instance.
