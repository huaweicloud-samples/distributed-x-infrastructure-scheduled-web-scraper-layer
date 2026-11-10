# distributed-x-infrastructure-scheduled-web-scraper-layer

> [English](README.md)

[![License](https://img.shields.io/badge/License-MIT%20No%20Attribution-blue.svg)](LICENSE)
[![Huawei Cloud](https://img.shields.io/badge/Huawei%20Cloud-FunctionGraph-red.svg)](https://support.huaweicloud.com/intl/en-us/)
[![Build Status](https://img.shields.io/badge/Build-Passing-brightgreen.svg)](#)

> 华为云上的定时网页快照函数

---

## 1. 概述

定时触发器按 Quartz 风格 cron 表达式调用一个函数工作流（FunctionGraph）函数。每次执行向配置的目标页面发起 HTTP GET，把响应正文按可排序的对象键写入私有对象存储服务（OBS）桶，并向云日志服务（LTS）输出结构化 JSON 日志。函数源码与声明的 HTTP 库打进同一个部署归档；运行时凭据来自调用上下文下发的临时凭据，部署包内不保存长期密钥。

适用于希望在华为云上获得一份紧凑、可复现的「定时无服务器采集任务」参考实现的工程师：如何声明 TIMER 触发器、函数如何在不持有长期密钥的前提下获得对象存储访问能力、以及确定性对象键如何让快照保持可排序。

### 核心能力

- 由可配置 Quartz cron 表达式驱动的 TIMER 触发器，并可一键关闭。
- 一个 Python 3.9 的 FunctionGraph 函数（`index.handler`），512 MB / 600 s，与声明的库一起打包。
- 确定性、可排序的对象键 `snapshots/YYYY/MM/DD/HHMMSS-<哈希>.html`，落在私有 OBS 桶中。
- 结构化 JSON 日志，携带服务名、链路标识、触发类型、字节数与对象键。
- 事件归一支持 TIMER、直接调用与 API 网关形态，并允许单次调用覆盖目标地址。
- 轻量验证档：不创建定时触发器，保留完整的抓取与写桶链路。
- 本地端到端检查：26 项断言覆盖配置、事件解码、抓取回退、对象键生成、写桶、日志与部署归档，全程不连接云端。

---

## 2. 目录

- [1. 概述](#1-概述)
- [2. 目录](#2-目录)
- [3. 架构](#3-架构)
- [4. 方案亮点](#4-方案亮点)
- [5. 涉及云服务](#5-涉及云服务)
- [6. 前置条件](#6-前置条件)
- [7. 快速开始](#7-快速开始)
- [8. 分步部署](#8-分步部署)
- [9. 使用方法 / 验证](#9-使用方法--验证)
- [10. 清理资源](#10-清理资源)
- [11. 详细说明](#11-详细说明)
- [12. 依赖](#12-依赖)
- [13. FAQ / 故障排除](#13-faq--故障排除)
- [14. 贡献指南](#14-贡献指南)
- [15. 许可证](#15-许可证)
- [16. 联系方式 / 维护者](#16-联系方式--维护者)

---

## 3. 架构

> 定时触发器发起一次调用；函数读取页面、写入快照并输出日志。

```
                        ┌────────────────────┐
                        │  TIMER 定时触发器  │
                        │  Quartz cron 规则  │
                        └──────────┬─────────┘
                                   │ ① 按 cron 表达式触发
                                   ▼
┌────────────────────────────────────────────────────────────────────┐
│         FunctionGraph 函数（Python 3.9 · 512 MB · 600 s）          │
│      index.handler · 源码与第三方库同包（单个 function.zip）       │
└──────────┬───────────────────────┬───────────────────────┬─────────┘
           │                       │                       │
           ▼                       ▼                       ▼
┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐
│     ② 目标页面     │  │    ③ OBS 私有桶    │  │    ④ LTS 日志组    │
│  HTTP GET 取正文   │  │   按日期的对象键   │  │   结构化 JSON 行   │
└────────────────────┘  └────────────────────┘  └────────────────────┘
```

**轻量验证档**（`-var enable_timer=false`）：不创建 TIMER 触发器。函数、私有桶、日志组与日志流保持不变，可直接调用函数完成验证。

```
                        ┌────────────────────┐
                        │    直接调用函数    │
                        │   CLI / 测试事件   │
                        └──────────┬─────────┘
                                   │ ① CLI / 测试事件直接调用
                                   ▼
┌────────────────────────────────────────────────────────────────────┐
│         FunctionGraph 函数（Python 3.9 · 512 MB · 600 s）          │
│      index.handler · 源码与第三方库同包（单个 function.zip）       │
└──────────┬───────────────────────┬───────────────────────┬─────────┘
           │                       │                       │
           ▼                       ▼                       ▼
┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐
│     ② 目标页面     │  │    ③ OBS 私有桶    │  │    ④ LTS 日志组    │
│  HTTP GET 取正文   │  │   按日期的对象键   │  │   结构化 JSON 行   │
└────────────────────┘  └────────────────────┘  └────────────────────┘
```

步骤 ① 为定时触发器按 cron 表达式触发（轻量档为直接调用）；② 为出站 HTTP GET 读取配置页面；③ 用调用上下文的临时凭据把快照对象写入私有桶；④ 向 LTS 输出结构化 JSON 日志行。两档中的 ②、③、④ 完全一致。

组件职责、部署包形态、临时凭据与配置对应关系见 [`docs/architecture.md`](docs/architecture.md)。

**关键组件**：

- **FunctionGraph TIMER 触发器**：`type = "TIMER"`、`schedule_type = "Cron"`，由六字段 Quartz 表达式驱动；`enable_timer=false` 时不创建。
- **FunctionGraph**：一个 Python 3.9 函数，512 MB / 600 s，入口 `index.handler`，已开启 LTS 日志。
- **对象存储服务（OBS）**：私有桶，保存按日期分区的 `text/html` 快照对象。
- **云日志服务（LTS）**：一个日志组 + 一个日志流，默认保留 7 天，采集标准输出的结构化日志行。
- **统一身份认证（IAM）**：以 `op_svc_cff` 为被委托方的云服务委托，授予 `OBS OperateAccess`。

---

## 4. 方案亮点

- **单归档、无外部挂载**：`scripts/package-function.sh` 把函数模块与声明的 HTTP 库组装进同一个 `build/function.zip`，运行时不依赖外部目录。
- **部署包内无长期密钥**：写桶使用调用上下文下发的临时凭据；部署所需访问密钥只留在部署机。
- **确定性对象键**：键由 UTC 时间与目标地址短哈希组成，快照可排序、可复现。
- **抓取回退**：优先使用随包打入的 HTTP 客户端，库不可用时回退标准库，保证最小化环境中仍可导入并运行。
- **两套验证档**：保留定时触发器做自动运行，或关闭触发器直接调用函数做一次性核对。
- **本地端到端检查**：26 项断言通过注入协作者走完整条 handler 链路，不连接任何云服务、不访问外网。

---

## 5. 涉及云服务

| 服务 | 用途 | 说明 |
|---|---|---|
| 函数工作流（FunctionGraph） | 快照函数与 TIMER 触发器 | Python 3.9、512 MB、600 s；一个函数 + 一个触发器 |
| 对象存储服务（OBS） | 保存快照对象的私有桶 | `acl = "private"`，桶名全局唯一 |
| 云日志服务（LTS） | 结构化应用日志 | 一个日志组 + 一个日志流，默认保留 7 天 |
| 统一身份认证（IAM） | 运行时委托 | 以 `op_svc_cff` 为被委托方的云服务委托，含 `OBS OperateAccess` |

> 不创建 VPC、NAT 网关、弹性公网 IP、公网负载均衡与公网入站入口。以上服务均由本仓库的 Terraform 创建；释放方式见[第 10 章「清理资源」](#10-清理资源)。

---

## 6. 前置条件

| 项 | 要求 | 说明 |
|---|---|---|
| **账号** | 已完成实名认证的华为云账号 | 个人或企业账号 |
| **权限** | IAM **Tenant Administrator** 或同等权限 | 用于创建 FunctionGraph、OBS、LTS 与云服务委托 |
| **区域** | 建议 `cn-north-4` | 不同区域的运行时与桶可用性存在差异 |
| **Terraform** | `>= 1.5.0` | IaC 部署工具 |
| **huaweicloud Provider** | `>= 1.97.0` | 华为云 Terraform Provider |
| **Python** | `>= 3.8` | 供打包脚本与本地检查使用 |
| **Bash** | Git Bash / WSL / Linux | 运行 `scripts/package-function.sh` |
| **访问密钥** | 在华为云「我的凭证」页面获取 Access Key 与 Secret Access Key，并通过 shell 环境提供 | 不要把凭据写入任何代码或配置文件 |

---

## 7. 快速开始

### 一键部署（推荐）

```bash
# 1. 克隆仓库
git clone <repo-https-url> distributed-x-infrastructure-scheduled-web-scraper-layer
cd distributed-x-infrastructure-scheduled-web-scraper-layer

# 2. 通过 shell 环境提供访问密钥（见第 6 章）
export HW_ACCESS_KEY="<your-access-key>"
export HW_SECRET_KEY="<your-secret-key>"

# 3. 构建部署归档并部署
bash scripts/package-function.sh
cd infra
cp terraform.tfvars.example terraform.tfvars
# 编辑 terraform.tfvars：填写 obs_bucket_name 与 target_url
terraform init
terraform plan
terraform apply -auto-approve
```

> **部署耗时**：数分钟；函数、桶、日志资源与委托一同创建。
> **完整步骤与预期输出**：见[第 8 章](#8-分步部署)与 [`docs/deployment-guide.md`](docs/deployment-guide.md)。

---

## 8. 分步部署

### 步骤 1：构建部署归档

```bash
bash scripts/package-function.sh
```

**预期输出**：`archive=.../build/function.zip files=<N> bytes=<N>`，随后 `Done: .../build/function.zip`。

### 步骤 2：初始化工作目录

```bash
cd infra
terraform init
```

**预期输出**：`Terraform has been successfully initialized!`

### 步骤 3：预览资源变更

```bash
terraform validate
terraform plan
```

**预期输出**：`Success! The configuration is valid.`，随后 `Plan: N to add, 0 to change, 0 to destroy.`

### 步骤 4：执行部署

```bash
terraform apply -auto-approve
```

**预期输出**：`Apply complete! Resources: N added, 0 changed, 0 destroyed.`

### 步骤 5：记录关键输出

```bash
terraform output
```

**预期输出**：列出 `bucket_name`、`function_name`、`function_urn`、`timer_schedule`、`timer_id`、`lts_group_id`、`lts_stream_id` 与 `invoke_command`。

---

## 9. 使用方法 / 验证

> **验证提醒**：部署完成后请按本章步骤自行验证，确认业务功能可用，方可视为交付完成。下列本地端到端检查已在开发期实际执行；云端命令需部署完成后方可执行。

### 验证 1：本地端到端检查（开发期已执行）

```bash
bash scripts/package-function.sh
python scripts/local-e2e/test_e2e.py
```

**预期输出**：
```
=== Summary: 26 passed, 0 failed ===
```

检查覆盖配置默认值与覆盖、事件类型判定、事件 / JSON 请求体中的目标地址覆盖、链路标识、注入与回退抓取、对象键形状与 URL 敏感性、两种写桶客户端接口、结构化日志与级别过滤、handler 成功 / 手动 / 覆盖 / 失败四条路径、摘要稳定性以及部署归档内容。全部协作者均为注入替身，不连接云服务、不访问外网。

### 验证 2：直接调用函数（需部署后执行）

```bash
hcloud fgs invoke --function-name "$(terraform output -raw function_name)" --body '{}'
```

**预期结果**：`statusCode = 200`，响应体含 `ok: true` 与 `trigger`、`target`、`http_status`、`bytes`、`sha256`、`bucket`、`key`、`object_status`、`trace_id`。

也支持单次调用覆盖目标地址：

```bash
hcloud fgs invoke --function-name "$(terraform output -raw function_name)" \
  --body '{"target_url": "https://www.example.com", "x-trace-id": "check-001"}'
```

### 验证 3：核对快照对象（需部署后执行）

打开 `terraform output -raw bucket_name` 指向的桶，在 `result_prefix` 前缀下查看对象。键形如 `snapshots/2026/11/09/065900-1a2b3c4d5e6f.html`，内容类型 `text/html; charset=utf-8`，正文为当次抓取到的页面内容。

### 验证 4：核对结构化日志（需部署后执行）

打开 `terraform output -raw lts_stream_id` 日志流。每次调用应出现 `invocation started` 与 `snapshot stored` 两行 `type=log` JSON，含 `service`、`trace_id`、`level`、`message`；成功行另带 `key` 与 `bytes`。抓取失败时产生 `ERROR` 行并返回 502。

### 验证 5：关闭定时触发器的轻量档

```bash
terraform apply -auto-approve -var enable_timer=false
```

再重复验证 2。**预期结果**：handler 响应与日志行一致；`timer_id` 为空，未创建触发器。

---

## 10. 清理资源

```bash
cd infra
terraform destroy -auto-approve
```

**预期输出**：`Destroy complete! Resources: N destroyed.`

> **避免资源残留**：
> - `terraform destroy` 只释放 Terraform 状态跟踪的资源；
> - 控制台手工创建的额外对象或触发器需手工释放；
> - 结果桶配置了 `force_destroy = true`，归档的快照对象会随桶一起清理。

---

## 11. 详细说明

### 工作流程

TIMER 触发器（或直接调用）进入 `index.handler`。事件适配层归一触发类型、解析可选的目标地址覆盖与链路标识；抓取层用随包打入的客户端发起 HTTP GET，库不可用时回退标准库；接着由 UTC 时间与目标地址短哈希生成确定性对象键；存储层用调用上下文的临时凭据构造 OBS 客户端并写入正文；日志层输出结构化 JSON 行，handler 返回含摘要、字节数与对象键的结果。抓取异常统一收敛为结构化 502 响应。

### 模块划分

| 模块 | 源码位置 | 职责 |
|---|---|---|
| 入口 | `src/functions/src/index.py` | `create_handler(deps)`，可注入 config / fetch / 客户端工厂 / 时钟 / 日志 sink；模块级 `handler` |
| 配置 | `src/functions/src/config.py` | `Config` 数据类与 `load_config()`，空值保留默认 |
| 事件适配 | `src/functions/src/events.py` | `event_kind()`、`target_override()`、`trace_id()` |
| 抓取 | `src/functions/src/fetcher.py` | `fetch()`，优先随包客户端、标准库回退、支持 opener 注入 |
| 存储 | `src/functions/src/storage.py` | `result_key()`、`make_client()`、`put_snapshot()` |
| 可观测 | `src/functions/src/observability.py` | 结构化 JSON 日志器，支持级别过滤与 sink 注入 |

### 配置项

| 变量 | 默认值 | 说明 |
|---|---|---|
| `region` | `cn-north-4` | 部署区域，同时用于推导 OBS 端点 |
| `app_name` | `scheduled-web-scraper` | 所有资源名前缀 |
| `obs_bucket_name` | 按应用名 + 区域推导 | 全局唯一的私有桶名 |
| `function_runtime` | `Python3.9` | FunctionGraph 运行时 |
| `function_memory_size` | `512` | 函数内存 MB |
| `function_timeout` | `600` | 函数超时秒数 |
| `enable_timer` | `true` | 是否创建 TIMER 触发器 |
| `timer_schedule` | `0 59 6,10,14,18 * * ?` | 六字段 Quartz cron 串 |
| `timer_schedule_type` | `Cron` | 触发器调度类型 |
| `target_url` | `https://www.example.com` | 每次调用抓取的页面地址 |
| `result_prefix` | `snapshots` | 对象键前缀 |
| `lts_ttl_in_days` | `7` | 日志保留天数 |
| `service_name` / `log_level` | `scheduled-web-scraper` / `INFO` | 结构化日志服务名与最低级别 |

完整清单与逐步说明见 [`docs/deployment-guide.md`](docs/deployment-guide.md)。

### 事件形态与响应

| 输入 | 识别为 | 说明 |
|---|---|---|
| `{"trigger_type":"TIMER", ...}` | `TIMER` | 定时触发器 |
| `{"schedule_time":"..."}` 或 `{"type":"timer"}` | `TIMER` | 平台定时器变体 |
| `{"httpMethod":"GET", ...}` | `APIG` | 网关形态事件 |
| `{}` | `MANUAL` | CLI / 测试事件直接调用 |
| `{"target_url":"..."}` 或 JSON 请求体中的 `url` / `target` | 覆盖配置页面 | 仅对该次调用生效 |

成功返回 `{"statusCode": 200, "body": {...}, "isBase64Encoded": false}`；抓取失败返回 `502` 与 `{"ok": false, "error": "fetch_failed", "detail": "..."}`。

---

## 12. 依赖

| 名称 | 版本 | 用途 |
|---|---|---|
| Terraform | `>= 1.5.0` | IaC 编排 |
| huaweicloud Provider | `>= 1.97.0` | 华为云资源 |
| Python | `>= 3.8` | 打包脚本与本地检查；函数运行时 `Python3.9` |
| `requests` | `2.31.0` | 随部署归档打包的 HTTP 客户端 |
| OBS Python SDK | 由 FunctionGraph 运行时提供 | 由调用上下文凭据构造桶客户端 |

---

## 13. FAQ / 故障排除

### Q1：部署提示「权限不足」怎么办？

**A**：确认账号具备 IAM **Tenant Administrator**，或至少具备 FunctionGraph、OBS、LTS 与创建云服务委托的权限。

### Q2：`terraform apply` 报 `FSS.1501 The delegate not exist` 是什么原因？

**A**：IAM 委托传播是异步的。配置已声明对委托的 `depends_on`，等待约一分钟后重新 apply 即可。

### Q3：桶名被拒绝是什么原因？

**A**：桶名全局唯一。请显式设置 `obs_bucket_name` 为自己的唯一名称。

### Q4：定时器没有按预期触发，该查什么？

**A**：`timer_schedule` 必须是六字段 Quartz 表达式（秒 分 时 日 月 周），周字段用 `?`。核对 `terraform output timer_schedule` 与 `timer_id`。

### Q5：函数返回 502 `fetch_failed` 怎么办？

**A**：检查 `target_url`、出站连通性与超时；`fetch failed` 日志行会记录异常类型。随包客户端不可用时 handler 会自动回退标准库客户端。

### Q6：抓取成功但对象没有写入，为什么？

**A**：桶客户端需要调用上下文提供的完整临时凭据三元组。确认 `op_svc_cff` 委托已带 `OBS OperateAccess`，且函数日志配置已生效。

### 排障速查

| 现象 | 可能原因 | 处置 |
|---|---|---|
| `FSS.1009 Invalid function UserData` | 存在空字符串环境变量 | 配置在编码前过滤空值 |
| 缺部署包报错 | 跳过打包步骤 | `terraform plan` 前先运行 `bash scripts/package-function.sh` |
| `files=<N>` 但归档内没有第三方库 | 本地库安装不可用 | 联网后重新打包；期间 handler 回退标准库 |
| 日志流没有日志 | LTS 绑定未生效 | 确认 `enable_lts_log = true` 与日志组 / 流标识 |

---

## 14. 贡献指南

欢迎提交 Issue 与 PR，建议流程：

1. **Issue**：描述问题或建议，附复现命令、预期与实际输出、截图。
2. **PR**：从 `main` 建特性分支；提交前运行 `terraform fmt -check`、`terraform validate`、`bash scripts/package-function.sh` 与 `python scripts/local-e2e/test_e2e.py`。
3. **Code Review**：由 **[@<github-username>](https://github.com/<github-username>)** 评审后合并。

详见 `CONTRIBUTING.md`。

---

## 15. 许可证

本实践采用 **MIT No Attribution** 许可证。完整条款见仓库根目录的 [`LICENSE`](LICENSE)。

```
MIT No Attribution

Copyright (c) Huawei Cloud

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software... (no attribution required)
```

---

## 16. 联系方式 / 维护者

| 项 | 内容 |
|---|---|
| **创建者** | [@<github-username>](https://github.com/<github-username>) |
| **维护者** | [@<github-username>](https://github.com/<github-username>) |
| **联系方式** | GitHub Issues / PR（见[第 14 章](#14-贡献指南)） |
