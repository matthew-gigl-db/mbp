# 2026-10-23 -- Branded HTML presentation

## Goal

A Databricks-branded, customer-facing HTML presentation (modeled on `genie-build-waves/docs/genie-build-waves-pitch.html`) that teaches SDLC on Databricks and makes the case for Declarative Automation Bundles as the opinionated way to build data products.

## Changes

* Added `docs/sdlc-best-practices-pitch.html` (single file, no build step). Sections: problem, lifecycle (dev -> ci -> tst -> uat -> prod), bundle anatomy and what `bundle deploy` does, deep dive (modes, presets, variables, references, identity, prevent_destroy, plans, generate/bind, templates/mutators), why bundles vs Terraform vs REST (measured numbers from `deployment-complexity-comparison.md`), objection handling, tagging for cost allocation, GitHub Actions with OIDC, Genie Code in the bundle editor, testing/rollback, adoption roadmap, checklist.
* Linked it from `README.md`.

## Decisions

* Reused the brand tokens, components, and Brandfolder asset URLs already used in the Genie Build Waves pitch; no new asset URLs.
* Animations (hero terminal, editor mock, comparison bars) are plain DOM with `prefers-reduced-motion` and print fallbacks.
* All numbers come from the comparison doc (260 / 251 + 10 per env / 259 lines; 0 / 12 resource types / 15 endpoints and 29 call sites).
* The editor mock shows the real `orders_refresh.job.yml` and is labeled illustrative.
* The billing query in the tagging section was run against `system.billing.usage` + `list_prices` to confirm it executes.

## Verification

* HTML parsed with balanced tags; all in-page anchors and relative links resolve; every Brandfolder URL already exists in the Genie Build Waves pitch.
* No internal identifiers or old product names.

## Files

* `docs/sdlc-best-practices-pitch.html` (new)
* `README.md`
* `docs/sessions/INDEX.md`
