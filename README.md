# Mercury

QA testing and monitoring platform for API test execution, reporting, and service monitoring.

## Features

- **Test Case Management** — Hierarchical folder organization, pre/post request scripting (Python), `{{variable}}` placeholder substitution, multipart file upload
- **Test Plans** — Organize test cases into executable plans with environment selection, retry logic, and Feishu notifications
- **Scheduled Execution** — APScheduler-based cron and interval triggers with concurrency guard
- **Execution Reports** — Real-time progress tracking, pass/fail/error stats, request/response headers display
- **Environment Management** — Multiple environments with variable sets, bulk edit mode, copy/duplicate
- **Performance Testing** — Goose-based load testing with codegen, build, and download workflow
- **Service Monitors** — Latency monitoring, morning brew checks, push record verification, LLM story rank alerts
- **Project Data Export/Import** — Full project sync between environments via API

## Tech Stack

- **Backend**: Django 5.1, Python 3
- **Frontend**: Vue 3, Ant Design Vue, Vite, ECharts
- **Database**: MySQL
- **Search**: Elasticsearch
- **Storage**: AWS S3
- **CI/CD**: GitLab CI, Docker, Kubernetes
- **Test Runner**: Ceres TestExecutor

## Quick Start

```bash
# Install dependencies
pip3 install -r requirements.txt
cd mercury-frontend && npm install && npm run build && cd ..

# Run development server
python3 manage.py runserver 0.0.0.0:8000
```

## Deployment

Deployment configuration lives under `deploy/mercury`:

```
deploy/mercury/
├── Dockerfile
├── deploy.sh
├── k8s.yaml
└── start_server.sh
```

Tag-based deployment: `prod-YYYYMMDD-vN` / `test-YYYYMMDD-vN`

## API

- `GET /api/test/` — Health check
- `GET /api/projects/{id}/export/` — Export project data
- `POST /api/projects/{id}/import/` — Import project data
- `POST /api/testcases/{id}/run/` — Run single testcase
- `POST /api/testplans/{id}/run/` — Run test plan

See `CLAUDE.md` for detailed architecture and development guide.
