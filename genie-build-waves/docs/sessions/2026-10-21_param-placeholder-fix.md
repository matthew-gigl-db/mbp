# Session: Parameter Placeholder Fix (`{{param}}` in Automation Prompts)

**Date:** 2026-10-21  
**Branch:** `mg-genie-build-waves-init`  
**Commit:** latest on branch (fix: use {{param}} placeholders in automation prompts)

## Problem

sGt build run `842455926421383` passed waves 0-1 but failed at wave 2 because `session_id` never reached the Genie Code agents. The agents improvised a file-based claim mechanism (`claim_01`, `claim_06`, etc.) to self-assign sessions — a clear signal they couldn't see their assigned `session_id`. Wave 2 had a collision: two agents both claimed session 08, nobody ran session 07.

Waves 0-1 passed by luck (2 iterations → 2 sessions, 3 iterations → 3 sessions — each agent happened to pick a different one).

## Root Cause

Two requirements for `genie_task` parameters to reach the agent:

1. **`genie_task.parameters`** (not `context`) — the Jobs API resolves `{{input.*}}` and `{{job.*}}` templates in this field. Fixed in an earlier commit (`7225bb7`).

2. **`{{param_name}}` placeholders in the automation's `user_prompt`** — the Genie Code runtime substitutes these from the resolved parameters. **This was missing.**

### The bug

Our `thin_prompt` function generated:
```
Parameters:
- session_id
- wave
- run_id
```

The trading-app's `thin_prompt` (the proven reference) generated:
```
Parameters:
- session_id: {{session_id}}
- wave: {{wave}}
- run_id: {{run_id}}
```

The difference: `f"- {p}"` vs `f"- {p}: {{{{{p}}}}}"`. Without the `{{}}` placeholders, the Genie Code runtime had nothing to substitute — the prompt listed parameter names but never included the values.

The same issue affected the smoke prompt: we used `session_id=<session_id value>` (angle-bracket pseudo-templates) instead of `session_id={{session_id}}` (actual runtime placeholders).

## Fix

One-line change in `thin_prompt`:
```python
# Before (broken):
param_lines = "\n".join(f"- {p}" for p in params)

# After (fixed):
param_lines = "\n".join(f"- {p}: {{{{{p}}}}}" for p in params)
```

Smoke prompt updated to use `{{session_id}}` and `{{nonce}}`.

## Verification

Created a toy test: real `genie_task` inside a `for_each` with inputs `{"session_id": "ALPHA", "nonce": "b72b0ed1"}` and `{"session_id": "BRAVO", "nonce": "b72b0ed1"}`. The automation prompt contained `{{session_id}}` and `{{nonce}}` placeholders. Both iterations completed SUCCESS in ~51s. The nonce (`b72b0ed1`) is unguessable — if the agent echoes it correctly, parameter resolution works.

## Nonce-Based Smoke Test

Also improved the smoke test to be a proper parameter-resolution check:

- Setup generates a random 8-char hex nonce at patch time
- Nonce is injected into each `for_each` input item
- Passed as `"nonce": "{{input.nonce}}"` in `genie_task.parameters`
- Smoke prompt uses `{{nonce}}` placeholder
- If the agent echoes the correct nonce, `{{input.*}}` → `parameters` → `{{param}}` chain is proven

Previously the smoke test was unreliable: both iterations echoed the smoke job's ID as `session_id` (guessed from context) because the prompt had no `{{}}` placeholders.

## How `genie_task` Parameters Work (Reference)

```
for_each input: {"session_id": "07", "nonce": "abc123"}
       │
       ▼  Jobs API resolves {{input.*}} templates
genie_task.parameters: {"session_id": "07", "nonce": "abc123"}
       │
       ▼  Genie Code runtime substitutes {{param}} in user_prompt
automation prompt: "...session_id: 07...nonce: abc123..."
       │
       ▼  Agent sees actual values
```

Both steps are required. Field name alone (`parameters` vs `context`) is necessary but not sufficient.

## Files Modified

- `src/notebooks/setup_build_waves_job.ipynb` — `thin_prompt` and `SMOKE_PROMPT` use `{{param}}` placeholders
- `resources/build_waves_smoke.job.yml` — nonce field, updated comments

## Recovery for sGt Build

The sGt session needs to:
1. Pull, redeploy with `--var` flags, re-run setup (updates automation prompts)
2. Repair run `842455926421383`: select `w2_sessions`, `w2_integrate`, `w2_gate`, `w2_gate_check`
3. Sessions 06/08 will re-validate (work already committed). Session 07 will receive its `session_id` this time.
