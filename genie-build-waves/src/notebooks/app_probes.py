"""Authenticated HTTP probes against Databricks Apps.

Shared by wave_gate_check (runtime gate) and app_probe_check (smoke job).

Requests go only to the app's own URL as returned by `w.apps.get(name).url`; a probe
supplies a path, never a host. Auth uses `w.config.authenticate()` headers for the
caller's identity (in a job: the run-as identity), which needs CAN_USE on the app.
Redirects are not followed: the Apps auth proxy answers an unaccepted credential with
a redirect to sign-in, which is reported as an auth failure rather than followed.
"""

import json
import re
import time
from urllib.parse import urlparse

import requests

DEFAULT_PROBE = {"path": "/", "method": "GET", "expect_status": [200, 204]}
MCP_PROTOCOL_VERSION = "2025-03-26"
_PATH_RE = re.compile(r"^/[A-Za-z0-9._~!$&'()*+,;=:@%/?\-]*$")


def validate_probe(p) -> list[str]:
    """Static checks for one probe definition (used by the setup notebook too)."""
    errs = []
    if not isinstance(p, dict):
        return [f"probe must be an object (got {p!r})"]
    path = p.get("path")
    if not isinstance(path, str) or not _PATH_RE.match(path) or "://" in path or path.startswith("//"):
        errs.append(f"probe path must be an absolute path on the app such as /api/health (got {path!r})")
    method = str(p.get("method", "POST" if p.get("mcp_initialize") else "GET")).upper()
    if method not in ("GET", "POST", "HEAD"):
        errs.append(f"probe {path}: method must be GET, POST or HEAD")
    if p.get("mcp_initialize") and method != "POST":
        errs.append(f"probe {path}: mcp_initialize probes are POST")
    es = p.get("expect_status", 200)
    if not all(isinstance(x, int) for x in (es if isinstance(es, list) else [es])):
        errs.append(f"probe {path}: expect_status must be an integer or a list of integers")
    if p.get("response_regex") is not None:
        try:
            re.compile(p["response_regex"])
        except re.error as e:
            errs.append(f"probe {path}: invalid response_regex: {e}")
    return errs


def _sse_or_json(text: str):
    """MCP servers answer with JSON or an SSE stream; return the first JSON-RPC message."""
    text = (text or "").strip()
    if text.startswith("{"):
        return json.loads(text)
    for line in text.splitlines():
        if line.startswith("data:"):
            data = line[5:].strip()
            if data.startswith("{"):
                return json.loads(data)
    return None


def run_probe(base_url: str, headers: dict, probe: dict, timeout_s: int = 30, session=None) -> dict:
    """Run one probe. Returns {path, method, status, result: pass|fail, detail, elapsed_ms}."""
    s = session or requests
    path = probe["path"]
    mcp = bool(probe.get("mcp_initialize"))
    method = str(probe.get("method", "POST" if mcp else "GET")).upper()
    expect = probe.get("expect_status", 200)
    expect = expect if isinstance(expect, list) else [expect]
    hdrs = dict(headers)
    body = None
    if mcp:
        hdrs.update({"Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
        body = json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": MCP_PROTOCOL_VERSION, "capabilities": {},
                       "clientInfo": {"name": "genie-build-waves-gate", "version": "1"}},
        })
    elif probe.get("json") is not None:
        hdrs["Content-Type"] = "application/json"
        body = json.dumps(probe["json"])

    out = {"path": path, "method": method, "mcp_initialize": mcp}
    t0 = time.time()
    try:
        r = s.request(method, base_url.rstrip("/") + path, headers=hdrs, data=body,
                      allow_redirects=False, timeout=int(probe.get("timeout_seconds", timeout_s)))
    except requests.RequestException as e:
        out.update({"result": "fail", "detail": f"{type(e).__name__}: {str(e)[:200]}"})
        return out
    out.update({"status": r.status_code, "elapsed_ms": int((time.time() - t0) * 1000)})

    if 300 <= r.status_code < 400:
        loc = r.headers.get("Location", "")
        same_host = urlparse(loc).netloc in ("", urlparse(base_url).netloc)
        why = "redirect" if same_host else "redirected to sign-in: the app did not accept this identity's credentials"
        if r.status_code not in expect:
            out.update({"result": "fail", "detail": f"{r.status_code} {why} ({loc[:120]})"})
            return out
    if r.status_code in (401, 403) and r.status_code not in expect:
        out.update({"result": "fail", "detail": f"{r.status_code}: identity lacks access (needs CAN_USE on the app)"})
        return out
    if r.status_code not in expect:
        out.update({"result": "fail", "detail": f"status {r.status_code}, expected {expect}: {r.text[:200]}"})
        return out

    if mcp:
        try:
            msg = _sse_or_json(r.text)
        except ValueError as e:
            msg, out["detail"] = None, f"unparseable MCP response: {e}"
        info = ((msg or {}).get("result") or {}).get("serverInfo")
        if not info:
            err = (msg or {}).get("error")
            out.update({"result": "fail", "detail": out.get("detail") or f"no result.serverInfo in initialize response"
                        + (f" (error: {json.dumps(err)[:200]})" if err else f": {r.text[:200]}")})
            return out
        out["server_info"] = info
        out["protocol_version"] = ((msg or {}).get("result") or {}).get("protocolVersion")

    rx = probe.get("response_regex")
    if rx and not re.search(rx, r.text or ""):
        out.update({"result": "fail", "detail": f"response did not match {rx!r}: {r.text[:200]}"})
        return out
    out["result"] = "pass"
    return out


def run_app_probes(w, app_name: str, probes: list | None = None, timeout_s: int = 30, retries: int = 1, session=None):
    """Probe one app. Returns (results, problems). Each failing probe is retried `retries` times (cold start)."""
    app = w.apps.get(app_name)
    if not app.url:
        return [], [f"app {app_name} has no URL (not deployed?)"]
    headers = w.config.authenticate()
    results, problems = [], []
    for p in probes or [DEFAULT_PROBE]:
        res = run_probe(app.url, headers, p, timeout_s, session)
        for _ in range(retries):
            if res["result"] == "pass":
                break
            time.sleep(10)
            res = run_probe(app.url, headers, p, timeout_s, session)
        results.append(res)
        if res["result"] != "pass":
            problems.append(f"probe {res['method']} {res['path']}: {res.get('detail')}")
    return results, problems
