#!/usr/bin/env python3
"""
deploy_orders_rest.py -- the orders_bundle deployment, rebuilt by hand on the REST API.

ILLUSTRATIVE ONLY. DO NOT USE IN PRODUCTION.

This script exists to make one point concrete: everything `databricks bundle deploy`
does for the YAML in ../../orders_bundle (databricks.yml + resources/, five targets)
has to be written, tested, and maintained by you when you go straight to the REST API.
This version covers four environments, no per-PR environments, and is still
incomplete -- see KNOWN GAPS at the bottom of the file.

Usage (example):
    DATABRICKS_HOST=https://<workspace-host> \
    DATABRICKS_CLIENT_ID=<sp-application-id> DATABRICKS_CLIENT_SECRET=<secret> \
    python deploy_orders_rest.py --env tst --bundle-root ../../orders_bundle \
        --run-as <sp-application-id>
"""

from __future__ import annotations

import argparse
import base64
import glob
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# 1. Environment model. In a bundle this is the `targets` block.
# ---------------------------------------------------------------------------
ENVIRONMENTS = {
    "dev": {"catalog": "retail_dev", "paused": True, "development": True, "shared": False},
    "tst": {"catalog": "retail_tst", "paused": True, "development": False, "shared": True},
    "uat": {"catalog": "retail_uat", "paused": True, "development": False, "shared": True},
    "prod": {"catalog": "retail", "paused": False, "development": False, "shared": True},
}
SCHEMA = "orders"
GROUPS = {"engineers": "data-engineers", "consumers": "data-consumers", "operators": "platform-operators"}
TAGS = {"project": "orders-medallion", "businessUnit": "Retail Analytics", "costCenter": "CC-0000",
        "owner": "data-engineering"}
PROTECTED_ENVS = {"prod"}  # bundle equivalent: lifecycle.prevent_destroy


# ---------------------------------------------------------------------------
# 2. Authentication + a client with retries. The CLI does this for you (and
#    supports GitHub OIDC federation natively via DATABRICKS_AUTH_TYPE=github-oidc).
# ---------------------------------------------------------------------------
class Client:
    def __init__(self, host: str, client_id: str, client_secret: str):
        self.host = host.rstrip("/")
        resp = requests.post(
            f"{self.host}/oidc/v1/token",
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials", "scope": "all-apis"},
            timeout=30,
        )
        resp.raise_for_status()
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"
        # NOTE: the token expires (typically after an hour). Long deploys need refresh logic.

    def call(self, method: str, path: str, ok_404: bool = False, **kwargs):
        for attempt in range(6):
            r = self.session.request(method, f"{self.host}{path}", timeout=60, **kwargs)
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(min(2**attempt, 30))
                continue
            if ok_404 and r.status_code == 404:
                return None
            if r.status_code >= 400:
                raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:500]}")
            return r.json() if r.content else {}
        raise RuntimeError(f"{method} {path} exhausted retries")


# ---------------------------------------------------------------------------
# 3. Naming. Bundles derive all of this from `mode: development` / presets.
# ---------------------------------------------------------------------------
def names(env: str, user_short: str) -> dict[str, str]:
    if ENVIRONMENTS[env]["development"]:
        return {
            "schema": f"dev_{user_short}_{SCHEMA}",
            "pipeline": f"[dev {user_short}] orders_medallion",
            "job": f"[dev {user_short}] orders_refresh",
        }
    return {"schema": SCHEMA, "pipeline": "orders_medallion", "job": "orders_refresh"}


# ---------------------------------------------------------------------------
# 4. Deployment state + lock. Bundles keep both in the workspace automatically.
# ---------------------------------------------------------------------------
def state_paths(root: str) -> tuple[str, str]:
    return f"{root}/state/deployment.json", f"{root}/state/deploy.lock"


def read_state(c: Client, root: str) -> dict:
    path, _ = state_paths(root)
    exported = c.call("GET", "/api/2.0/workspace/export", ok_404=True,
                      params={"path": path, "format": "SOURCE"})
    return json.loads(base64.b64decode(exported["content"])) if exported else {}


def write_state(c: Client, root: str, state: dict) -> None:
    path, _ = state_paths(root)
    c.call("POST", "/api/2.0/workspace/import", json={
        "path": path, "format": "AUTO", "overwrite": True,
        "content": base64.b64encode(json.dumps(state, indent=2).encode()).decode()})


def acquire_lock(c: Client, root: str) -> str:
    _, lock = state_paths(root)
    c.call("POST", "/api/2.0/workspace/mkdirs", json={"path": f"{root}/state"})
    if c.call("GET", "/api/2.0/workspace/get-status", ok_404=True, params={"path": lock}):
        raise SystemExit(f"Another deployment holds {lock}. Delete it only if that deploy crashed.")
    token = str(uuid.uuid4())
    # Race window: two runners can both pass the check above. Real locking needs more care.
    c.call("POST", "/api/2.0/workspace/import", json={
        "path": lock, "format": "AUTO", "overwrite": False,
        "content": base64.b64encode(token.encode()).decode()})
    return token


def release_lock(c: Client, root: str) -> None:
    _, lock = state_paths(root)
    c.call("POST", "/api/2.0/workspace/delete", json={"path": lock})


# ---------------------------------------------------------------------------
# 5. Code upload. Bundles sync incrementally, honor .gitignore, and delete stale files.
# ---------------------------------------------------------------------------
def upload_tree(c: Client, local_root: Path, remote_root: str) -> set[str]:
    uploaded: set[str] = set()
    for path in sorted(local_root.rglob("*")):
        rel = path.relative_to(local_root).as_posix()
        if path.is_dir() or any(p in rel for p in (".venv", "__pycache__", ".pytest_cache", "dist/")):
            continue
        remote = f"{remote_root}/{rel}"
        c.call("POST", "/api/2.0/workspace/mkdirs", json={"path": remote.rsplit("/", 1)[0]})
        c.call("POST", "/api/2.0/workspace/import", json={
            "path": remote, "format": "AUTO", "overwrite": True,
            "content": base64.b64encode(path.read_bytes()).decode()})
        uploaded.add(remote)
    return uploaded


def delete_stale(c: Client, remote_root: str, keep: set[str]) -> None:
    stack = [remote_root]
    while stack:
        listing = c.call("GET", "/api/2.0/workspace/list", ok_404=True, params={"path": stack.pop()})
        for obj in (listing or {}).get("objects", []):
            if obj["object_type"] == "DIRECTORY":
                stack.append(obj["path"])
            elif obj["path"] not in keep:
                c.call("POST", "/api/2.0/workspace/delete", json={"path": obj["path"]})


def build_and_upload_wheel(c: Client, bundle_root: Path, artifact_root: str) -> str:
    subprocess.run(["uv", "build", "--wheel"], cwd=bundle_root, check=True)
    wheels = sorted(glob.glob(str(bundle_root / "dist" / "*.whl")), key=os.path.getmtime)
    if not wheels:
        raise SystemExit("wheel build produced nothing")
    wheel = Path(wheels[-1])
    # Serverless caches by filename: without a unique version per deploy, code changes
    # can be silently ignored. Bundles handle this with artifacts_dynamic_version.
    remote = f"{artifact_root}/{int(time.time())}/{wheel.name}"
    c.call("POST", "/api/2.0/workspace/mkdirs", json={"path": remote.rsplit("/", 1)[0]})
    c.call("POST", "/api/2.0/workspace/import", json={
        "path": remote, "format": "AUTO", "overwrite": True,
        "content": base64.b64encode(wheel.read_bytes()).decode()})
    return remote


# ---------------------------------------------------------------------------
# 6. Unity Catalog: create-or-update, then reconcile grants (add AND remove).
# ---------------------------------------------------------------------------
def ensure_schema(c: Client, catalog: str, schema: str) -> str:
    full = f"{catalog}.{schema}"
    comment = "Orders medallion data product (bronze, silver, gold)."
    if c.call("GET", f"/api/2.1/unity-catalog/schemas/{full}", ok_404=True) is None:
        c.call("POST", "/api/2.1/unity-catalog/schemas",
               json={"catalog_name": catalog, "name": schema, "comment": comment})
    else:
        c.call("PATCH", f"/api/2.1/unity-catalog/schemas/{full}", json={"comment": comment})
    return full


def ensure_volume(c: Client, catalog: str, schema: str, name: str) -> str:
    full = f"{catalog}.{schema}.{name}"
    if c.call("GET", f"/api/2.1/unity-catalog/volumes/{full}", ok_404=True) is None:
        c.call("POST", "/api/2.1/unity-catalog/volumes", json={
            "catalog_name": catalog, "schema_name": schema, "name": name,
            "volume_type": "MANAGED", "comment": "Raw order files (JSON)."})
    return full


def reconcile_grants(c: Client, securable: str, full: str, desired: dict[str, set[str]]) -> None:
    current = c.call("GET", f"/api/2.1/unity-catalog/permissions/{securable}/{full}")
    have = {a["principal"]: set(a.get("privileges", [])) for a in current.get("privilege_assignments", [])}
    changes = []
    for principal in set(have) | set(desired):
        add = sorted(desired.get(principal, set()) - have.get(principal, set()))
        remove = sorted(have.get(principal, set()) - desired.get(principal, set()))
        # Careful: removing privileges you did not grant (e.g. an admin's) is an outage.
        # Bundles only manage the grants they declare; a hand-written script must decide.
        if principal not in desired:
            remove = []
        if add or remove:
            changes.append({"principal": principal, "add": add, "remove": remove})
    if changes:
        c.call("PATCH", f"/api/2.1/unity-catalog/permissions/{securable}/{full}", json={"changes": changes})


# ---------------------------------------------------------------------------
# 7. Pipeline + job: create on first deploy, full replace afterwards, keyed by the
#    IDs we stored in state (names are not unique and must never be the key).
# ---------------------------------------------------------------------------
def upsert_pipeline(c: Client, state: dict, spec: dict) -> str:
    pid = state.get("pipeline_id")
    if pid and c.call("GET", f"/api/2.0/pipelines/{pid}", ok_404=True):
        c.call("PUT", f"/api/2.0/pipelines/{pid}", json={**spec, "id": pid})
        return pid
    created = c.call("POST", "/api/2.0/pipelines", json=spec)
    return created["pipeline_id"]


def upsert_job(c: Client, state: dict, settings: dict) -> int:
    jid = state.get("job_id")
    if jid and c.call("GET", "/api/2.2/jobs/get", ok_404=True, params={"job_id": jid}):
        c.call("POST", "/api/2.2/jobs/reset", json={"job_id": jid, "new_settings": settings})
        return jid
    return c.call("POST", "/api/2.2/jobs/create", json=settings)["job_id"]


def set_acl(c: Client, object_path: str, acl: list[dict]) -> None:
    # PUT replaces the full ACL. Remember: service principals are identified by
    # application ID; unknown principal names are silently dropped by some endpoints.
    c.call("PUT", f"/api/2.0/permissions/{object_path}", json={"access_control_list": acl})


# ---------------------------------------------------------------------------
# 8. Orchestration -- the part `bundle deploy` hides completely.
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", choices=sorted(ENVIRONMENTS), required=True)
    ap.add_argument("--bundle-root", type=Path, required=True)
    ap.add_argument("--run-as", help="service principal application ID for shared envs")
    args = ap.parse_args()
    env = ENVIRONMENTS[args.env]
    if env["shared"] and not args.run_as:
        raise SystemExit("--run-as is required for shared environments")

    c = Client(os.environ["DATABRICKS_HOST"], os.environ["DATABRICKS_CLIENT_ID"],
               os.environ["DATABRICKS_CLIENT_SECRET"])
    me = c.call("GET", "/api/2.0/preview/scim/v2/Me")
    user_name = me["userName"]
    user_short = user_name.split("@")[0].replace(".", "_").replace("-", "_")
    n = names(args.env, user_short)
    root = f"/Workspace/Users/{user_name}/.bundle/orders_rest/{args.env}"
    files_root, artifacts_root = f"{root}/files", f"{root}/artifacts"

    acquire_lock(c, root)
    try:
        state = read_state(c, root)

        # Code and artifacts
        uploaded = upload_tree(c, args.bundle_root, files_root)
        delete_stale(c, files_root, uploaded)
        wheel_path = build_and_upload_wheel(c, args.bundle_root, artifacts_root)

        # Unity Catalog objects, in dependency order
        catalog = env["catalog"]
        schema_full = ensure_schema(c, catalog, n["schema"])
        reconcile_grants(c, "schema", schema_full, {
            GROUPS["engineers"]: {"USE_SCHEMA", "SELECT"},
            GROUPS["consumers"]: {"USE_SCHEMA", "SELECT"}})
        volume_full = ensure_volume(c, catalog, n["schema"], "landing")
        reconcile_grants(c, "volume", volume_full, {
            GROUPS["engineers"]: {"READ_VOLUME", "WRITE_VOLUME"}})

        # Pipeline -- every path must be absolute and point at the uploaded copy
        tags = {**TAGS, "env": args.env}
        pipeline_spec = {
            "name": n["pipeline"], "catalog": catalog, "schema": n["schema"],
            "serverless": True, "continuous": False, "photon": True,
            "development": env["development"],
            "root_path": f"{files_root}/src/pipelines/orders_medallion",
            "libraries": [{"glob": {"include": f"{files_root}/src/pipelines/orders_medallion/transformations/**"}}],
            "environment": {"dependencies": [f"--editable {files_root}"]},
            "configuration": {"orders.landing_path": f"/Volumes/{catalog}/{n['schema']}/landing/orders"},
            "tags": tags,
        }
        if env["shared"]:
            pipeline_spec["run_as"] = {"service_principal_name": args.run_as}
        pipeline_id = upsert_pipeline(c, state, pipeline_spec)

        # Job -- the pipeline ID has to be threaded in by hand
        job_settings = {
            "name": n["job"], "max_concurrent_runs": 1, "tags": tags,
            "schedule": {"quartz_cron_expression": "0 0 6 * * ?", "timezone_id": "UTC",
                         "pause_status": "PAUSED" if env["paused"] else "UNPAUSED"},
            "parameters": [{"name": "catalog", "default": catalog},
                           {"name": "schema", "default": n["schema"]}],
            "tasks": [
                {"task_key": "refresh_pipeline",
                 "pipeline_task": {"pipeline_id": pipeline_id, "full_refresh": False}},
                {"task_key": "quality_gate", "depends_on": [{"task_key": "refresh_pipeline"}],
                 "environment_key": "default",
                 "python_wheel_task": {"package_name": "orders_lib", "entry_point": "quality_gate",
                                       "parameters": ["--catalog", "{{job.parameters.catalog}}",
                                                      "--schema", "{{job.parameters.schema}}"]}},
            ],
            "environments": [{"environment_key": "default",
                              "spec": {"environment_version": "4", "dependencies": [wheel_path]}}],
        }
        if env["shared"]:
            job_settings["run_as"] = {"service_principal_name": args.run_as}
        job_id = upsert_job(c, state, job_settings)

        # Permissions on every object, plus the deployment folder itself
        # Note the vocabulary differs per object type: CAN_MANAGE_RUN on jobs is CAN_RUN
        # on pipelines. Bundles translate one top-level `CAN_RUN` for you.
        job_acl = [{"group_name": GROUPS["engineers"], "permission_level": "CAN_VIEW"}]
        pipeline_acl = [{"group_name": GROUPS["engineers"], "permission_level": "CAN_VIEW"}]
        if env["shared"]:
            job_acl.append({"group_name": GROUPS["operators"], "permission_level": "CAN_MANAGE_RUN"})
            pipeline_acl.append({"group_name": GROUPS["operators"], "permission_level": "CAN_RUN"})
        set_acl(c, f"jobs/{job_id}", job_acl)
        set_acl(c, f"pipelines/{pipeline_id}", pipeline_acl)
        folder = c.call("GET", "/api/2.0/workspace/get-status", params={"path": root})
        set_acl(c, f"directories/{folder['object_id']}", [
            {"group_name": GROUPS["engineers"], "permission_level": "CAN_READ"}])

        # Resources removed from config must be deleted -- unless they hold data
        for key, path in (("pipeline_id", "/api/2.0/pipelines/{}"),):
            old = state.get(key)
            if old and old != pipeline_id and args.env not in PROTECTED_ENVS:
                c.call("DELETE", path.format(old), ok_404=True)

        write_state(c, root, {"pipeline_id": pipeline_id, "job_id": job_id, "schema": schema_full,
                              "volume": volume_full, "wheel": wheel_path, "deployed_at": time.time()})
        print(json.dumps({"pipeline_id": pipeline_id, "job_id": job_id}, indent=2))
    finally:
        release_lock(c, root)


if __name__ == "__main__":
    sys.exit(main())

# ---------------------------------------------------------------------------
# KNOWN GAPS -- each one is handled by `databricks bundle deploy` today:
#   * No plan / diff before applying (bundle plan; deploy --plan plan.json for approved plans).
#   * No schema validation of specs before calling APIs (bundle validate --strict).
#   * No drift detection between the last deployed config and what is live.
#   * No GitHub OIDC workload identity federation; needs a long-lived client secret.
#   * Token refresh, pagination, and API version changes are not handled.
#   * The file lock has a race window and no stale-lock recovery (--force-lock).
#   * `destroy` is not implemented at all; prevent_destroy is a hard-coded env list.
#   * No per-resource selective deploy, no `bundle run`, no `bundle summary`/`open`.
#   * Variables, lookups (e.g. warehouse ID by name), and complex variables do not exist.
#   * Adding a dashboard, app, model serving endpoint, Lakebase project, or Genie space
#     means another hand-written create/update/delete path per resource type.
# ---------------------------------------------------------------------------
