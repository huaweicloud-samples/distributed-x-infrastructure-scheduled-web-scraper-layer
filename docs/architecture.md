# 架构说明

## 总体架构

本实践演示「用一个定时触发的无服务器函数完成网页快照采集与归档」：函数工作流（FunctionGraph）的定时触发器按 Quartz 风格 cron 表达式调用函数；函数每次执行向配置的目标页面发起 HTTP GET，把响应正文按可排序的对象键写入私有对象存储桶，并向云日志服务（LTS）输出结构化 JSON 日志。函数源码与其声明的第三方 HTTP 库打进同一个部署归档；运行时凭据来自调用上下文下发的临时凭据，部署包内不保存长期密钥。

完整档（默认 `enable_timer = true`）由定时触发器发起调用：

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

**图例**：① 定时触发器按 cron 表达式（或直接调用）触发函数；② 函数向配置的目标页面发起 HTTP GET 并读取正文；③ 用调用上下文的临时凭据把快照对象写入私有桶；④ 向 LTS 输出结构化 JSON 日志行。

## 轻量验证档拓扑

把 `enable_timer` 设为 `false` 时，定时触发器不再创建；函数、私有桶、日志组与日志流保持不变。链路变化只在「谁发起调用」这一环，函数内部的抓取、对象键生成、写桶与日志输出完全一致，可直接用 CLI 或测试事件调用函数完成验证。

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

两档的拓扑差异仅限发起端：完整档由平台定时器按计划调用；轻量档由使用者主动调用。函数与三个下游目标之间的三条链路、步骤编号 ②③④ 在两档中保持一致。

## 关键组件

| 组件 | 服务 | 职责 |
|---|---|---|
| 定时触发器 | 函数工作流（FunctionGraph）TIMER 触发器 | `type = "TIMER"`、`schedule_type = "Cron"`，按 `0 59 6,10,14,18 * * ?` 一类 Quartz 表达式触发函数；`enable_timer=false` 时不创建 |
| 快照函数 | 函数工作流（FunctionGraph） | Python 3.9、512 MB、600 s；入口 `index.handler`；解码事件、抓取页面、生成对象键、写桶、输出日志、返回结构化结果 |
| 结果存储 | 对象存储服务（OBS） | 私有桶（`acl = "private"`），保存 `text/html` 快照对象；桶名全局唯一，可由 `obs_bucket_name` 指定或按应用名与区域推导 |
| 结构化日志 | 云日志服务（LTS） | 一个日志组 + 一个日志流，保留期由 `lts_ttl_in_days` 控制；函数开启 `enable_lts_log`，只向标准输出写 JSON 行 |
| 运行时授权 | 统一身份认证（IAM）云服务委托 | 以 `op_svc_cff` 为被委托服务、授予 `OBS OperateAccess`，使函数获得写桶权限；日志投递由函数上的日志配置承载 |
| 部署归档 | `build/function.zip` | 由 `scripts/package-function.sh` 组装：`src/functions/src/` 下的源码 + `requirements.txt` 声明的库同包，无独立依赖层 |

## 工作流程

1. 定时触发器到达计划时间，或使用者以 CLI / 测试事件直接调用函数，FunctionGraph 以 `index.handler` 进入。
2. `events.event_kind()` 把事件归一为 `TIMER` / `MANUAL` / `APIG` / `UNKNOWN`；`events.target_override()` 允许本次调用从事件顶层或 JSON 请求体覆盖目标地址；`events.trace_id()` 大小写不敏感读取 `x-trace-id`，缺失时用本地标识。
3. `fetcher.fetch()` 发起 HTTP GET：优先使用随归档打包的 `requests`，库不可用或本地最小化环境时回退标准库 `urllib.request`；返回正文与状态码。
4. `storage.result_key()` 生成确定性、可排序的对象键 `<prefix>/YYYY/MM/DD/HHMMSS-<url 哈希前 12 位>.html`，同一目标地址在同一时刻的键稳定可复现。
5. `storage.make_client()` 从调用上下文读取临时访问密钥、秘密访问密钥与临时凭据标识，构造 OBS 客户端；`storage.put_snapshot()` 兼容 `putContent` 与 `put_object` 两种客户端接口，写入私有桶。
6. `observability.create_logger()` 输出含 `service` / `trace_id` / `level` / `message` 的 JSON 行，由 LTS 采集；函数返回 `statusCode = 200` 与含 `sha256`、`bytes`、`bucket`、`key`、`object_status` 的结果体。
7. 抓取异常收敛为 `statusCode = 502` 与 `fetch_failed` 结构化错误，并写一条 `ERROR` 级日志，不向调用方抛出未处理异常。

## 部署包形态

`scripts/package-function.sh` 把 `src/functions/src/` 的七个模块（`config.py`、`events.py`、`fetcher.py`、`observability.py`、`storage.py`、`index.py`）与 `requirements.txt` 声明的库一并复制到 `build/package`，再打成单个 `build/function.zip`。`infra/functions.tf` 通过 `func_code` 以 base64 上传该归档，`code_type = "zip"`、`handler = "index.handler"`。源码与第三方库同包，函数运行时不依赖外部挂载目录。

本地端到端检查对此设有专门断言：归档内既要有全部自有模块，也要有随包打入的第三方库目录，确保部署包自洽。

## 凭据分工

| 平面 | 目标 | 凭据来源 | 提供位置 |
|---|---|---|---|
| 部署控制面 | Terraform 创建函数、桶、日志与委托 | 部署者在 shell 环境提供的 Access Key 与 Secret Access Key | 部署机 shell 环境；`terraform.tfvars.example` 只放占位符 |
| 函数数据面 | 私有桶写对象 | 调用上下文下发的临时访问密钥 / 秘密访问密钥 / 临时凭据标识 | `src/functions/src/storage.py` 的 `make_client()`，经 `context` 读取 |

控制面凭据只存在于部署机，不会写进部署包、环境变量或代码；数据面凭据由平台在每次调用时下发，函数不持有长期密钥。`storage.make_client()` 把三者一并交给 OBS 客户端，缺少临时凭据标识时写桶会失败，因此本地检查通过注入的客户端工厂替身来验证同一条调用链，而不连接云端。

## 安全设计

| 项 | 设计 |
|---|---|
| 长期密钥 | 部署包、配置与代码中不含长期密钥；访问密钥由部署机 shell 环境提供，`terraform.tfvars` 被版本控制忽略 |
| 桶访问 | 结果桶为私有桶，无公网读写入口；未创建 VPC、NAT 网关、弹性公网 IP 或公网负载均衡 |
| 权限最小化 | 云服务委托仅授予 `OBS OperateAccess`，不含通配策略；日志投递由函数日志配置承载，不额外下发权限 |
| 目标地址 | 默认 `https://www.example.com`；事件可覆盖目标地址属教学用途，生产使用应改为地址白名单并限制出站范围 |
| 传输 | 出站抓取使用 HTTPS；OBS 客户端使用区域 HTTPS 端点 |
| 环境净化 | 函数工作流拒绝空字符串环境变量，Terraform 在编码 `user_data` 前过滤空值，避免 `FSS.1009` |
| 日志 | 结构化日志只写标准输出，函数内不持有日志凭据或网络客户端 |
| 对象可追溯 | 结果体与日志行都带 `trace_id`、`key`、`bytes` 与正文 `sha256`，便于核对写入结果 |

## 配置对应关系

| 配置项 | 位置 | 说明 |
|---|---|---|
| `REGION` | `infra/variables.tf` → `region` | 部署区域，默认 `cn-north-4`，同时用于推导 OBS 端点 |
| `OBS_BUCKET` | `infra/storage.tf` → `huaweicloud_obs_bucket.results.bucket` | 私有桶名，随环境变量下发 |
| `OBS_ENDPOINT` | `infra/functions.tf` → `https://obs.<region>.myhuaweicloud.com` | OBS 客户端区域端点 |
| `TARGET_URL` | `infra/variables.tf` → `target_url` | 每次调用抓取的页面地址 |
| `RESULT_PREFIX` | `infra/variables.tf` → `result_prefix` | 对象键前缀，默认 `snapshots` |
| `TIMER_SCHEDULE` | `infra/variables.tf` → `timer_schedule` | Quartz 风格 cron 串，默认 `0 59 6,10,14,18 * * ?` |
| `SERVICE_NAME` / `LOG_LEVEL` | `infra/variables.tf` | 日志服务名与最低输出级别 |
| `LTS_GROUP_ID` / `LTS_STREAM_ID` | `infra/observability.tf` | 日志组与日志流标识，随环境变量下发 |
| `enable_timer` | `infra/variables.tf` | 是否创建定时触发器，默认 `true` |
| `function_runtime` / `function_memory_size` / `function_timeout` | `infra/variables.tf` | 运行时 Python 版本、内存与超时 |
| `lts_ttl_in_days` | `infra/variables.tf` | 日志保留天数，默认 7 |

完整参数、分步命令与排障表见 [`docs/deployment-guide.md`](deployment-guide.md)。
