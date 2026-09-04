#!/usr/bin/env python3
"""Mercury MCP Server — lets Claude operate test/prod Mercury via tools.

Communicates over stdio (JSON-RPC). Requires `mcp` Python SDK.

Usage (Claude Code):
  Add to .claude/settings.local.json:
  {
    "mcpServers": {
      "mercury": {
        "command": "python3",
        "args": ["<path>/ceres/mcp_server.py"],
        "env": {
          "MERCURY_TEST_URL": "https://test-qa-mercury.aws.solab.ai",
          "MERCURY_PROD_URL": "https://prod-qa-mercury.aws.solab.ai"
        }
      }
    }
  }
"""
import asyncio
import json
import os
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# ── Config ──────────────────────────────────────────────────────────────────
ENVS = {
    "nb-test": os.environ.get("MERCURY_TEST_URL", "https://test-qa-mercury.aws.solab.ai"),
    "nb-prod": os.environ.get("MERCURY_PROD_URL", "https://prod-qa-mercury.aws.solab.ai"),
}

# In-memory JWT storage per environment
_tokens: dict[str, str] = {}

app = Server("mercury")


# ── Helpers ─────────────────────────────────────────────────────────────────
def _base_url(env: str) -> str:
    url = ENVS.get(env)
    if not url:
        raise ValueError(f"Unknown environment '{env}'. Use 'test' or 'prod'.")
    return url.rstrip("/")


def _headers(env: str) -> dict:
    token = _tokens.get(env)
    if not token:
        raise ValueError(f"Not logged in to '{env}'. Call the 'login' tool first.")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _parse_json(r: httpx.Response) -> Any:
    try:
        return r.json()
    except (json.JSONDecodeError, ValueError):
        raise ValueError(f"Server returned non-JSON response ({r.status_code}): {r.text[:300]}")


def _get(env: str, path: str, params: dict | None = None) -> Any:
    r = httpx.get(f"{_base_url(env)}/api/{path}", headers=_headers(env), params=params, timeout=30)
    r.raise_for_status()
    return _parse_json(r)


def _post(env: str, path: str, body: dict | None = None) -> Any:
    r = httpx.post(f"{_base_url(env)}/api/{path}", headers=_headers(env), json=body or {}, timeout=60)
    r.raise_for_status()
    return _parse_json(r)


def _download_file(env: str, testcase_id: int, filename: str) -> bytes:
    """Download a testcase file from Mercury as raw bytes."""
    r = httpx.get(
        f"{_base_url(env)}/api/testcases/{testcase_id}/download-file/",
        headers=_headers(env),
        params={"name": filename},
        timeout=120,
    )
    r.raise_for_status()
    return r.content


def _upload_file(env: str, testcase_id: int, filename: str, content: bytes, content_type: str = "application/octet-stream"):
    """Upload a file to a testcase in Mercury."""
    headers = {"Authorization": _headers(env)["Authorization"]}
    r = httpx.post(
        f"{_base_url(env)}/api/testcases/{testcase_id}/upload-file/",
        headers=headers,
        files={"file": (filename, content, content_type)},
        timeout=120,
    )
    r.raise_for_status()
    return _parse_json(r)


def _text(data: Any) -> list[TextContent]:
    if isinstance(data, str):
        return [TextContent(type="text", text=data)]
    return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2, default=str))]


# ── Tool definitions ────────────────────────────────────────────────────────
TOOLS = [
    Tool(
        name="list_environments",
        description="List all available Mercury environments (no login required).",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="login",
        description="Authenticate to Mercury (test or prod) via LDAP. Must be called before any other tool.",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"], "description": "Target environment"},
                "email": {"type": "string", "description": "LDAP email (e.g. user@shanda.com)"},
                "password": {"type": "string", "description": "LDAP password"},
            },
            "required": ["environment", "email", "password"],
        },
    ),
    Tool(
        name="project_list",
        description="List all projects the user has access to.",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
            },
            "required": ["environment"],
        },
    ),
    Tool(
        name="case_list",
        description="List testcases in a project. Supports search by name.",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "project": {"type": "integer", "description": "Project ID"},
                "search": {"type": "string", "description": "Case name substring filter"},
                "page_size": {"type": "integer", "description": "Max results (default 50)"},
            },
            "required": ["environment", "project"],
        },
    ),
    Tool(
        name="case_get",
        description="Get full details of a testcase by ID.",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "id": {"type": "integer", "description": "Testcase ID"},
            },
            "required": ["environment", "id"],
        },
    ),
    Tool(
        name="case_create",
        description="Create a new testcase.",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "project": {"type": "integer"},
                "case_name": {"type": "string"},
                "method": {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"]},
                "url": {"type": "string"},
                "headers": {"type": "array", "description": '[{"key":"k","value":"v","enabled":true}]'},
                "body_type": {"type": "string", "enum": ["none", "json", "formUrlEncoded", "multipart"]},
                "body": {"type": "object"},
                "assertions": {"type": "array"},
                "folder": {"type": "integer", "description": "Folder ID"},
                "pre_request_script": {"type": "string"},
                "post_request_script": {"type": "string"},
                "timeout": {"type": "integer", "description": "Request timeout in seconds (default 30)"},
                "ws_steps": {
                    "type": "array",
                    "description": (
                        "WebSocket-only. Required when url uses ws:// or wss:// (after {{var}} resolution). "
                        "Ordered steps: {kind:'send', payload_type:'text'|'json'|'binary_b64', payload:...} | "
                        "{kind:'recv', timeout_ms:int} | {kind:'wait', duration_ms:int} | "
                        "{kind:'close', code:int, reason:str}. recv defaults to 60s."
                    ),
                },
            },
            "required": ["environment", "project", "case_name", "method", "url"],
        },
    ),
    Tool(
        name="case_delete",
        description="Delete a testcase by ID (soft delete).",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "id": {"type": "integer", "description": "Testcase ID"},
            },
            "required": ["environment", "id"],
        },
    ),
    Tool(
        name="case_update",
        description="Update an existing testcase. Only include fields to change.",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "id": {"type": "integer"},
                "case_name": {"type": "string"},
                "method": {"type": "string"},
                "url": {"type": "string"},
                "headers": {"type": "array"},
                "body_type": {"type": "string"},
                "body": {"type": "object"},
                "assertions": {"type": "array"},
                "folder": {"type": "integer"},
                "pre_request_script": {"type": "string"},
                "post_request_script": {"type": "string"},
                "timeout": {"type": "integer", "description": "Request timeout in seconds"},
                "ws_steps": {
                    "type": "array",
                    "description": (
                        "WebSocket steps. Set to [] to clear, or omit to leave untouched. "
                        "See case_create.ws_steps for shape."
                    ),
                },
            },
            "required": ["environment", "id"],
        },
    ),
    Tool(
        name="case_run",
        description="Run a single testcase and return the result.",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "id": {"type": "integer", "description": "Testcase ID"},
                "env_id": {"type": "integer", "description": "Environment (Env) ID to use for variables"},
            },
            "required": ["environment", "id"],
        },
    ),
    Tool(
        name="plan_list",
        description="List testplans in a project.",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "project": {"type": "integer", "description": "Project ID"},
            },
            "required": ["environment"],
        },
    ),
    Tool(
        name="plan_get",
        description="Get testplan details including case count.",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "id": {"type": "integer"},
            },
            "required": ["environment", "id"],
        },
    ),
    Tool(
        name="plan_cases",
        description="List testcases in a testplan with sort order.",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "id": {"type": "integer", "description": "Testplan ID"},
            },
            "required": ["environment", "id"],
        },
    ),
    Tool(
        name="plan_add_cases",
        description="Add testcases to a testplan.",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "id": {"type": "integer", "description": "Testplan ID"},
                "case_ids": {"type": "array", "items": {"type": "integer"}, "description": "Testcase IDs to add"},
            },
            "required": ["environment", "id", "case_ids"],
        },
    ),
    Tool(
        name="plan_create",
        description="Create a new testplan.",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "project": {"type": "integer"},
                "name": {"type": "string"},
                "env_id": {"type": "integer", "description": "Environment ID for variable resolution"},
                "is_serial": {"type": "boolean", "description": "Serial execution (default true)"},
                "feishu_webhook": {"type": "string", "description": "Feishu webhook URL for notifications"},
            },
            "required": ["environment", "project", "name", "env_id"],
        },
    ),
    Tool(
        name="plan_update",
        description="Update an existing testplan. Only include fields to change.",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "id": {"type": "integer", "description": "Testplan ID"},
                "name": {"type": "string"},
                "env_id": {"type": "integer", "description": "Environment ID"},
                "is_serial": {"type": "boolean"},
                "feishu_webhook": {"type": "string"},
                "notify_on_failure": {"type": "boolean"},
                "phone_on_failure": {"type": "boolean"},
            },
            "required": ["environment", "id"],
        },
    ),
    Tool(
        name="plan_remove_cases",
        description="Remove testcases from a testplan.",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "id": {"type": "integer", "description": "Testplan ID"},
                "case_ids": {"type": "array", "items": {"type": "integer"}, "description": "Testcase IDs to remove"},
            },
            "required": ["environment", "id", "case_ids"],
        },
    ),
    Tool(
        name="plan_run",
        description="Run a testplan. Returns execution ID and status.",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "id": {"type": "integer", "description": "Testplan ID"},
                "env_id": {"type": "integer", "description": "Override environment ID"},
            },
            "required": ["environment", "id"],
        },
    ),
    Tool(
        name="plan_sync",
        description="Sync all testplan case snapshots from live testcases.",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "id": {"type": "integer", "description": "Testplan ID"},
            },
            "required": ["environment", "id"],
        },
    ),
    Tool(
        name="execution_list",
        description="List recent test executions. Filter by status, trigger type, testplan.",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "project": {"type": "integer"},
                "status": {"type": "string", "enum": ["passed", "failed", "running", "error"]},
                "trigger_type": {"type": "string", "enum": ["manual", "scheduled", "api"]},
                "testplan": {"type": "integer", "description": "Testplan ID"},
                "page_size": {"type": "integer"},
            },
            "required": ["environment"],
        },
    ),
    Tool(
        name="execution_get",
        description="Get execution summary (pass/fail counts, duration, pass rate).",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "id": {"type": "integer", "description": "Execution ID"},
            },
            "required": ["environment", "id"],
        },
    ),
    Tool(
        name="execution_case_results",
        description="Get per-case results of an execution. Filter by status to see failures.",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "id": {"type": "integer", "description": "Execution ID"},
                "status": {"type": "string", "enum": ["passed", "failed", "error"], "description": "Filter by case status"},
                "page_size": {"type": "integer"},
            },
            "required": ["environment", "id"],
        },
    ),
    Tool(
        name="folder_list",
        description="List folders (flat) for a project. Use folder_tree for the nested view.",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "project": {"type": "integer"},
                "parent": {"type": "integer", "description": "Filter to direct children of this folder"},
            },
            "required": ["environment"],
        },
    ),
    Tool(
        name="folder_tree",
        description="Get the folder tree for a project (nested, includes testcase_count per folder).",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "project": {"type": "integer"},
            },
            "required": ["environment", "project"],
        },
    ),
    Tool(
        name="folder_create",
        description="Create a folder under a project (top-level when parent is omitted).",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "project": {"type": "integer"},
                "name": {"type": "string"},
                "parent": {"type": "integer", "description": "Parent folder ID (omit for root)"},
                "sort_order": {"type": "integer"},
            },
            "required": ["environment", "project", "name"],
        },
    ),
    Tool(
        name="folder_update",
        description="Rename or move a folder. Only include fields to change.",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "id": {"type": "integer", "description": "Folder ID"},
                "name": {"type": "string"},
                "parent": {"type": "integer", "description": "New parent folder ID (use null/omit to move to root)"},
                "sort_order": {"type": "integer"},
            },
            "required": ["environment", "id"],
        },
    ),
    Tool(
        name="folder_delete",
        description="Soft-delete a folder. Subfolders cascade; testcases inside become folder=null.",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "id": {"type": "integer", "description": "Folder ID"},
            },
            "required": ["environment", "id"],
        },
    ),
    Tool(
        name="env_list",
        description="List environments (with variable names) for a project.",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "project": {"type": "integer"},
            },
            "required": ["environment"],
        },
    ),
    Tool(
        name="env_create",
        description="Create a new environment with variables.",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "project": {"type": "integer"},
                "name": {"type": "string", "description": "Environment name"},
                "variables": {"type": "string", "description": "JSON string of variables"},
            },
            "required": ["environment", "project", "name"],
        },
    ),
    Tool(
        name="env_update",
        description="Update an environment's variables. Merges with existing variables (use null to delete a key).",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "id": {"type": "integer", "description": "Environment ID"},
                "variables": {"type": "string", "description": "JSON string of variables to merge (null value deletes a key)"},
            },
            "required": ["environment", "id", "variables"],
        },
    ),
    Tool(
        name="project_sync",
        description="Export a project from one environment and import to another. Overwrites all folders, testcases, envs, testplans in the target project.",
        inputSchema={
            "type": "object",
            "properties": {
                "from_environment": {"type": "string", "enum": ["nb-test", "nb-prod"], "description": "Source environment to export from"},
                "from_project_id": {"type": "integer", "description": "Source project ID"},
                "to_environment": {"type": "string", "enum": ["nb-test", "nb-prod"], "description": "Target environment to import to"},
                "to_project_id": {"type": "integer", "description": "Target project ID"},
            },
            "required": ["from_environment", "from_project_id", "to_environment", "to_project_id"],
        },
    ),
    Tool(
        name="coverage_check",
        description=(
            "Aggregate real user requests to NB backend over the past N hours from "
            "the deployed mercury's nginx ES logs and report which URL patterns are "
            "covered by Ceres testcases vs not. Mercury-originated traffic "
            "(User-Agent contains 'Mercury-Monitor' or 'python-requests') is "
            "filtered server-side. Available on nb-test (test ES) and nb-prod "
            "(prod ES). No login required."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "hours": {"type": "integer", "description": "Lookback window in hours (default 24)"},
                "project": {"type": "integer", "description": "Ceres project ID to compare coverage against (optional)"},
                "host": {"type": "string", "description": "Restrict to a specific http_host"},
                "exclude_host": {"type": "string", "description": "Drop a specific http_host"},
                "top_n": {"type": "integer", "description": "Max patterns returned in covered/uncovered lists (default 200)"},
                "raw_top_n": {"type": "integer", "description": "Top-N raw URLs pulled from ES before normalization (default 10000)"},
            },
            "required": ["environment"],
        },
    ),
    # ── Perf Plans ──────────────────────────────────────────────────────
    Tool(
        name="perf_plan_list",
        description="List PerfPlans (load testing plans) for a project. Returns id, name, target_rate, duration_secs, transaction_count, case_count.",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "project": {"type": "integer"},
                "search": {"type": "string"},
            },
            "required": ["environment"],
        },
    ),
    Tool(
        name="perf_plan_get",
        description="Get full PerfPlan detail including nested setup + transaction cases (with snapshots).",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "id": {"type": "integer", "description": "PerfPlan ID"},
            },
            "required": ["environment", "id"],
        },
    ),
    Tool(
        name="perf_plan_create",
        description="Create a PerfPlan. After creation, attach cases via perf_plan_cases_add and (optionally) upload data files via curl: /api/perf-plans/{id}/upload-account-pool/ for account pool or /cases/{plan_case_id}/upload-data/ per case (multipart over MCP stdio is unreliable for large files — use curl).",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "project": {"type": "integer"},
                "env": {"type": "integer", "description": "Ceres env ID (the {{host}}/etc. var set)"},
                "name": {"type": "string"},
                "description": {"type": "string"},
                "target_rate": {"type": "integer", "description": "Target RPS (default 100)"},
                "duration_secs": {"type": "integer", "description": "Run duration in seconds (default 60)"},
                "max_vus": {"type": "integer", "description": "Max concurrent VUs (default 50)"},
                "transactions": {"type": "array", "description": "[{name, weight, sort_order}]. Names referenced by perf_plan_cases_add with role='transaction'."},
                "notify_feishu_webhook": {"type": "string"},
                "notify_on_completion": {"type": "boolean"},
                "notify_on_failure": {"type": "boolean"},
            },
            "required": ["environment", "project", "name"],
        },
    ),
    Tool(
        name="perf_plan_update",
        description="Partial update of a PerfPlan. Only include fields you want to change. To edit cases, use perf_plan_cases_*.",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "id": {"type": "integer"},
                "name": {"type": "string"},
                "description": {"type": "string"},
                "env": {"type": "integer"},
                "target_rate": {"type": "integer"},
                "duration_secs": {"type": "integer"},
                "max_vus": {"type": "integer"},
                "transactions": {"type": "array"},
                "notify_feishu_webhook": {"type": "string"},
                "notify_on_completion": {"type": "boolean"},
                "notify_on_failure": {"type": "boolean"},
            },
            "required": ["environment", "id"],
        },
    ),
    Tool(
        name="perf_plan_delete",
        description="Soft-delete a PerfPlan.",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "id": {"type": "integer"},
            },
            "required": ["environment", "id"],
        },
    ),
    Tool(
        name="perf_plan_cases_add",
        description="Attach testcases to a PerfPlan. role='setup' runs once per VU at startup (in order). role='transaction' joins the named transaction's case chain (in sort order; weighted-picked at runtime).",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "id": {"type": "integer", "description": "PerfPlan ID"},
                "role": {"type": "string", "enum": ["setup", "transaction"]},
                "transaction_name": {"type": "string", "description": "Required for role='transaction'; must match an entry in plan.transactions[]."},
                "case_ids": {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["environment", "id", "role", "case_ids"],
        },
    ),
    Tool(
        name="perf_plan_cases_delete",
        description="Detach cases from a PerfPlan by their PerfPlanCase IDs (not testcase IDs — use perf_plan_get to discover them).",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "id": {"type": "integer", "description": "PerfPlan ID"},
                "plan_case_ids": {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["environment", "id", "plan_case_ids"],
        },
    ),
    Tool(
        name="perf_plan_sync",
        description="Refresh case_snapshot for every PerfPlanCase from the live testcase row. Returns list of cases whose snapshot diverged. Run this after editing referenced testcases so subsequent runs see the latest definition.",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "id": {"type": "integer", "description": "PerfPlan ID"},
            },
            "required": ["environment", "id"],
        },
    ),
    Tool(
        name="perf_plan_run",
        description="Trigger a load run for a PerfPlan. Async — returns the PerfRun id immediately with status='pending'. Poll perf_run_get to watch summary_json (refreshed every ~2s). Run params can override plan defaults.",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "id": {"type": "integer", "description": "PerfPlan ID"},
                "target_rate": {"type": "integer", "description": "Override target RPS"},
                "duration_secs": {"type": "integer", "description": "Override duration"},
                "max_vus": {"type": "integer", "description": "Override max VUs"},
            },
            "required": ["environment", "id"],
        },
    ),
    Tool(
        name="perf_run_list",
        description="List recent runs for a plan (default 50, ordered newest first).",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "plan_id": {"type": "integer"},
                "limit": {"type": "integer"},
            },
            "required": ["environment", "plan_id"],
        },
    ),
    Tool(
        name="perf_run_get",
        description="Get one PerfRun — status, started/finished time, summary_json (live during running, frozen on completion).",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "id": {"type": "integer", "description": "PerfRun ID"},
            },
            "required": ["environment", "id"],
        },
    ),
    Tool(
        name="perf_run_abort",
        description="Signal a running PerfRun to stop. Driver polls status every ~1s and transitions to 'aborted' after finishing in-flight requests (graceful).",
        inputSchema={
            "type": "object",
            "properties": {
                "environment": {"type": "string", "enum": ["nb-test", "nb-prod"]},
                "id": {"type": "integer", "description": "PerfRun ID"},
            },
            "required": ["environment", "id"],
        },
    ),
]


# ── Tool handlers ───────────────────────────────────────────────────────────
@app.list_tools()
async def list_tools():
    return TOOLS


def _coerce_args(name: str, arguments: dict) -> dict:
    """Auto-fix common parameter issues: string→int coercion and name aliases."""
    args = dict(arguments)

    # Map common aliases to canonical parameter names
    _aliases = {
        "plan_id": "id", "case_id": "id", "execution_id": "id",
        "source_env": "from_environment", "target_env": "to_environment",
        "source_project_id": "from_project_id", "target_project_id": "to_project_id",
        "project_name": None,  # drop unsupported params
        "limit": "page_size",
    }
    for alias, canonical in _aliases.items():
        if alias in args and canonical and canonical not in args:
            args[canonical] = args.pop(alias)
        elif alias in args and canonical is None:
            args.pop(alias)

    # Find the tool schema to know which fields should be integers
    tool_schema = next((t for t in TOOLS if t.name == name), None)
    if tool_schema:
        props = tool_schema.inputSchema.get("properties", {})
        for key, spec in props.items():
            if spec.get("type") == "integer" and key in args and isinstance(args[key], str):
                try:
                    args[key] = int(args[key])
                except (ValueError, TypeError):
                    pass

    return args


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        arguments = _coerce_args(name, arguments)
        return await asyncio.to_thread(_dispatch, name, arguments)
    except httpx.TimeoutException:
        env = arguments.get("environment", "?")
        return _text(f"Request timed out connecting to {env}")
    except httpx.ConnectError:
        env = arguments.get("environment", "?")
        return _text(f"Cannot connect to {env} — check network or URL")
    except httpx.HTTPStatusError as e:
        body = e.response.text[:500]
        return _text(f"HTTP {e.response.status_code}: {body}")
    except ValueError as e:
        return _text(f"Error: {e}")
    except Exception as e:
        return _text(f"Error: {type(e).__name__}: {e}")


def _dispatch(name: str, args: dict) -> list[TextContent]:
    # ── List environments (no login needed) ───────────────────────────
    if name == "list_environments":
        envs = []
        for key, url in ENVS.items():
            logged_in = key in _tokens
            envs.append({"name": key, "url": url, "logged_in": logged_in})
        return _text(envs)

    env = args.get("environment", "nb-test")

    # ── Login ───────────────────────────────────────────────────────────
    if name == "login":
        try:
            r = httpx.post(
                f"{_base_url(env)}/api/auth/login/",
                json={"email": args["email"], "password": args["password"]},
                timeout=15,
            )
        except httpx.TimeoutException:
            return _text(f"Login failed: connection to {env} timed out")
        except httpx.ConnectError:
            return _text(f"Login failed: cannot connect to {env} ({_base_url(env)})")
        except httpx.HTTPError as e:
            return _text(f"Login failed: {type(e).__name__}: {e}")
        if r.status_code != 200:
            try:
                detail = r.json().get("detail", r.text)
            except Exception:
                detail = r.text
            return _text(f"Login failed ({r.status_code}): {detail}")
        data = r.json()
        _tokens[env] = data["token"]
        user = data.get("user", {})
        return _text(f"Logged in to {env} as {user.get('display_name', user.get('email'))}")

    # ── Projects ────────────────────────────────────────────────────────
    if name == "project_list":
        return _text(_get(env, "projects/"))

    # ── Cases ───────────────────────────────────────────────────────────
    if name == "case_list":
        params = {"project": args.get("project"), "search": args.get("search"), "page_size": args.get("page_size", 50)}
        return _text(_get(env, "testcases/", {k: v for k, v in params.items() if v is not None}))

    if name == "case_get":
        return _text(_get(env, f"testcases/{args['id']}/"))

    if name == "case_create":
        body = {k: v for k, v in args.items() if k not in ("environment",) and v is not None}
        return _text(_post(env, "testcases/", body))

    if name == "case_delete":
        r = httpx.delete(f"{_base_url(env)}/api/testcases/{args['id']}/", headers=_headers(env), timeout=30)
        r.raise_for_status()
        return _text(f"Deleted testcase {args['id']}")

    if name == "case_update":
        cid = args.pop("id")
        body = {k: v for k, v in args.items() if k not in ("environment",) and v is not None}
        r = httpx.patch(f"{_base_url(env)}/api/testcases/{cid}/", headers=_headers(env), json=body, timeout=30)
        r.raise_for_status()
        return _text(_parse_json(r))

    if name == "case_run":
        body = {}
        if args.get("env_id"):
            body["env_id"] = args["env_id"]
        return _text(_post(env, f"testcases/{args['id']}/run/", body))

    # ── Plans ───────────────────────────────────────────────────────────
    if name == "plan_list":
        params = {"project": args.get("project")}
        return _text(_get(env, "testplans/", {k: v for k, v in params.items() if v is not None}))

    if name == "plan_get":
        return _text(_get(env, f"testplans/{args['id']}/"))

    if name == "plan_cases":
        return _text(_get(env, f"testplans/{args['id']}/cases/"))

    if name == "plan_create":
        body = {
            "project": args["project"],
            "name": args["name"],
            "env": args["env_id"],
            "is_serial": args.get("is_serial", True),
        }
        if args.get("feishu_webhook"):
            body["feishu_webhook"] = args["feishu_webhook"]
        return _text(_post(env, "testplans/", body))

    if name == "plan_update":
        pid = args.pop("id")
        body = {}
        if "name" in args: body["name"] = args["name"]
        if "env_id" in args: body["env"] = args["env_id"]
        if "is_serial" in args: body["is_serial"] = args["is_serial"]
        if "feishu_webhook" in args: body["feishu_webhook"] = args["feishu_webhook"]
        if "notify_on_failure" in args: body["notify_on_failure"] = args["notify_on_failure"]
        if "phone_on_failure" in args: body["phone_on_failure"] = args["phone_on_failure"]
        r = httpx.patch(f"{_base_url(env)}/api/testplans/{pid}/", headers=_headers(env), json=body, timeout=30)
        r.raise_for_status()
        return _text(_parse_json(r))

    if name == "plan_add_cases":
        return _text(_post(env, f"testplans/{args['id']}/cases/", {"case_ids": args["case_ids"]}))

    if name == "plan_remove_cases":
        case_ids = set(args["case_ids"])
        plan_cases = _get(env, f"testplans/{args['id']}/cases/")
        plan_case_ids = [pc["id"] for pc in plan_cases if pc["testcase"] in case_ids]
        if not plan_case_ids:
            return _text({"deleted": 0, "note": "No matching cases in plan"})
        r = httpx.request(
            "DELETE",
            f"{_base_url(env)}/api/testplans/{args['id']}/cases/",
            headers=_headers(env),
            json={"plan_case_ids": plan_case_ids},
            timeout=30,
        )
        r.raise_for_status()
        return _text(_parse_json(r))

    if name == "plan_run":
        body = {}
        if args.get("env_id"):
            body["env_id"] = args["env_id"]
        return _text(_post(env, f"testplans/{args['id']}/run/", body))

    if name == "plan_sync":
        # GET diffs first, then POST all
        diffs = _get(env, f"testplans/{args['id']}/sync/")
        if not diffs:
            return _text("All cases are up to date.")
        ids = [d["plan_case_id"] for d in diffs]
        result = _post(env, f"testplans/{args['id']}/sync/", {"plan_case_ids": ids})
        return _text(f"Synced {result.get('synced', 0)} case(s). Changed: {[d['case_name'] for d in diffs]}")

    # ── Executions ──────────────────────────────────────────────────────
    if name == "execution_list":
        params = {
            "project": args.get("project"),
            "status": args.get("status"),
            "trigger_type": args.get("trigger_type"),
            "testplan": args.get("testplan"),
            "page_size": args.get("page_size", 10),
            "ordering": "-id",
        }
        return _text(_get(env, "executions/", {k: v for k, v in params.items() if v is not None}))

    if name == "execution_get":
        return _text(_get(env, f"executions/{args['id']}/"))

    if name == "execution_case_results":
        params = {"status": args.get("status"), "page_size": args.get("page_size", 50)}
        return _text(_get(env, f"executions/{args['id']}/case-results/", {k: v for k, v in params.items() if v is not None}))

    # ── Folders ─────────────────────────────────────────────────────────
    if name == "folder_list":
        params = {k: args.get(k) for k in ("project", "parent")}
        return _text(_get(env, "folders/", {k: v for k, v in params.items() if v is not None}))

    if name == "folder_tree":
        return _text(_get(env, "folders/tree/", {"project": args["project"]}))

    if name == "folder_create":
        body = {"project": args["project"], "name": args["name"]}
        if args.get("parent") is not None:
            body["parent"] = args["parent"]
        if args.get("sort_order") is not None:
            body["sort_order"] = args["sort_order"]
        return _text(_post(env, "folders/", body))

    if name == "folder_update":
        fid = args["id"]
        body = {k: v for k, v in args.items() if k not in ("environment", "id") and v is not None}
        r = httpx.patch(
            f"{_base_url(env)}/api/folders/{fid}/",
            headers=_headers(env), json=body, timeout=30,
        )
        r.raise_for_status()
        return _text(_parse_json(r))

    if name == "folder_delete":
        r = httpx.delete(
            f"{_base_url(env)}/api/folders/{args['id']}/",
            headers=_headers(env), timeout=30,
        )
        r.raise_for_status()
        return _text(f"Deleted folder {args['id']}")

    # ── Environments ────────────────────────────────────────────────────
    if name == "env_list":
        params = {"project": args.get("project")}
        return _text(_get(env, "envs/", {k: v for k, v in params.items() if v is not None}))

    if name == "env_create":
        variables = args.get("variables", "{}")
        if isinstance(variables, str):
            variables = json.loads(variables)
        body = {"project": args["project"], "name": args["name"], "variables": variables}
        return _text(_post(env, "envs/", body))

    if name == "env_update":
        env_id = args["id"]
        # Fetch current variables, merge, then patch
        current = _get(env, f"envs/{env_id}/")
        variables = dict(current.get("variables", {}))
        new_vars = args["variables"]
        if isinstance(new_vars, str):
            new_vars = json.loads(new_vars)
        for k, v in new_vars.items():
            if v is None:
                variables.pop(k, None)
            else:
                variables[k] = v
        r = httpx.patch(
            f"{_base_url(env)}/api/envs/{env_id}/",
            headers=_headers(env),
            json={"variables": variables},
            timeout=30,
        )
        r.raise_for_status()
        return _text(_parse_json(r))

    # ── Project sync (export from A, import to B) ────────────────────
    if name == "project_sync":
        src_env = args["from_environment"]
        dst_env = args["to_environment"]
        src_id = args["from_project_id"]
        dst_id = args["to_project_id"]

        export_data = _get(src_env, f"projects/{src_id}/export/")
        src_stats = {
            "folders": len(export_data.get("folders", [])),
            "testcases": len(export_data.get("testcases", [])),
            "envs": len(export_data.get("envs", [])),
            "testplans": len(export_data.get("testplans", [])),
        }

        # Collect file info and strip files from export (will re-upload after import)
        files_by_source_id: dict[int, list[dict]] = {}
        for tc in export_data.get("testcases", []):
            if tc.get("files"):
                files_by_source_id[tc["source_id"]] = tc["files"]
                tc["files"] = []

        result = _post(dst_env, f"projects/{dst_id}/import/", export_data)
        case_id_map = result.get("case_id_map", {})

        # Transfer files: download from source, upload to target
        files_transferred = 0
        files_failed = []
        for src_case_id, file_list in files_by_source_id.items():
            dst_case_id = case_id_map.get(str(src_case_id))
            if not dst_case_id:
                continue
            for file_meta in file_list:
                fname = file_meta.get("name", "")
                try:
                    content = _download_file(src_env, src_case_id, fname)
                    _upload_file(dst_env, dst_case_id, fname, content,
                                 file_meta.get("content_type", "application/octet-stream"))
                    files_transferred += 1
                except Exception as e:
                    files_failed.append(f"{fname} (case {src_case_id}): {e}")

        return _text({
            "message": f"Synced {src_env} project {src_id} -> {dst_env} project {dst_id}",
            "exported": src_stats,
            "imported": result.get("stats", result),
            "files_transferred": files_transferred,
            "files_failed": files_failed or None,
        })

    # ── Coverage check (no auth, hits /api/coverage_monitor/) ──────────
    if name == "coverage_check":
        if env not in ("nb-test", "nb-prod"):
            return _text(f"coverage_check supports nb-test/nb-prod only, got '{env}'")
        # The mercury view uses env=test|prod (matches its own ENV setting,
        # which is independent of MCP's environment naming).
        target_env = "prod" if env == "nb-prod" else "test"
        params = {
            "env": target_env,
            "hours": args.get("hours", 24),
            "top_n": args.get("top_n", 200),
            "raw_top_n": args.get("raw_top_n", 10000),
        }
        if args.get("project") is not None:
            params["project"] = args["project"]
        if args.get("host"):
            params["host"] = args["host"]
        if args.get("exclude_host"):
            params["exclude_host"] = args["exclude_host"]
        r = httpx.get(f"{_base_url(env)}/api/coverage_monitor/", params=params, timeout=120)
        r.raise_for_status()
        return _text(_parse_json(r))

    # ── Perf Plans ──────────────────────────────────────────────────────
    if name == "perf_plan_list":
        params = {k: v for k, v in {"project": args.get("project"), "search": args.get("search")}.items() if v is not None}
        return _text(_get(env, "perf-plans/", params))

    if name == "perf_plan_get":
        return _text(_get(env, f"perf-plans/{args['id']}/"))

    if name == "perf_plan_create":
        body = {k: v for k, v in args.items() if k not in ("environment",) and v is not None}
        return _text(_post(env, "perf-plans/", body))

    if name == "perf_plan_update":
        pid = args.pop("id")
        body = {k: v for k, v in args.items() if k not in ("environment",) and v is not None}
        r = httpx.patch(f"{_base_url(env)}/api/perf-plans/{pid}/", headers=_headers(env), json=body, timeout=30)
        r.raise_for_status()
        return _text(_parse_json(r))

    if name == "perf_plan_delete":
        r = httpx.delete(f"{_base_url(env)}/api/perf-plans/{args['id']}/", headers=_headers(env), timeout=30)
        r.raise_for_status()
        return _text(f"Deleted perf plan {args['id']}")

    if name == "perf_plan_cases_add":
        body = {
            "role": args["role"],
            "transaction_name": args.get("transaction_name", ""),
            "case_ids": args["case_ids"],
        }
        return _text(_post(env, f"perf-plans/{args['id']}/cases/", body))

    if name == "perf_plan_cases_delete":
        r = httpx.delete(
            f"{_base_url(env)}/api/perf-plans/{args['id']}/cases/",
            headers=_headers(env),
            json={"plan_case_ids": args["plan_case_ids"]},
            timeout=30,
        )
        r.raise_for_status()
        return _text(_parse_json(r))

    if name == "perf_plan_sync":
        return _text(_post(env, f"perf-plans/{args['id']}/sync/"))

    if name == "perf_plan_run":
        body = {k: v for k, v in args.items() if k in ("target_rate", "duration_secs", "max_vus") and v is not None}
        return _text(_post(env, f"perf-plans/{args['id']}/run/", body))

    if name == "perf_run_list":
        params = {}
        if args.get("limit") is not None:
            params["limit"] = args["limit"]
        return _text(_get(env, f"perf-plans/{args['plan_id']}/runs/", params))

    if name == "perf_run_get":
        return _text(_get(env, f"perf-runs/{args['id']}/"))

    if name == "perf_run_abort":
        return _text(_post(env, f"perf-runs/{args['id']}/abort/"))

    return _text(f"Unknown tool: {name}")


# ── Main ────────────────────────────────────────────────────────────────────
async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
