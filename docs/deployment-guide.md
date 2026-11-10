# 部署指导书

> 本指导书按 `distributed-x-infrastructure-scheduled-web-scraper-layer` 的真实目录名书写，所有 `cd` 均为相对路径。

## 1. 部署前准备

| 项 | 要求 |
|---|---|
| 账号 | 已完成实名认证的华为云账号 |
| 权限 | 具备创建 FunctionGraph、OBS、LTS 与 IAM 委托的权限 |
| 区域 | 建议 `cn-north-4`；切换到其他区域时请同步确认运行时与桶名可用 |
| Terraform | `>= 1.5.0` |
| huaweicloud Provider | `>= 1.97.0` |
| Python | `>= 3.8`，供打包脚本组装 zip 使用 |
| Bash | 供 `scripts/package-function.sh` 使用（Git Bash / WSL / Linux 均可） |
| 访问密钥 | 在华为云「我的凭证」页面获取 Access Key 与 Secret Access Key，仅通过部署机 shell 环境提供 |

> 不要把访问密钥写进 `terraform.tfvars`、代码或任何提交到版本控制的文件。`infra/terraform.tfvars.example` 只含占位符与默认值，复制后填写的内容已被 `.gitignore` 忽略。

## 2. 构建部署归档

在仓库根目录执行：

```bash
bash scripts/package-function.sh
```

脚本依次完成：清空并重建 `build/package`、复制 `src/functions/src/` 与 `requirements.txt`、把声明的库安装进同一个目录、组装 `build/function.zip`。

**预期输出**（文件数与字节数随本地库版本略有差异）：

```
[1/4] Preparing build directory ...
[2/4] Copying function sources ...
[3/4] Bundling declared libraries into the same archive ...
      bundled libraries from requirements.txt
[4/4] Assembling deployment archive ...
archive=.../build/function.zip files=<N> bytes=<N>
Done: .../build/function.zip
```

若本地缺少网络导致库安装失败，脚本会打印回退提示；`fetcher.py` 在这种情况下自动使用标准库客户端，函数仍可运行。

## 3. 本地检查（部署前建议执行）

```bash
python scripts/local-e2e/test_e2e.py
```

**预期输出**：`=== Summary: 26 passed, 0 failed ===`

该检查不连接云端，覆盖配置默认值与覆盖、事件类型判定、目标地址覆盖、链路标识、抓取回退、对象键形状与 URL 敏感性、写桶接口兼容、结构化日志、handler 成功 / 手动 / 覆盖 / 失败四条路径、摘要稳定性，以及部署归档内容。

Terraform 静态检查：

```bash
cd infra
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
```

**预期输出**：`Success! The configuration is valid.`

## 4. 填写部署参数

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
```

按需编辑 `terraform.tfvars`。重点参数：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `region` | `cn-north-4` | 部署区域 |
| `app_name` | `scheduled-web-scraper` | 所有资源名前缀 |
| `obs_bucket_name` | 空（按应用名 + 区域推导） | 全局唯一的桶名；建议显式指定 |
| `function_runtime` | `Python3.9` | 函数运行时 |
| `function_memory_size` | `512` | 内存 MB |
| `function_timeout` | `600` | 超时秒数 |
| `enable_timer` | `true` | 是否创建定时触发器；轻量档设为 `false` |
| `timer_schedule` | `0 59 6,10,14,18 * * ?` | Quartz 风格 cron 串 |
| `timer_schedule_type` | `Cron` | 触发器调度类型 |
| `target_url` | `https://www.example.com` | 抓取目标页面 |
| `result_prefix` | `snapshots` | 对象键前缀 |
| `lts_ttl_in_days` | `7` | 日志保留天数 |
| `service_name` | `scheduled-web-scraper` | 结构化日志服务名 |
| `log_level` | `INFO` | 最低日志级别 |

`timer_schedule` 为六字段 Quartz 串（秒 分 时 日 月 周），与常见的五字段 cron 不同；修改时务必保留六个字段，周字段用 `?`。

## 5. 执行部署

```bash
cd infra
terraform init
terraform plan
terraform apply -auto-approve
```

**预期输出**：`Plan: N to add, 0 to change, 0 to destroy.` 随后 `Apply complete! Resources: N added, 0 changed, 0 destroyed.`

首次创建云服务委托后传播存在延迟，函数创建可能报 `FSS.1501 The delegate not exist`；配置已声明 `depends_on`，等待约一分钟后重新 `terraform apply -auto-approve` 即可。

## 6. 记录输出

```bash
terraform output
```

| 输出 | 用途 |
|---|---|
| `bucket_name` | 核对快照对象 |
| `function_name` / `function_urn` | 直接调用函数、查看版本 |
| `timer_schedule` / `timer_id` | 确认触发器是否创建及其 cron 串 |
| `lts_group_id` / `lts_stream_id` | 查看结构化日志 |
| `invoke_command` | 直接调用函数的示例命令 |

## 7. 部署后验证

### 7.1 直接调用函数

```bash
hcloud fgs invoke --function-name "$(terraform output -raw function_name)" --body '{}'
```

也可在控制台选择该函数，用测试事件 `{"target_url": "https://www.example.com"}` 调用。

**预期结果**：返回 `statusCode = 200`，响应体含 `ok: true`、`trigger`、`target`、`http_status`、`bytes`、`sha256`、`bucket`、`key`、`object_status` 与 `trace_id`。

### 7.2 核对快照对象

在 `terraform output -raw bucket_name` 指向的私有桶中查看 `result_prefix` 前缀下的对象。对象键形如：

```
snapshots/2026/11/09/065900-1a2b3c4d5e6f.html
```

内容类型为 `text/html; charset=utf-8`，正文是当次抓取到的页面内容。用同一目标地址与同一时刻重放，键保持稳定。

### 7.3 核对结构化日志

打开 `terraform output -raw lts_stream_id` 日志流，每次调用应出现 `invocation started` 与 `snapshot stored` 两行 `type=log` JSON，含 `service`、`trace_id`、`level`、`message`，成功行另带 `key` 与 `bytes`。抓取失败时会出现 `fetch failed` 的 `ERROR` 行，且函数返回 502。

### 7.4 轻量验证档

```bash
terraform apply -auto-approve -var enable_timer=false
```

此时 `timer_id` 为空、`timer_schedule` 输出提示触发器已关闭，其余资源不变。按 7.1 直接调用函数，验证结果与完整档一致。本档不创建定时器，不会按计划自动产生调用，适合做一次性链路核对。

> 部署完成后请按本节步骤自行验证，确认业务功能可用，方可视为交付完成。

## 8. 排障表

| 现象 | 可能原因 | 处置 |
|---|---|---|
| `FSS.1009 Invalid function UserData` | 存在空字符串环境变量 | 配置已用 `local.env_without_empty` 过滤空值；检查新增变量是否绕过该过滤 |
| `FSS.1501 The delegate not exist` | 云服务委托传播延迟 | 等待约一分钟后重新 apply |
| 打包报缺 `build/function.zip` | 未执行打包脚本就 plan | 先运行 `bash scripts/package-function.sh`；配置对此给出明确的运行时报错而非晦涩的 base64 错误 |
| OBS 桶名冲突 | 桶名全局唯一 | 显式设置 `obs_bucket_name` 为自己的唯一名称 |
| 函数返回 502 `fetch_failed` | 目标地址不可达、超时或证书问题 | 检查 `target_url`、出站连通性与超时；查看 `fetch failed` 日志行的错误类型 |
| 写桶失败但抓取成功 | 委托权限未生效或临时凭据标识缺失 | 确认 `op_svc_cff` 委托与 `OBS OperateAccess` 已生效；`make_client()` 需拿到完整三元组 |
| 定时触发器未按时调用 | cron 串字段数不对 | 使用六字段 Quartz 串，周字段用 `?`；核对 `timer_schedule` 输出 |
| 日志流里没有日志 | 函数日志开关或日志组绑定未生效 | 确认 `enable_lts_log = true` 且 `log_group_id` / `log_stream_id` 指向本实践的资源 |

## 9. 释放资源

```bash
cd infra
terraform destroy -auto-approve
```

**预期输出**：`Destroy complete! Resources: N destroyed.`

`terraform destroy` 只释放 Terraform 状态跟踪的资源；在控制台手工创建的额外对象或触发器需手工释放，避免残留。桶配置了 `force_destroy = true`，归档的快照对象会随桶一起清理。
