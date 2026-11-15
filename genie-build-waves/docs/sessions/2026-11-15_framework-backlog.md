# 2026-11-15: Framework backlog from the Agentic Trading build 4 request

## Problem

A request doc from Agentic Trading build 4 (2026-10-31, runs `800187417582767` and `396653921760382`, sessions 50-71; consumer source `agenticTrading/docs/requests/R16_build_waves_lessons.md`) sat unmerged on branch `mg-genie-build-waves-agentic-b4-lessons` (commit `d59c71b`). It named the project, run ids and session numbers, which mbp allows only in session summaries. The owner asked whether its findings were already in `main`, then to rewrite it as a generic backlog doc before starting a new project at monitor level 4.

## Findings (checked against `main` at `0b14e4a`)

* Open: 1 freshness from run start (gate still uses `run_start`), 2 waivers, 4 dashboard objects, 5 request schema (runner `{path, change, why}` vs integrator `{from, path, change}`), 8 redaction placeholder.
* Partly: 3 owner steps (planner tip covers destroy and deletes only), 6 statuses (non-final values count as incomplete and get a continuation pass; no explicit list in the runner skill), 9 tooling (`capability_probe` does not check the CLI version).
* Done (documented): 7 blocked/failed sessions end SUCCESS (README "Why not repair?", design note `2026-11-15_failing-session-iterations-design.md`).

## Changes

* New `docs/plans/2026-11-15_framework-backlog.md`: the nine items, generic, with state on `main`, a proposed adopt / defer / drop, and whether to address each before a new level 4 project.
* The old branch can be deleted once this merges.

## Files

`docs/plans/2026-11-15_framework-backlog.md` (new), `docs/sessions/2026-11-15_framework-backlog.md`, `docs/sessions/INDEX.md`.
