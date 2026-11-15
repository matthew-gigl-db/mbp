# 2026-11-15: Research spike, agent handoff and owner notifications

## Problem

In the first level 4 external-monitor test, the monitor's escalation went unseen for about 11 hours and its session was later suspended. The owner asked which channels could notify them and let agents (the monitor, Genie Code, Genie One) talk to each other, for example through GitHub Issues, and asked for a write-up only, no build-out.

## Findings (details in `docs/plans/2026-11-15_agent-handoff-notifications-spike.md`)

* Genie Code's GitHub connector: authenticated as the owner, read a public repo's PRs and issues, could not resolve a private personal repo, exposed read tools only. The GitHub app used for Git folders (code and workflows permission) is not the connector's app. Docs say the connector can write issues after the admin setup for write and private access.
* GitHub Mobile pushes only direct mentions, assignments, review requests and deployment approvals. Content authored with the owner's own token does not notify the owner; a bot author (`github-actions[bot]`) does.
* An issue comment does not wake a suspended agent session; a forwarder (agent API or automation) is needed.
* Genie One MCP (`system.ai.genie_one_mcp` via Unity Gateway; Beta endpoint ends 2026-11-30) could act as a responder, but per-user connector OAuth, possible interactive approval of write tools, and workspace IP access lists vs GitHub-hosted runners are open.
* No workspace-native file trigger fires on Git folder changes.

## Decision

Research only. If picked up: job failure notification variables first, then the Actions-issue-as-bot design with a reply forwarder.

## Files

`docs/plans/2026-11-15_agent-handoff-notifications-spike.md` (new), `docs/plans/2026-11-03_devin-monitor-requirements.md` (open question link), `docs/sessions/INDEX.md`.
