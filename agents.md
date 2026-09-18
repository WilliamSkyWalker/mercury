# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Related Projects

- **Predict Backend**: `~/Documents/predict`
- **Predict Frontend**: `~/Documents/predict-monile`

## Project Overview

Mercury is a Django 5.1 QA testing and monitoring platform that orchestrates API test execution, reporting, and service monitoring. Test execution is handled by ceres TestExecutor with scheduled monitors via APScheduler and cron.

## Deployment

Deployment configuration lives under `deploy/mercury`:

```
deploy/
└── mercury/
    ├── .gitlab-ci.yml
    ├── Dockerfile
    ├── deploy.sh
    ├── k8s.yaml
    └── start_server.sh
```

GitLab uses `deploy/mercury/.gitlab-ci.yml` as its custom CI configuration path.

## Common Commands

### Run the development server
```bash
python3 manage.py runserver 0.0.0.0:8000
```

### Build frontend
```bash
cd mercury-frontend && npm install && npm run build
```

### Install dependencies
```bash
pip3 install -r requirements.txt
```

### Database Schema Changes
**Never use Django's `makemigrations` or `migrate` commands.** All database changes are maintained via hand-written SQL, provided to the user for manual execution in production.

### Ceres CLI

Manage testcases, testplans and perf scenarios from the shell without going through the web API:

```bash
# Testcases
python3 manage.py ceres case list --project sample --limit 20
python3 manage.py ceres case get 486 --output json
python3 manage.py ceres case create --project sample --name "foo" --url "{{host}}/x" --json-file payload.json
python3 manage.py ceres case update 486 --name "new name" --json-file patch.json
python3 manage.py ceres case delete 486
python3 manage.py ceres case run 486 --env Sample_prod

# Testplans
python3 manage.py ceres plan list --project sample
python3 manage.py ceres plan cases 3
python3 manage.py ceres plan add-cases 3 480 481 482
python3 manage.py ceres plan remove-cases 3 976 977
python3 manage.py ceres plan sync 3 --all
python3 manage.py ceres plan run 3 --env Sample_prod            # foreground, polls until done
python3 manage.py ceres plan run 3 --async                      # returns execution_id immediately
```

Every subcommand accepts `--output table|json`. Resources can be referenced by id or name. JSON payloads for `create`/`update` can come from `--json-file PATH`, `--json '{"k":"v"}'`, or `--stdin`. The CLI uses the ORM and `TestExecutor` directly — no login required.

### MCP Server (Claude Code Integration)

Mercury provides an MCP server that lets Claude directly operate test and production environments via natural language. Configured in `.mcp.json` at project root.

**Setup**: Create `.mcp.json` in the project root (gitignored), then restart Claude Code and approve the `mercury` MCP server.

macOS / Linux:
```json
{
  "mcpServers": {
    "mercury": {
      "command": "python3",
      "args": ["ceres/mcp_server.py"],
      "env": {
        "MERCURY_TEST_URL": "https://test-qa-mercury.aws.solab.ai",
        "MERCURY_PROD_URL": "https://prod-qa-mercury.aws.solab.ai"
      }
    }
  }
}
```

Windows — 把 `"command"` 改为 `"python"`。

**First use**: Tell Claude to login (e.g., "登录 test 环境，邮箱 xxx 密码 xxx"). JWT is cached in memory for 24h.

**Environments**: `nb-test`, `nb-prod`

**Available tools**:
- `login` — LDAP auth to any environment
- `project_list` / `project_sync` — list projects; export/import across environments
- `case_list` / `case_get` / `case_create` / `case_update` / `case_delete` / `case_run` — testcase CRUD + execution
- `folder_list` / `folder_tree` / `folder_create` / `folder_update` / `folder_delete` — folder management for grouping testcases
- `plan_list` / `plan_get` / `plan_create` / `plan_update` / `plan_cases` / `plan_add_cases` / `plan_remove_cases` / `plan_run` / `plan_sync` — testplan management
- `execution_list` / `execution_get` / `execution_case_results` — view execution reports
- `env_list` / `env_create` / `env_update` — environment variables
- `perf_plan_list` / `perf_plan_get` / `perf_plan_create` / `perf_plan_update` / `perf_plan_delete` — PerfPlan CRUD
- `perf_plan_cases_add` / `perf_plan_cases_delete` — attach/detach testcases (role='setup' vs 'transaction')
- `perf_plan_sync` — refresh case snapshots after editing referenced testcases
- `perf_plan_run` — trigger a load run (async, returns PerfRun)
- `perf_run_list` / `perf_run_get` / `perf_run_abort` — run history, live status, graceful abort. **Account pool / per-case data file uploads use curl, not MCP** (multipart over stdio is unreliable for the 1-50MB range)

**Examples**:
```
"在 prod 上跑全量回归"
"看一下 test 最近失败的执行，分析原因"
"把 test 的 sample 项目同步到 prod"
"创建一个 GET 用例，URL 是 {{host}}/api/health"
```

### Deployment
Tags must follow the pattern `[branch]-YYYYMMDD-v#` (e.g., `prod-20250101-v1`). Deployments are triggered manually in GitLab CI.

### Project Data Export / Import

Ceres supports full project data export and import via API, useful for syncing test cases between environments (e.g., test → prod).

**Export** — `GET /api/projects/{id}/export/`
Returns JSON containing all folders, testcases, envs, and testplans with their relationships. Uses `source_id` references for cross-linking.

**Import** — `POST /api/projects/{id}/import/`
Accepts the export JSON. **Overwrite mode**: clears all existing folders, testcases, envs, testplans in the target project, then recreates from import data. ID mappings are rebuilt automatically.

**Cross-environment sync workflow**:
```bash
# Export from test environment
curl -H "Authorization: Bearer $TOKEN" https://test-qa-mercury.aws.solab.ai/api/projects/1/export/ > export.json

# Import to prod environment
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d @export.json https://prod-qa-mercury.aws.solab.ai/api/projects/1/import/
```

## Architecture

### Django Apps

- **ceres** — Test case management platform with full CRUD, hierarchical folder organization, pre/post request scripting (Python), `{{variable}}` placeholder substitution, multipart file upload (S3), scheduled execution (APScheduler), in-process load testing via PerfPlan + TestExecutor reuse (replacing the older Goose/Rust pipeline). Uses soft-delete pattern (`is_deleted` flag).

### URL Routing

All API routes are mounted under `/api/`:
- `ceres` routes are defined in `ceres/urls.py`
- Health check: `GET /api/test/`

### Configuration

- **`mercury/env.json`** — Central config file containing environment flag (`ENV`), database credentials, Elasticsearch settings, S3 config, and external service connections. The `ENV` field (`test` or `prod`) drives all environment-specific behavior.
- **`mercury/settings.py`** — Reads `env.json` at startup.

### Test Execution Flow (Prediction example)

```
Cron (every 15 min) → curl /api/runtest/?env=test&shell_script=pridiction_runtest.sh&...
  → views.runtest() parses params, generates task_id="task-{collection}-{env}-{yyyymmdd-HHmmss}"
  → Thread(runtest_async) runs async:
    1. subprocess.run(['bash', 'pridiction_runtest.sh', task_id, env])
       → ceres TestExecutor
       → outputs JSON + HTML reports to templates/static/{task_id}.*
    2. Parse JSON report: count assertion pass rate, collect failed URLs and x-trace-ids
    3. If passrate < 100%, send Feishu notification
       - prod/prod_visit: auto-retry up to 2 times; test: no retry
    4. service.add_Report() → write to Elasticsearch (api_monitor index)
    5. service.store_Report() → upload HTML to S3 (qa/mercury/ prefix)
```

Report access: `GET /api/showreport/{id}` reads local templates/static/ first, falls back to S3.

### Ceres Execution Flow (testplan scheduled execution)

```
APScheduler (interval/cron trigger)
  → _execute_scheduled_task(task_id)
  → Check concurrency guard (skip if previous execution still running)
  → Load testplan cases with snapshots (to_executable())
  → Create ExecutionRecord (status='running')
  → Spawn thread: TestExecutor.execute_plan_async()
    → For each testcase:
       pre-script → resolve variables → HTTP request → assertions → post-script
       → Save ExecutionCaseResult, update counts in real-time
    → Final: update status, send notification, handle retry
```

### Ceres Load Testing (PerfPlan)

Load testing runs **in-process** inside the Mercury pod — no external binary, no codegen, no Rust/Goose. The driver (`ceres/engine/perf_driver.py`) reuses `TestExecutor.run_single_case` from functional testing, scheduling calls at a target arrival rate. This is a deliberate trade-off versus Goose/k6/JMeter: lower single-machine throughput ceiling (Python + thread pool → ~3-5k RPS on a sized pod) in exchange for using the exact same testcase definitions, pre/post scripts, and assertions as monitor tests.

DB schema lives in `scripts/mercury_mysql_schema.sql` (hand-rolled, `managed=False`).

#### Data Model

```
PerfPlan
├── project / env / name / description
├── target_rate (RPS) / duration_secs / max_vus
├── transactions JSON: [{name, weight, sort_order}]    — metadata only
├── account_data_file_s3_key  — optional per-VU account pool (CSV/JSON)
├── notify_feishu_webhook / notify_on_completion / notify_on_failure
└── soft-delete + timestamps

PerfPlanCase (junction)
├── perf_plan_id / testcase_id (FK to ceres_testcase)
├── role: 'setup' | 'transaction'
│      setup: runs once per VU at startup (sequential, shared VC within VU)
│      transaction: belongs to a transaction's case chain
├── transaction_name (matches PerfPlan.transactions[].name; '' for setup)
├── sort_order
├── data_file_s3_key + data_mode ('round_robin' | 'random' | 'sequential_once')
└── case_snapshot JSONB — same pattern as TestplanCase

PerfRun
├── perf_plan_id
├── target_rate / duration_secs / max_vus (snapshot of run params)
├── status: pending → running → completed | failed | setup_failed
│                            ↘ aborting → aborted
├── started_at / finished_at / last_heartbeat_at
├── summary_json — flushed every ~2s, shape:
│      { total_reqs, success_count, error_count, dropped_count,
│        active_vus, current_rps,
│        latency_ms: {p50, p95, p99, avg, min, max},
│        per_transaction: {<name>: {count, error_rate, p95_ms}} }
└── error_message
```

#### Runtime Flow

```
POST /api/perf-plans/{id}/run/
  → PerfRun row created (status='pending')
  → start_run_in_background(run_id) → daemon thread
    Phase 1: load plan structure (transactions, setup/load case lists, data sources)
    Phase 2: download data files from S3 (account pool + per-case data files)
    Phase 3: init VUs (max_vus instances):
       - each VU binds to one account row (round-robin if rows < VUs)
       - each VU runs setup cases sequentially against its private VC
       - failed setup → VU dropped; >50% failure → run marked 'setup_failed'
       - on success, snapshot post-setup runtime_vars as VU baseline
    Phase 4: load loop @ target_rate
       - every 1/rate seconds, weighted-pick a transaction
       - acquire idle VU (or record dropped_count if all busy)
       - VU runs transaction cases sequentially in a fresh VC seeded from
         (env vars + account row + baseline post-setup vars)
       - data file picked one row per case fire (if bound)
       - setVar within transaction chains across cases; reset between transactions
    Phase 5: flush summary_json every ~2s; poll status='aborting' every ~1s
    Phase 6: on duration end or abort, wait for in-flight to finish,
             set status='completed' or 'aborted', flush final summary
```

#### Key Concepts

- **VU isolation**: each VU has its own VariableContext. Setup mutations persist within the VU (e.g., login writes `token`). Transaction cases get a fresh VC clone per transaction — intra-transaction setVar chains, but cross-transaction state never leaks. This avoids races without sacrificing chained-case workflows.
- **Saturation policy**: when all VUs are busy, the tick is `dropped` and the schedule continues — target rate stays honest at the metric level. The actual rate falls below target until either VUs free up or max_vus is raised.
- **Abort**: DB-driven. UI/API sets `status='aborting'`; the driver polls every ~1s and transitions to `aborted` after in-flight requests finish. Works across pod restarts because state is in DB.
- **Multi-instance reserved**: `last_heartbeat_at` field is reserved for future multi-pod claim/orphan-detection. v1 is single-pod; the schema is forward-compatible.

#### Account Pool & Data Files

CSV (header row) or JSON (array of objects). Uploaded via multipart, stored at `qa/mercury/perf_data/{plan_id}/`:

```bash
# Account pool — per-VU binding (each VU = different test user)
curl -X POST /api/perf-plans/{id}/upload-account-pool/ \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@accounts.csv"
# Per-case data file — per-request row picking
curl -X POST /api/perf-plans/{id}/cases/{plan_case_id}/upload-data/ \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@articles.csv" -F "mode=random"
```

Max 50 MB; allowed extensions `.csv .json .tsv`. Driver loads the whole file into memory at run start.

#### API Surface

- `GET/POST /api/perf-plans/` — plan CRUD (list, create)
- `GET/PATCH/DELETE /api/perf-plans/{id}/` — get, update, soft-delete
- `GET/POST/PUT/DELETE /api/perf-plans/{id}/cases/` — manage PerfPlanCase rows
- `POST /api/perf-plans/{id}/sync/` — refresh snapshots
- `POST /api/perf-plans/{id}/run/` — trigger run, returns PerfRun
- `GET /api/perf-plans/{id}/runs/` — list runs for this plan
- `POST /api/perf-plans/{id}/upload-account-pool/` — multipart
- `POST /api/perf-plans/{id}/cases/{plan_case_id}/upload-data/` — multipart
- `GET /api/perf-runs/{id}/` — run detail with summary_json
- `POST /api/perf-runs/{id}/abort/` — signal abort
- `GET /api/perf-runs/{id}/metrics/` — OpenMetrics for Prometheus (no auth)

#### Debugging

- `summary_json` is the source of truth for live + final state. Poll the run detail endpoint.
- If `status='failed'`, `error_message` has the top-level exception. For deeper traces grep the Mercury container log for `perf-run-{id}` thread name.
- If `status='setup_failed'`, at least 50% of VU setup chains failed. Most common cause: bad credentials in account pool, or a setup case that depends on something not yet provisioned.
- If `dropped_count` is high, VUs are saturated. Raise `max_vus` or accept that target rate exceeds backend capacity.

### External Dependencies

- **PostgreSQL** — Application data (via psycopg)
- **Elasticsearch** — Test report indexing and latency monitoring queries
- **AWS S3** — Report file storage and test data files
- **Feishu** — Webhook notifications for test results

### Deployment

- Docker (Ubuntu 22.04 base with Python 3, Node.js 20, lcov 2.3)
- Kubernetes (namespace: `monitor`, port 8000, health probe at `/api/test`)
- GitLab CI with tag-based deployments (`test-202*` / `prod-202*`)
- Cron jobs configured in `start_server.sh` for scheduled monitoring (prod only)

### Key Patterns

- Async operations use `threading.Thread` (not Celery/task queues)
- Report IDs follow: `task-{collection}-{env}-{timestamp}`
- `ceres` models use JSON fields for flexible parameter storage
- Scheduled tasks use APScheduler with concurrency guard (skip if previous still running)
- Frontend detects new deployments on route change (script hash comparison)

## Ceres Script Engine

### Script Language
Scripts use **Python** syntax. Available in Pre-request and Post-response tabs.

### mercury API (available as `mercury` in scripts)

| Method | Description |
|--------|-------------|
| `mercury.getVar(name)` | Get runtime variable (set by previous cases) |
| `mercury.setVar(name, value)` | Set runtime variable (available in subsequent cases) |
| `mercury.getEnvVar(name)` | Get environment variable |
| `mercury.getEnvName()` | Get current environment name |
| `mercury.skip(reason)` | Pre-request only. Mark the current case as **skipped** (not pass/fail/error). Use when a precondition is missing — e.g. `if not mercury.getVar('reportId'): mercury.skip('no reportId')`. Skipped cases don't count toward pass rate denominator and don't trigger failure notifications. |

### Request/Response Objects

**Pre-request** (`req`): `req.url`, `req.method`, `req.headers` (dict, read/write/delete), `req.body`
**Post-response** (`res`): `res.status`, `res.body` (supports dot access), `res.headers`

### Available Modules
`json`, `base64`, and Python builtins (`str`, `int`, `len`, `range`, `sorted`, `map`, `filter`, etc.)

### Assertion Operators
`eq` `neq` `gt` `gte` `lt` `lte` `in` `nin` `contains` `notContains` `isNull` `isNotNull` `isEmpty` `isNotEmpty` `matches`

### Assertion Field Paths
- `res.status` — HTTP status code
- `res.responseTime` — Response duration in ms
- `res.body.data.id` — Nested field access
- `res.body.items[0].name` — Array index
- `res.body.items[*].status` — Wildcard (assert all items)
- `res.body.data.length` — Array/string length
- `res.headers.x-trace-id` — Response header (case-insensitive)

## APIs Excluded from Monitoring Coverage

Some endpoints are intentionally out-of-scope for ceres testcases — even when `coverage_check` surfaces them as uncovered, do **not** propose adding testcases for them.

| Pattern | Reason |
|---------|--------|
| `/api/news/link2Insight*` (incl. `unreadCount`) | Out-of-scope per product decision |

When summarizing coverage gaps, filter these out silently before presenting the list.

## Test Case Assertion Design Principles

When writing or improving test case assertions, follow these principles to ensure assertions catch real regressions rather than just verifying the API is alive.

### Core Principle: Assert What the Frontend Uses

Assertions must be driven by **how the frontend actually consumes the API response**, not just whether the API returns 200. Read the frontend code (service files, providers, models) to identify which fields are critical for rendering, navigation, and state management.

### Assertion Depth Levels (from worst to best)

1. **No assertions** — only catches connection errors. Never acceptable for non-setup cases.
2. **Status-only** (`res.status eq 200`) — catches server errors but misses empty/malformed responses.
3. **Basic existence** (`res.body.items isNotNull`) — catches null responses but misses missing nested fields.
4. **Deep field validation** (`res.body.items[*].title isNotEmpty`) — catches structural regressions at the field level the frontend depends on. **This is the target level.**

### Use `[*]` Wildcard for Array Assertions

Prefer `items[*].field` over `items[0].field`. The wildcard checks **every element** in the array, catching cases where some items have missing fields while the first item happens to be fine.

```
# Bad — only checks the first item
res.body.items[0].title isNotNull

# Good — checks ALL items
res.body.items[*].title isNotNull
```

### Assertion Design Checklist

For each API endpoint:

1. **Identify the frontend service file** that calls this endpoint (e.g., `news.dart`, `prediction.dart`)
2. **Trace field usage** through service → provider → model → UI widget
3. **Assert on fields the frontend reads**, especially:
   - Navigation/routing fields: IDs (`newsId`, `storyId`, `userId`, `eventId`)
   - Display content: `title`, `summary`, `content`, `displayName`
   - Media: `media[*].url`, `thumbnail`, `avatarUrl`
   - Social counts: `likeCount`, `commentCount`, `bangCount`
   - User state: `liked`, `saved`, `isRead`, `subscribed`
   - Nested objects the frontend destructures: `user.userId`, `source.name`, `options[*].optionKey`
4. **Don't assert on optional/nullable fields** that the frontend handles gracefully with fallbacks
5. **Use appropriate operators**:
   - `isNotNull` for fields that must exist (can be empty string or 0)
   - `isNotEmpty` for fields that must have content (strings, arrays)
   - `gt 0` for counts and lengths
   - `eq` for known exact values (status codes, enum values)

### Examples by API Type

**List endpoint** (e.g., `/api/dis/comment/list/{threadId}`):
```
res.status eq 200
res.body.items.length gt 0
res.body.items[*].id isNotNull
res.body.items[*].content isNotEmpty
res.body.items[*].user isNotNull
res.body.items[*].user.userId isNotNull
res.body.items[*].user.displayName isNotNull
res.body.items[*].createdAt isNotNull
```

**Detail endpoint** (e.g., `/api/prediction/event/{id}`):
```
res.status eq 200
res.body.eventId isNotEmpty
res.body.title isNotEmpty
res.body.options isNotNull
res.body.options.length gt 0
res.body.options[*].optionKey isNotEmpty
res.body.options[*].optionText isNotEmpty
res.body.options[*].probability isNotNull
res.body.voteCount isNotNull
```

**Configuration endpoint** (e.g., `/api/user/application/configuration`):
```
res.status eq 200
res.body.currentUser isNotNull
res.body.currentUser.userId isNotNull
res.body.currentUser.displayName isNotNull
res.body.subscribed isNotNull
res.body.userRequestLimit isNotNull
res.body.userRequestLimit.bang isNotNull
res.body.features isNotNull
```

**SSE/streaming endpoint** (e.g., `/api/v1/recommend/bang/bang`):
```
res.status eq 200
res.body isNotEmpty
```

**Write endpoint** (e.g., `POST /api/dis/comment/post`):
```
res.status eq 200
res.body.id isNotEmpty
```

**Fire-and-forget endpoint** (e.g., `POST /api/dis/opinion/post`):
```
res.status eq 200
```

### Workflow for Improving Assertions

1. Get the latest execution results to see current assertion coverage
2. Read frontend service/provider/model files to map API → field usage
3. Update assertions via MCP `case_update` with deep field checks using `[*]` wildcards
4. Run the testplan and verify all pass
5. Fix any failures (distinguish assertion issues from backend issues)
6. Sync to prod via `project_sync` + `plan_sync`
