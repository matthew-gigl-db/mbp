# Gate Accuracy Improvements (Batch A)

**Date:** 2026-10-23

## Problem

Feedback from a consumer Genie Code session (semanticGroundTruth build) identified three gate accuracy issues that caused at least 2 of 5 wave-2 repairs:

1. **Redeploy log lines counted as errors by default.** DEFAULT_ERROR_PATTERNS included ELIFECYCLE, and there were no default ignore_patterns. Every app redeploy logs ELIFECYCLE Command failed and SIGTERM timeout from the old deployment. The gate's SQL query catches same-service lines after the new deployment's create_time (to handle runtime logs without the deployment_id attribute), so the old deployment's shutdown lines fell in the window and failed the gate.

2. **Gate didn't say why a line counted as an error.** Error samples were formatted as `{time} [{src}] {body}` with no match reason. The SIGTERM line matched because severity_text was ERROR, not because of any error_patterns entry, so removing patterns didn't help. Without the match reason, diagnosis was a guessing game.

3. **AppKit JSON error logs not caught.** Logs like JSON level error matched no default pattern, so 500s never failed a wave.

## Root Cause

1. ELIFECYCLE is a npm lifecycle signal, not an error indicator — it fires on both crash and graceful shutdown. The gate's SQL query OR condition (deployment_id match OR same-service after create_time) deliberately catches runtime logs without the deployment_id attribute, but this also catches old deployment shutdown lines. Changing the query would risk missing real runtime errors.
2. check_app_logs built error samples without tagging the match source (severity vs pattern).
3. DEFAULT_ERROR_PATTERNS had no pattern for JSON-formatted log levels.

## Changes

### src/notebooks/wave_gate_check.ipynb (cell 5)

* Removed ELIFECYCLE from DEFAULT_ERROR_PATTERNS.
* Added UnhandledPromiseRejection to DEFAULT_ERROR_PATTERNS (was missing).
* Added a JSON level error pattern for AppKit logs (matches level error or fatal in JSON).
* Added DEFAULT_IGNORE_PATTERNS with SIGTERM timeout and ELIFECYCLE bracket patterns — old-deployment shutdown noise.
* Changed check_app_logs to use DEFAULT_IGNORE_PATTERNS when ignore_patterns is not set (was empty list).
* Changed error sample format to tag each error with how it matched: [severity] or [pattern:regex].
* Changed the max_errors problem message to suggest ignore_patterns when severity-matched errors are present.

### src/skills/genie-build-session-runner/SKILL.md

* Updated the error_patterns reference in the converge diagnosis section to list the new defaults (without ELIFECYCLE, with JSON level pattern and UnhandledPromiseRejection).
* Updated to mention default ignore_patterns.

### docs/manifest-schema.md

* Updated error_patterns default list: removed ELIFECYCLE, added UnhandledPromiseRejection and JSON level pattern.
* Updated ignore_patterns description to document the new defaults and explain they are old-deployment shutdown noise.

### examples/converge-waves.json

* Removed explicit error_patterns override (uses new defaults which include the JSON level pattern).
* Updated ignore_patterns to include the new default ignore patterns alongside the existing project-specific ones.

## Decisions

* ELIFECYCLE dropped entirely from defaults rather than scoped to BUILD logs — simpler, and ELIFECYCLE is a process lifecycle signal, not an error.
* DEFAULT_IGNORE_PATTERNS ships with the two most common redeploy noise lines. Projects can still override ignore_patterns (which replaces defaults).
* Error samples now include [severity] or [pattern:regex] tag, making it obvious whether to adjust error_patterns or ignore_patterns.
* Removed error_patterns from the converge example rather than fighting JSON escaping for the nested quotes in the regex — the example now uses the framework defaults.

## Files Modified

* src/notebooks/wave_gate_check.ipynb — DEFAULT_ERROR_PATTERNS, DEFAULT_IGNORE_PATTERNS, check_app_logs error tagging
* src/skills/genie-build-session-runner/SKILL.md — error_patterns and ignore_patterns reference
* docs/manifest-schema.md — error_patterns and ignore_patterns defaults
* examples/converge-waves.json — removed error_patterns override, updated ignore_patterns