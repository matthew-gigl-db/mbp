# Research spike: agent handoff and owner notifications for external monitors

**Status:** research only, not scheduled for implementation
**Date:** 2026-11-15
**Scope:** How an external build monitor (`src/skills/genie-build-monitor/SKILL.md`), Genie Code, Genie One and the owner could exchange messages about a build, and how the owner gets a push notification when the monitor needs a decision. Related: `2026-11-03_devin-monitor-requirements.md`, `2026-11-03_omnigent-monitor-options.md`.

## Problem

In the first level 4 test the monitor escalated correctly (same failure after its own fix), but the escalation lived only in the agent's own session. The owner did not see it for about 11 hours, and the agent's session was later suspended for inactivity, so it would not have noticed a reply either. Monitor guardrail 10 now requires an `ESCALATION:` report sent to every channel the owner configures and a stop in the platform's needs-attention state. This spike lists the channels that could carry that report, and a reply, automatically.

Wanted:

1. A push notification to the owner (phone) when the monitor needs a decision.
2. A reply path that wakes the monitor.
3. Ideally, Genie (Genie Code or Genie One) can read and write the same thread.

## What each agent can do with GitHub Issues

| Agent | Read issues | Write issues | Notes |
|---|---|---|---|
| Genie Code, chat (Databricks GitHub connector) | Public repos; private repos only if the connector's GitHub app has access to them | Supported by the connector per docs ("writes are limited to file contents, issues, and pull requests"), after the admin setup for write and private access | Observed: the connector authenticated as the owner, read a public repo's PRs and issues, but could not resolve a private personal repo, and exposed only read tools (`issue_read`, `list_issues`, `search_issues`). The GitHub app used by Databricks Git folders (code and workflows permission only) is not the connector's app. [Connect Genie Code to MCP servers](https://docs.databricks.com/aws/en/genie-code/mcp), [Search GitHub code with Genie Code](https://docs.databricks.com/aws/en/genie-code/github-mcp) |
| Genie Code, custom GitHub MCP service | Yes | Yes, if the issue write tools are exposed | Unity Catalog HTTP connection to GitHub's MCP server with per-user OAuth (managed or own GitHub App), registered as an MCP service and added to Genie Code. Needs `CREATE CONNECTION` on a schema. Not verified inside build-job Genie Code tasks. |
| Genie Code tasks inside the build job | Unknown | Unknown | Not verified that job tasks see the owner's chat connectors. A notebook task with a token from a Databricks secret is the dependable alternative. |
| Genie One | Via its GitHub connector | Connector write tools exist; in Genie Agents, write tools pause for user approval | [Connect Genie One to external applications with MCP](https://docs.databricks.com/aws/en/genie-one/external-sources/), [Connect a Genie Agent to MCP tools and sources](https://docs.databricks.com/aws/en/genie-agents/external-tools/) |
| External monitor (coding agent) with a fine-grained token | Yes | Yes, with **Issues: Read and write** on the repo | If the token belongs to the owner, everything it creates is authored by the owner (see gotchas). |
| Omnigent | Yes | Yes, through its GitHub App (sandboxes get `git` and `gh` as the signed-in user with short-lived tokens); its GitHub Actions docs show an issue workflow with `issues: write` | [Connect GitHub · Omnigent](https://omnigent.ai/docs/deploy/github-connect), [Configure Omnigent in GitHub Actions · Omnigent](https://omnigent.ai/docs/programmatic/github-actions). Hosted on a Databricks Sandbox it also has the workspace CLI (see the Omnigent note). |

## Notification channels

| Channel | Trigger | Reaches the owner as | Setup | Notes |
|---|---|---|---|---|
| Build job failure notifications | The build run fails | Email (`email_notifications.on_failure`), or Slack / Teams / PagerDuty / webhook via a notification destination | Bundle setting; destinations need a workspace admin | Independent of the monitor being awake. Fires when the monitor starts deciding, not when it escalates. [Add notifications on a job](https://docs.databricks.com/aws/en/jobs/notifications/), [Manage notification destinations](https://docs.databricks.com/aws/en/admin/workspace-settings/notification-destinations/) |
| The agent's own notifications | The agent's session needs the user | Agent app: in-app, push, desktop, mobile | User setting in the agent | Only if the agent ends its turn in the needs-attention state (guardrail 10). |
| Agent synced to Slack or Teams | Session messages | Slack or Teams thread | The agent org's Slack or Teams integration | |
| GitHub issue that assigns or @mentions the owner | Issue created or comment posted | GitHub Mobile push (direct mentions, assignments, review requests, deployment approvals only) | Owner enables those push types in GitHub Mobile | New issues in a watched repo and workflow-run results do not push. [Configuring notifications - GitHub Docs](https://docs.github.com/en/subscriptions-and-notifications/get-started/configuring-notifications) |
| GitHub Actions workflow on `hi_genie/**` pushes | The monitor commits a message file | The workflow opens or comments on an issue as `github-actions[bot]` (built-in `GITHUB_TOKEN`, `issues: write`), assigned to and mentioning the owner, so it pushes | One workflow file; Actions minutes on private repos | No personal token needed. Works with the folder handoff below. |
| Polling job in Databricks | Scheduled job checks the remote head of the message folder (`git ls-remote`) | The task fails on a new message, so its failure email fires | One small job | A workaround: "failure" means "new mail". |
| Genie Code scheduled task | Every N minutes checks the folder or the agent's session | Depends on where scheduled-task results surface | Untested | |

Does not work:

* **File arrival triggers** watch Unity Catalog volumes and external locations, not workspace Git folders, and a Git folder only changes when something pulls.
* **Watching the repo** on GitHub notifies about issues, PRs and releases, not plain pushes.

## Candidate designs

### A. Agent connector only (works today)

Genie Code reads and messages the monitor's sessions through the agent's MCP connector. Chat only, no record in the repo, and someone has to look.

### B. Folder handoff (works today)

The `hi_genie/` + `hey_<agent>/` pattern: the monitor commits its report to `hi_genie/`, Genie Code (in the Git folder) or the owner replies in `hey_<agent>/`. Reviewed record in Git, existing access only. Conflicts with "one writer at a time" during a run, so keep it on its own branch or between runs. No notification by itself.

### C. Folder handoff + Actions issue + reply forwarder

1. The monitor hits a stop condition, commits `hi_genie/<run>_escalation.md`, posts the same report in its session.
2. Workflow `on: push` with `paths: ['hi_genie/**']` opens or updates one issue per run as `github-actions[bot]`, `--assignee <owner>`, body mentions `@<owner>`. GitHub Mobile pushes it.
3. The monitor checks the issue once after about 10 minutes, then ends its turn waiting (guardrail 10).
4. The owner replies in the issue from the phone.
5. Workflow `on: issue_comment` (author = owner) posts the reply into the monitor's session through the agent's API, which resumes a suspended session. Needs the agent's API key (for Devin, a service-user `cog_` key) as an Actions secret and the session id in the issue body.
6. The monitor re-reads run state and branch head, acts on the chosen option.

Alternative to step 5: an agent-side automation that reacts to GitHub events or an incoming webhook, if the agent supports it.

### D. Issue posting built into genie-build-waves

`build_verdict` (or the gate) opens or updates one issue per run with a fine-grained token from a Databricks secret (Issues: Read and write on one repo). Two optional bundle variables (repo, secret key); empty means off. Deterministic, agent-agnostic, and gives Genie Code sessions in the build something to read. Pairs with the job failure notification variables.

### E. Genie One as the responder

The reply workflow (C step 5) calls the Genie One MCP instead of the agent API: `https://<workspace-host>/ai-gateway/mcp-services/system.ai.genie_one_mcp?o=<workspace-id>` ([Genie One MCP server](https://docs.databricks.com/aws/en/agents/mcp-tools/genie-mcp/)). Genie One reads the run's status files in the workspace and directs the monitor through the agent's MCP connector. Gives Genie a real turn.

Requirements and unknowns:

* A service principal with OAuth M2M, the `ai-gateway` scope, `EXECUTE` on `system.ai.genie_one_mcp`, and access to the data or files it should read. The Beta endpoint `/api/2.0/mcp/genie` reaches end of life on 2026-11-30; use the Unity Gateway URL.
* Connectors are per-user OAuth, so the service principal has no agent sign-in. The agent's MCP would need to be a custom MCP service with a shared credential, and the service principal `EXECUTE` on it.
* Not verified: that the Genie One MCP endpoint gives the caller its connectors and workspace-file access, and that connector write tools run without an interactive approval when called headless. If approval blocks, use Genie One only to read and summarize, and keep the direct agent API call for the wake-up.
* Genie One answers data questions; it does not repair runs or push fixes. Its role here is reading and relaying.

### F. Genie Code responder job

The reply workflow calls the Jobs API to start a small job with a Genie Code task whose prompt carries the reply and run id. The session reads the status files, decides, comments back or commits. Runs as the job's `run_as`. Same service principal and network needs as E.

### G. Omnigent as the monitor

Omnigent's GitHub App and `gh` cover issues natively, and on a Databricks Sandbox it has the workspace CLI. See `2026-11-03_omnigent-monitor-options.md` (sandbox egress is not controlled in the current beta).

## Gotchas found

* **Self-authored mentions do not notify.** GitHub does not notify you about your own activity. A monitor that writes with the owner's personal token creates issues and mentions authored by the owner, so no push. Use a bot author (`github-actions[bot]`, a GitHub App, or a machine user).
* **Issue comments do not wake an idle agent.** Something must forward the reply (agent API, agent automation, or a manual message).
* **Agents suspend idle sessions**, so monitor polling is not guaranteed. The job failure notification is the backstop.
* **Workspace IP access lists vs GitHub-hosted runners.** Any workflow that calls Databricks (E, F) needs the runners admitted (wide, changing ranges) or a self-hosted runner with a fixed address.
* **Interactive approval for write tools** may block headless Genie One or Genie Agent calls.

## Tests before building

1. Genie Code GitHub connector: give its app access to the private repo and Issues: Read and write; check whether write tools appear.
2. GitHub Mobile: an issue opened by `github-actions[bot]` that assigns and mentions the owner produces a push.
3. Agent API: a message to a suspended session resumes it.
4. Genie One in the UI, as the owner: read a status file under `build_root` and message the monitor through its connector; note whether it asks for approval.
5. Genie One MCP as a service principal (from a notebook): same as 4 with a shared-credential agent MCP service.

## If picked up later

Start with the job failure notification variables (D's partner, smallest and agent-agnostic) and design C (Actions issue as bot plus reply forwarder). Add D for repos that standardize on Issues, and E or F only after tests 4-5 pass.
