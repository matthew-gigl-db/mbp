# 2026-10-22 — Pitch Document Polish

**Branch:** `mg-genie-build-waves-init`
**File:** `docs/genie-build-waves-pitch.html`

## Summary

Visual polish pass on the customer-facing HTML pitch document. Rebuilt the animated hero Genie Code session to tell the correct orchestration story (Genie Code → Lakeflow Job → Genie Code), replaced the job run view with an animated Gantt-style timeline modeled on the real Lakeflow Jobs run timeline, fixed dark-mode product logos, corrected nested bullet numbering in Best Practices, and made the deploy steps actionable with real CLI commands.

## Problems & Root Causes

| Problem | Root Cause |
|---|---|
| Hero animation looked like an MCP/tool-call app, not an orchestrator that hands off to a Lakeflow Job | Original script showed Genie Code calling tools directly for waves/sessions instead of deploying a job and monitoring it |
| Job run view (columnar task cards) didn't convey timeline or parallelism | Static per-wave columns with task cards; no sense of time progression or bar fills |
| Product logo names (Lakeflow Jobs, Unity Catalog) invisible in dark mode on "Why Genie Code" cards | Cards used full-color lockups with navy wordmarks on a Navy 700 dark-mode surface |
| Best Practices items 4–8 rendered as numbered circles instead of sub-bullets | `.bp-list li` selector matched nested `<ul>` items, inflating the CSS counter for all subsequent items |
| Deploy step 4 said "Start the build from the Jobs UI (or CLI)" with no command | Missing `bundle run build_waves` command and gate result paths |
| Deploy step 5 said "repair run only the failed wave's tasks" with no command | Missing `jobs repair-run` with `rerun_dependent_tasks`; inaccurate claim about "skipped" waves |
| Smoke test flag `-p run_smoke=true` never set the parameter | `-p` is the global `--profile` flag; correct flag is `--params` |

## Changes

### Hero Animation Restructure (`efc0ae2`, `eedc294`)

- **Three-act narrative:** (1) Genie Code validates manifest, deploys bundle, generates task graph, triggers job; (2) Lakeflow Jobs run timeline plays with bars filling left-to-right; (3) Genie Code polls the completed job, reads gate files, and shows a summary card.
- **"View run 884213 ↗" link** transitions from the Genie Code chat to the job panel with a press animation.
- **Handoff message** explains the job is running on serverless compute and Genie Code will poll when it finishes.

### Animated Run Timeline (`efc0ae2`)

Replaced the per-wave columnar task cards with a Gantt-style timeline:

- **Rows:** `wN_sessions` (with ↻ badge showing iteration count), `wN_integrate`, `wN_gate`, `wN_gate_check` — matching real generated task names.
- **Bars** are positioned by simulated start time and duration. Each bar fills left-to-right while running (Lava + glow), turns green on success, then shows its duration label.
- **Wave 1 `for_each`** is expanded: Iteration 1–3 fill concurrently with circle checkmarks that turn green.
- **Wave 2 converge** shows attempt counting (1/5 → 3/5) and "soak window…" on the runtime gate.
- **Visual details:** time axis ticks, 25% vertical gridlines, alternating row bands, blue task names.
- **Timing:** ~11s animation; `realMs()` compresses simulated seconds with a 260ms floor so short tasks stay visible.
- **Numbers consistent:** 12 tasks, 25m 22s total, matching the poll result, summary card, and setup tool output.

### Dark-Mode Product Logos (`b20fa0d`)

- Wrapped each of the 4 product logos in `<picture>` with `<source media="(prefers-color-scheme: dark)">` pointing to the white lockup variant.
- Light mode unchanged (full-color lockups).

### Best Practices Nested Bullets (`9f21771`)

- Scoped numbered-circle styles to `.bp-list > li` (direct children only).
- Added `.bp-list ul` styles: `list-style: disc`, Lava-colored markers, 4px vertical padding.
- Counter now counts 1–8 correctly; "Curate your designs" sub-items render as plain bullets.

### Deploy Steps 4–5 and Smoke Flag (`8fc83dc`)

- **Step 4:** Real `bundle run build_waves` command, branch param note, per-wave task chain explanation, gate result file paths.
- **Step 5:** Explains Excluded cascade, passing sessions already committed, full `jobs repair-run` command with `rerun_dependent_tasks: true`.
- **Step 3 bug fix:** `-p run_smoke=true` → `--params run_smoke=true` in both the pitch HTML and `README.md`.

### README Accuracy Pass (`9a44b64`)

Checked every README claim against `databricks.yml`, the job YAMLs, the setup and gate notebooks, the skills and `manifest-schema.md`.

- **Skill changes and deploys.** Setup publishes skills from `${workspace.file_path}/src/skills`. On `dev` (source-linked deployment) that resolves to the repo itself, so a `SKILL.md` edit needs only the setup job; on other targets it is the deployed copy, so `bundle deploy` first. Manifest changes need only the setup job (it reads `manifest_path` directly). Fixed in README "Changing a build" and the pitch's Skills card. (First pass wrongly said a deploy was always needed; corrected after `bundle validate -o json` showed the source-linked `skills_dir` on dev.)
- `converge` added to the session-mode lists.
- The setup job is run after every deploy; deploy does not trigger it.
- Architecture table: Build Planner skill row added; setup notebook row covers retries, timeouts and smoke job reset.
- Runtime gate description covers jobs and pipelines, not only apps.
- `project_name` listed as optional; step 5 shows `bundle run build_waves` and the per-wave task chain.
- "Repair re-runs only failed tasks" corrected to re-run from the failed wave with dependents.

## Commits

| Commit | Description |
|---|---|
| `7df5ade` | feat: add Lava glow on hover to hero CTA buttons |
| `7836ab9` | feat: add Lava text-shadow glow to ghost button on hover |
| `12459a3` | feat: add Lava glow on hover to hero product strip logos |
| `cf23dcb` | feat: replace static hero wave diagram with animated Genie Code session |
| `eedc294` | feat: hero animation now shows Genie Code → Lakeflow Job → Genie Code |
| `efc0ae2` | feat: Lakeflow Job run view becomes an animated run timeline |
| `b20fa0d` | fix: use white product lockups in dark mode for Why Genie Code cards |
| `9f21771` | fix: nested bullets in Best Practices no longer get numbered circles |
| `8fc83dc` | docs: make deploy steps 4-5 actionable; fix smoke-test flag |
| `e30eafb` | docs: app scaffolding command is `databricks apps init`, not `apps create` (Best Practice #2) |
| `9a44b64` | docs: README accuracy pass against bundle source |
| (next) | chore: default `project_name` "Genie Build Waves"; setup header lists 4 automations; source-linked skill-change wording |

## Files Modified

- `docs/genie-build-waves-pitch.html` — all changes above
- `README.md` — smoke-test flag fix (`-p` → `--params`)

## Decisions

- **Timeline over columns.** The Gantt-style timeline better conveys parallelism and time progression than the original per-wave column layout. Modeled on the real Lakeflow Jobs run timeline screenshot.
- **`<picture>` for dark-mode logos.** Uses the browser's native `prefers-color-scheme` media query rather than JS toggling, matching the rest of the document's dark/light approach.
- **Direct-child selectors.** `.bp-list > li` scoping is the minimal fix that doesn't require restructuring the HTML or adding extra classes to nested items.
- **Real CLI commands in deploy steps.** Steps 4–5 now show copy-pasteable commands rather than prose descriptions, consistent with steps 1–3.
