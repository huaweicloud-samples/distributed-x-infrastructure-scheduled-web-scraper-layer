# distributed-x-infrastructure-scheduled-web-scraper-layer

> [中文](README.cn.md)

[![License](https://img.shields.io/badge/License-MIT%20No%20Attribution-blue.svg)](LICENSE)
[![Huawei Cloud](https://img.shields.io/badge/Huawei%20Cloud-FunctionGraph-red.svg)](https://support.huaweicloud.com/intl/en-us/)
[![Build Status](https://img.shields.io/badge/Build-Passing-brightgreen.svg)](#)

> A scheduled page-snapshot function on Huawei Cloud

---

## 1. Overview

A timer trigger invokes one FunctionGraph function on a Quartz-style cron expression. Each invocation fetches a configured page over HTTP, writes the response body as a dated snapshot object into a private Object Storage Service (OBS) bucket, and emits structured JSON log lines to Log Tank Service (LTS). The function source and its declared HTTP library ship in one deployment archive, and the runtime reaches the bucket with temporary credentials supplied by the invocation context.

Built for engineers who want a compact, reproducible reference for a scheduled serverless collection job on Huawei Cloud: how a TIMER trigger is declared, how a function obtains object-storage access without long-lived keys, and how a deterministic object key keeps snapshots sortable.

### Core Capabilities

- A TIMER trigger driven by a configurable Quartz cron expression, with a switch to disable it.
- One Python 3.9 FunctionGraph function (`index.handler`), 512 MB / 600 s, packaged with its declared library.
- Deterministic, sortable object keys `snapshots/YYYY/MM/DD/HHMMSS-<hash>.html` in a private OBS bucket.
- Structured JSON logs carrying service name, trace id, trigger kind, byte count and object key.
- Event decoding for TIMER, direct and API Gateway-shaped invocations, plus a per-invocation target override.
- A lightweight verification profile that omits the scheduled trigger while keeping the full fetch-and-store path.
- Local end-to-end checks: 26 assertions covering configuration, event decoding, fetch fallback, key generation, bucket writes, logging and the deployment archive, without contacting the cloud.

---

## 2. Table of Contents

- [1. Overview](#1-overview)
- [2. Table of Contents](#2-table-of-contents)
- [3. Architecture](#3-architecture)
- [4. Highlights](#4-highlights)
- [5. Cloud Services Used](#5-cloud-services-used)
- [6. Prerequisites](#6-prerequisites)
- [7. Quick Start](#7-quick-start)
- [8. Step-by-Step Deployment](#8-step-by-step-deployment)
- [9. Usage / Verification](#9-usage--verification)
- [10. Cleanup](#10-cleanup)
- [11. Detailed Explanation](#11-detailed-explanation)
- [12. Dependencies](#12-dependencies)
- [13. FAQ / Troubleshooting](#13-faq--troubleshooting)
- [14. Contributing](#14-contributing)
- [15. License](#15-license)
- [16. Contact / Maintainers](#16-contact--maintainers)

---

## 3. Architecture

> A scheduled trigger fires one function; the function reads a page, stores a snapshot and emits logs.

```
                        ┌────────────────────┐
                        │   TIMER trigger    │
                        │  Quartz cron rule  │
                        └──────────┬─────────┘
                                   │ ① cron schedule fires
                                   ▼
┌────────────────────────────────────────────────────────────────────┐
│        FunctionGraph function (Python 3.9 / 512 MB / 600 s)        │
│      index.handler - source and libraries in one function.zip      │
└──────────┬───────────────────────┬───────────────────────┬─────────┘
           │                       │                       │
           ▼                       ▼                       ▼
┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐
│   ② Target page    │  │    ③ OBS bucket    │  │  ④ LTS log group   │
│   HTTP GET body    │  │  dated object key  │  │   JSON log lines   │
└────────────────────┘  └────────────────────┘  └────────────────────┘
```

**Lightweight verification profile** (`-var enable_timer=false`): the TIMER trigger is not created. The function, private bucket, log group and log stream remain unchanged, so the function is invoked directly.

```
                        ┌────────────────────┐
                        │ Direct invocation  │
                        │  CLI / test event  │
                        └──────────┬─────────┘
                                   │ ① direct invocation
                                   ▼
┌────────────────────────────────────────────────────────────────────┐
│        FunctionGraph function (Python 3.9 / 512 MB / 600 s)        │
│      index.handler - source and libraries in one function.zip      │
└──────────┬───────────────────────┬───────────────────────┬─────────┘
           │                       │                       │
           ▼                       ▼                       ▼
┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐
│   ② Target page    │  │    ③ OBS bucket    │  │  ④ LTS log group   │
│   HTTP GET body    │  │  dated object key  │  │   JSON log lines   │
└────────────────────┘  └────────────────────┘  └────────────────────┘
```

Step ① is the scheduled trigger firing on its cron expression (or a direct invocation in the lightweight profile); ② is the outbound HTTP GET that reads the configured page; ③ writes the snapshot object to the private bucket with the invocation's temporary credentials; ④ emits structured JSON log lines to LTS. Steps ②, ③ and ④ are identical in both profiles.

Component responsibilities, deployment package layout, temporary credentials and configuration are documented in [`docs/architecture.md`](docs/architecture.md).

**Key components**:

- **FunctionGraph TIMER trigger**: `type = "TIMER"`, `schedule_type = "Cron"`, driven by a six-field Quartz expression; omitted when `enable_timer=false`.
- **FunctionGraph**: one Python 3.9 function, 512 MB / 600 s, entry point `index.handler`, LTS logging enabled.
- **Object Storage Service (OBS)**: a private bucket holding `text/html` snapshot objects under a date-partitioned key.
- **Log Tank Service (LTS)**: one group and one stream, 7-day retention by default, collecting structured log lines from standard output.
- **Identity and Access Management (IAM)**: a cloud service agency delegated to `op_svc_cff` with `OBS OperateAccess`.

---

## 4. Highlights

- **One archive, no external mount**: function modules and the declared HTTP library are assembled into a single `build/function.zip` by `scripts/package-function.sh`, so the function has no external directory dependency at runtime.
- **No long-lived keys in the package**: object writes use temporary credentials read from the invocation context; deployment keys stay on the deploy machine.
- **Deterministic object keys**: the key combines a UTC timestamp with a short hash of the target address, making snapshots sortable and reproducible.
- **Graceful fetch fallback**: the bundled HTTP client is preferred; a standard-library fallback keeps the handler importable in a minimal environment.
- **Two verification profiles**: keep the scheduled trigger for automatic runs, or omit it and invoke the function directly for a one-off check.
- **Local end-to-end checks**: 26 assertions exercise the full handler path with injected collaborators, without any cloud connection or outbound network access.

---

## 5. Cloud Services Used

| Service | Purpose | Notes |
|---|---|---|
| FunctionGraph | Snapshot function and TIMER trigger | Python 3.9, 512 MB, 600 s; one function + one trigger |
| Object Storage Service (OBS) | Private bucket for snapshot objects | `acl = "private"`, globally unique bucket name |
| Log Tank Service (LTS) | Structured application logs | One group + one stream, 7-day retention |
| Identity and Access Management (IAM) | Runtime agency | `op_svc_cff` cloud service agency with `OBS OperateAccess` |

> No VPC, NAT gateway, Elastic IP, public load balancer or public inbound endpoint is created. All services are created with the Terraform in this repository. To release them, see [Section 10 "Cleanup"](#10-cleanup).

---

## 6. Prerequisites

| Item | Requirement | Description |
|---|---|---|
| **Account** | Huawei Cloud account with real-name verification | Personal or enterprise account |
| **Permissions** | IAM **Tenant Administrator** or equivalent | To create FunctionGraph, OBS, LTS and an agency |
| **Region** | Recommended `cn-north-4` | Runtime and bucket availability differ across regions |
| **Terraform** | `>= 1.5.0` | IaC deployment tool |
| **huaweicloud Provider** | `>= 1.97.0` | Huawei Cloud Terraform Provider |
| **Python** | `>= 3.8` | Used by the packaging script and the local checks |
| **Bash** | Git Bash / WSL / Linux | Runs `scripts/package-function.sh` |
| **Access keys** | Obtain an Access Key and Secret Access Key from the Huawei Cloud "My Credentials" page and provide them through the shell environment | Do not write credentials into any code or configuration file |

---

## 7. Quick Start

### One-click Deployment (Recommended)

```bash
# 1. Clone this repository
git clone <repo-https-url> distributed-x-infrastructure-scheduled-web-scraper-layer
cd distributed-x-infrastructure-scheduled-web-scraper-layer

# 2. Provide access keys through the shell environment (see Section 6)
export HW_ACCESS_KEY="<your-access-key>"
export HW_SECRET_KEY="<your-secret-key>"

# 3. Build the deployment archive and deploy
bash scripts/package-function.sh
cd infra
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars: set obs_bucket_name and target_url
terraform init
terraform plan
terraform apply -auto-approve
```

> **Deployment time**: a few minutes; the function, bucket, log resources and agency are created together.
> **Full steps with expected output**: see [Section 8](#8-step-by-step-deployment) and [`docs/deployment-guide.md`](docs/deployment-guide.md).

---

## 8. Step-by-Step Deployment

### Step 1: Build the deployment archive

```bash
bash scripts/package-function.sh
```

**Expected output**: `archive=.../build/function.zip files=<N> bytes=<N>` followed by `Done: .../build/function.zip`.

### Step 2: Initialize the working directory

```bash
cd infra
terraform init
```

**Expected output**: `Terraform has been successfully initialized!`

### Step 3: Preview resource changes

```bash
terraform validate
terraform plan
```

**Expected output**: `Success! The configuration is valid.` followed by `Plan: N to add, 0 to change, 0 to destroy.`

### Step 4: Apply the deployment

```bash
terraform apply -auto-approve
```

**Expected output**: `Apply complete! Resources: N added, 0 changed, 0 destroyed.`

### Step 5: Record key outputs

```bash
terraform output
```

**Expected output**: lists `bucket_name`, `function_name`, `function_urn`, `timer_schedule`, `timer_id`, `lts_group_id`, `lts_stream_id` and `invoke_command`.

---

## 9. Usage / Verification

> **Verification notice**: after deployment, follow this section to verify that the business functionality works before considering the delivery complete. The local end-to-end checks below have been executed during development; the cloud commands require a deployed stack.

### Verification 1: Local end-to-end checks (executed during development)

```bash
bash scripts/package-function.sh
python scripts/local-e2e/test_e2e.py
```

**Expected output**:
```
=== Summary: 26 passed, 0 failed ===
```

The checks cover configuration defaults and overrides, event kind decoding, target override from the event or a JSON body, trace ids, injected and fallback fetching, object key shape and URL sensitivity, both bucket-client write interfaces, structured logging with level filtering, handler happy/manual/override/failure paths, digest stability and the contents of the deployment archive. All collaborators are injected; no cloud service or outbound network is contacted.

### Verification 2: Invoke the function directly (requires a deployed stack)

```bash
hcloud fgs invoke --function-name "$(terraform output -raw function_name)" --body '{}'
```

**Expected result**: `statusCode = 200` with `ok: true`, plus `trigger`, `target`, `http_status`, `bytes`, `sha256`, `bucket`, `key`, `object_status` and `trace_id`.

A per-invocation override is also accepted:

```bash
hcloud fgs invoke --function-name "$(terraform output -raw function_name)" \
  --body '{"target_url": "https://www.example.com", "x-trace-id": "check-001"}'
```

### Verification 3: Check the snapshot object (requires a deployed stack)

Open the bucket named by `terraform output -raw bucket_name` and look under the configured `result_prefix`. Keys look like `snapshots/2026/11/09/065900-1a2b3c4d5e6f.html`, with content type `text/html; charset=utf-8` and the fetched page as the body.

### Verification 4: Check structured logs (requires a deployed stack)

Open the stream named by `terraform output -raw lts_stream_id`. Each invocation produces `invocation started` and `snapshot stored` JSON lines with `service`, `trace_id`, `level` and `message`; the success line also carries `key` and `bytes`. A fetch failure produces an `ERROR` line and a 502 response.

### Verification 5: Lightweight profile without a scheduled trigger

```bash
terraform apply -auto-approve -var enable_timer=false
```

Then repeat Verification 2. **Expected result**: the same handler response and log lines; `timer_id` is empty and no trigger is created.

---

## 10. Cleanup

```bash
cd infra
terraform destroy -auto-approve
```

**Expected output**: `Destroy complete! Resources: N destroyed.`

> **Avoid resource residue**:
> - `terraform destroy` only releases resources tracked in the Terraform state;
> - objects or triggers created directly in the console must be released manually;
> - the result bucket uses `force_destroy = true`, so archived snapshots are removed with the bucket.

---

## 11. Detailed Explanation

### Workflow

The TIMER trigger (or a direct invocation) enters `index.handler`. The event adapter normalises the trigger kind, resolves an optional target override and a trace id. The fetcher performs an HTTP GET using the bundled library, falling back to the standard library when it is unavailable. A deterministic key is derived from the UTC time and a short hash of the target address. The storage layer builds an OBS client from the invocation's temporary credentials and writes the body, then the logger emits structured JSON lines and the handler returns a summary containing the digest, byte count and object key. Uncaught fetch errors become a structured 502 response.

### Modules

| Module | Source | Responsibility |
|---|---|---|
| Entry point | `src/functions/src/index.py` | `create_handler(deps)` with injectable config, fetch, client factory, clock and log sink; module-level `handler` |
| Configuration | `src/functions/src/config.py` | `Config` dataclass and `load_config()` with blank-value defaults |
| Event adapter | `src/functions/src/events.py` | `event_kind()`, `target_override()`, `trace_id()` |
| Fetcher | `src/functions/src/fetcher.py` | `fetch()` with bundled-client preference, standard-library fallback and opener injection |
| Storage | `src/functions/src/storage.py` | `result_key()`, `make_client()`, `put_snapshot()` |
| Observability | `src/functions/src/observability.py` | Structured JSON logger with level filtering and injectable sink |

### Configuration Items

| Variable | Default | Description |
|---|---|---|
| `region` | `cn-north-4` | Deployment region; also used to derive the OBS endpoint |
| `app_name` | `scheduled-web-scraper` | Prefix for every resource name |
| `obs_bucket_name` | derived from app name and region | Globally unique private bucket name |
| `function_runtime` | `Python3.9` | FunctionGraph runtime |
| `function_memory_size` | `512` | Function memory in MB |
| `function_timeout` | `600` | Function timeout in seconds |
| `enable_timer` | `true` | Create the TIMER trigger |
| `timer_schedule` | `0 59 6,10,14,18 * * ?` | Six-field Quartz cron expression |
| `timer_schedule_type` | `Cron` | Trigger schedule type |
| `target_url` | `https://www.example.com` | Page fetched by each invocation |
| `result_prefix` | `snapshots` | Object key prefix |
| `lts_ttl_in_days` | `7` | Log retention in days |
| `service_name` / `log_level` | `scheduled-web-scraper` / `INFO` | Structured log service name and minimum level |

See [`docs/deployment-guide.md`](docs/deployment-guide.md) for the full list and per-step details.

### Event Shapes and Response

| Input | Recognised as | Notes |
|---|---|---|
| `{"trigger_type":"TIMER", ...}` | `TIMER` | Scheduled trigger |
| `{"schedule_time":"..."}` or `{"type":"timer"}` | `TIMER` | Platform timer variants |
| `{"httpMethod":"GET", ...}` | `APIG` | Gateway-shaped event |
| `{}` | `MANUAL` | Direct CLI / test invocation |
| `{"target_url":"..."}` or a JSON body with `url` / `target` | overrides the configured page | Per-invocation only |

Success returns `{"statusCode": 200, "body": {...}, "isBase64Encoded": false}`; a fetch failure returns `502` with `{"ok": false, "error": "fetch_failed", "detail": "..."}`.

---

## 12. Dependencies

| Name | Version | Purpose |
|---|---|---|
| Terraform | `>= 1.5.0` | IaC orchestration |
| huaweicloud Provider | `>= 1.97.0` | Huawei Cloud resources |
| Python | `>= 3.8` | Packaging script and local checks; `Python3.9` function runtime |
| `requests` | `2.31.0` | HTTP client bundled into the deployment archive |
| OBS Python SDK | provided by the FunctionGraph runtime | Bucket client built from invocation credentials |

---

## 13. FAQ / Troubleshooting

### Q1: What if deployment reports "insufficient permissions"?

**A**: Confirm the account has IAM **Tenant Administrator**, or at least permissions for FunctionGraph, OBS, LTS and creating an agency.

### Q2: `terraform apply` fails with `FSS.1501 The delegate not exist`. Why?

**A**: IAM agency propagation is asynchronous. Wait about a minute and re-apply; the configuration already declares `depends_on` on the agency.

### Q3: The bucket name is rejected. Why?

**A**: Bucket names are globally unique. Set `obs_bucket_name` explicitly to a name of your own.

### Q4: The timer never fires. What should I check?

**A**: `timer_schedule` must be a six-field Quartz expression (second minute hour day month weekday), with `?` in the weekday field. Check `terraform output timer_schedule` and `timer_id`.

### Q5: The function returns 502 `fetch_failed`. What should I do?

**A**: Check `target_url`, outbound connectivity and the timeout. The `fetch failed` log line records the exception type. The handler always falls back to the standard-library client when the bundled library is unavailable.

### Q6: Objects are not written, although the fetch succeeded. Why?

**A**: The bucket client needs the full temporary credential triple from the invocation context. Verify the `op_svc_cff` agency carries `OBS OperateAccess` and that the function's log configuration is active.

### Troubleshooting Checklist

| Symptom | Possible Cause | Troubleshooting |
|---|---|---|
| `FSS.1009 Invalid function UserData` | Empty environment variable | The configuration filters empty values before encoding |
| Missing deployment package error | Packaging step skipped | Run `bash scripts/package-function.sh` before `terraform plan` |
| `files=<N>` but no third-party library in the zip | Local library install unavailable | Re-run packaging with network access; the handler falls back to the standard library meanwhile |
| No log lines in the stream | LTS binding not active | Confirm `enable_lts_log = true` and the group / stream ids |

---

## 14. Contributing

Issues and PRs are welcome. Please follow this process:

1. **Issue**: describe the problem or suggestion with reproduction commands, expected and actual output, and screenshots.
2. **PR**: create a feature branch from `main`; run `terraform fmt -check`, `terraform validate`, `bash scripts/package-function.sh` and `python scripts/local-e2e/test_e2e.py` before submitting.
3. **Code Review**: merged after review by **[@<github-username>](https://github.com/<github-username>)**.

See `CONTRIBUTING.md` for details.

---

## 15. License

This reference architecture is released under the **MIT No Attribution** license. See the [`LICENSE`](LICENSE) file at the repository root for details.

```
MIT No Attribution

Copyright (c) Huawei Cloud

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software... (no attribution required)
```

---

## 16. Contact / Maintainers

| Item | Content |
|---|---|
| **Creator** | [@<github-username>](https://github.com/<github-username>) |
| **Maintainer** | [@<github-username>](https://github.com/<github-username>) |
| **Contact** | GitHub Issues / PR (see [Section 14](#14-contributing)) |
