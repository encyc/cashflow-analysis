# 05 · 接口与任务状态

以下为一期目标契约草案，**全部新接口待开发**。当前只有原型 `POST /api/submissions`，不能把它当成下面的公司集成 API。公司可统一路径命名，但字段含义、鉴权和幂等语义必须保留。示例为虚构 ID，不使用真实客户信息。

## 1. 通用约定

- 公司内部接口前缀 `/api/v1/cashflow`，内部服务调用用公司服务身份，PC 使用公司登录会话；每次请求校验组织和业务单权限，`org_id` 从身份上下文取得。
- H5 接口前缀 `/api/v1/collection`，使用独立采集会话，仅允许自身 case 的授权、提交、补件和状态，不允许报告查询。
- Cookie 会话使用 Secure/HttpOnly 和适当 SameSite，变更请求校验 CSRF/Origin；公司接口如用 Bearer，则遵循公司凭据管理。不能把长期 access token 放 URL。
- 金额为分的十进制字符串，例 `"12500"` 表示 125.00 元；时间 ISO8601 含时区。日期过滤按 04，排序稳定。
- POST 创建/重试/生成必须携带 `Idempotency-Key`。在主体/操作范围内保存请求摘要及响应；建议保留至少 7 天，过期后仍有文件摘要/业务唯一键保护。同键不同内容返回 409。
- 受理异步工作返回 202，明确只代表任务已持久化；GET 状态为权威。所有响应含 `trace_id`，错误不返回堆栈/密码/完整身份字段。

错误响应：

```json
{
  "error": {
    "code": "FILE_PASSWORD_INVALID",
    "message": "文件密码不正确，请重新填写",
    "retryable": false,
    "action": "RESUBMIT_PASSWORD"
  },
  "trace_id": "tr_demo_001"
}
```

这里 `retryable` 表示可自动重试；客户重新提交正确密码属于新的输入操作。

## 2. 公司业务及 PC 接口

| 方法与路径（均在 cashflow 前缀下） | 主要输入 | 主要输出/权限 |
| --- | --- | --- |
| `POST /cases` | `business_id, subject_id, required_platforms, expected_period` | `case_id,status`；服务端核查客户确属业务单 |
| `GET /cases` | `business_id,status,created_from/to,cursor,limit` | 授权范围内列表、`next_cursor` |
| `GET /cases/{case_id}` | 无 | 材料齐备、最新尝试、当前报告、缺件，不混合两个状态 |
| `POST /cases/{case_id}/collection-sessions` | `expires_in_seconds` | 一次性采集链接、有效期；仅经办可发起 |
| `DELETE /collection-sessions/{session_id}` | 原因 | 撤销；旧链接/会话不可继续上传 |
| `GET /cases/{case_id}/files` | 可选状态过滤 | 脱敏文件列表、平台、身份结果、解析状态、是否采用 |
| `POST /cases/{case_id}/input-selection` | `file_ids,expected_input_revision,reason` | 新 `input_revision`；同平台最多一份，冲突返回 409 |
| `POST /cases/{case_id}/identity-confirmations` | `file_id,verification_ref,reason` | 无证件材料人工确认；有证件冲突不允许调用绕过 |
| `POST /cases/{case_id}/single-platform-exceptions` | `platform,reason,expected_input_revision` | 主管审批例外，记录决定 ID |
| `POST /cases/{case_id}/reports` | `input_revision` | 异步 `report_id,job_id,status`；通常由齐备事件自动调用同一生成逻辑 |
| `GET /cases/{case_id}/reports` | 分页 | 历史版本、输入修订、创建时间、可用状态 |
| `GET /reports/{report_id}` | 无 | 已发布报告元信息、完整性、版本；无权返回统一 404 |
| `GET /reports/{report_id}/overview` | `platform,start_date,end_date` | 该范围总览和月度组合图，附实际生效过滤条件 |
| `GET /reports/{report_id}/scenes` | `platform,start_date,end_date,scene` | 场景/渠道聚合；返回可下钻标识 |
| `GET /reports/{report_id}/loan-periods` | `platform` | 固定截止日窗口；不接受自定义日期，传入则 422 |
| `GET /reports/{report_id}/profiles` | `platform,start_date,end_date,sort` | 标签及交易画像，明确重叠计数 |
| `GET /reports/{report_id}/statistics` | `group_by,platform,start_date,end_date` | `group_by=category/party/payment/hour` 的原有模块数据 |
| `GET /reports/{report_id}/transactions` | 见后文 | 服务端分页、总笔数/收支汇总、`next_cursor` |
| `GET /reports/{report_id}/transactions/{transaction_id}` | 无 | 单笔原文字段、规则依据和受控来源定位 |
| `GET /files/{file_id}/content` | 可选 `page` | 权限校验后的原件流/预览；独立下载权限及审计 |
| `POST /cases/{case_id}/review-records` | `report_id,comment,adopt` | 保存备注或采用版本；不得改原交易 |
| `GET /jobs/{job_id}` | 无 | 阶段、状态、错误码和下一步；普通用户无堆栈 |
| `POST /jobs/{job_id}/retry` | `reason` | 技术暂时故障重试；永久错误要求新材料 |
| `POST /cases/{case_id}/deletion-requests` | `scope,reason` | 审批/执行中的删除单；按公司权限处理 |

交易过滤包含 `platform, direction, category, scene, channel_key, tag_key, keyword, start_date, end_date, min_amount_cents, max_amount_cents, cursor, limit`。金额两端包含；分页建议默认 20、上限 100，按 `(occurred_at DESC,id DESC)` 稳定排序。cursor 绑定 report_id 和过滤条件，修改条件需重新第一页。汇总是筛选结果全量汇总，不是当前页求和。

所有下钻参数使用后端提供的稳定 ID，不把渠道显示名拼接到路径充当权限凭据。非法枚举、反向日期/金额区间和超范围分页返回 422。

创建采集单示例：

```http
POST /api/v1/cashflow/cases
Idempotency-Key: demo-create-case-001
Content-Type: application/json
```

```json
{
  "business_id": "biz_demo_001",
  "subject_id": "sub_demo_001",
  "required_platforms": ["wechat", "alipay"],
  "expected_period": {"start_date": "2025-10-01", "end_date": "2026-09-28"}
}
```

```json
{"case_id":"case_demo_001","status":"WAITING_FILES","trace_id":"tr_demo_001"}
```

建议 201 创建、幂等重放返回原资源。账期未覆盖期望区间时进入待补件；主管若同意缩短区间，更新期望区间并留决策记录、生成新输入修订，不悄悄忽略。

## 3. 客户上传 H5 接口

| 方法与路径（collection 前缀） | 行为 |
| --- | --- |
| `POST /session/exchange` | 一次性短码 + 公司身份校验证据，换短期会话；不可用短码访问报告 |
| `GET /session` | 当前有效会话、采集单脱敏说明、要求平台、支持格式、限额与授权版本 |
| `POST /consents` | `policy_version,agreed=true`；服务端记录授权证据并返回 `consent_id` |
| `POST /files` | multipart：`file,platform,consent_id,password?`，幂等键；会话决定归属 |
| `GET /files/{file_id}/status` | 本会话所属材料处理状态、中文原因、下一步 |
| `POST /files/{file_id}/credentials` | `password`；仅对该客户待补密码文件，清理旧凭据并重新排队 |
| `POST /files/{file_id}/replacement` | 新文件 + 可选密码 + 幂等键，标记替换关系并递增修订 |
| `POST /complete` | 客户确认本轮提交完成；返回齐备/待补件，不代表报告成功 |

单次文件接收的 202 响应：

```json
{
  "submission_id": "submission_demo_001",
  "file_id": "file_demo_001",
  "status": "RECEIVED",
  "message": "文件已收到，正在处理",
  "status_url": "/api/v1/collection/files/file_demo_001/status",
  "trace_id": "tr_demo_002"
}
```

采用 API 流式转存，不在应用层一次读完整文件后判断上限；如公司改用签名直传，必须增加“完成上传确认”接口，由后端核验实际对象大小、SHA256、归属和内容后才进入 RECEIVED。断流对象不可触发解析。

链接中的一次性交换码在网关、分析工具和 Referer 中脱敏，页面交换后移除地址里的码；不能加载泄露完整 URL 的第三方统计脚本。刷新后依赖受控会话查询状态。

## 4. 状态机

状态分层，不能用一个 `status=success` 混淆上传、解析、报告、回调。

| 对象 | 状态及主要迁移 |
| --- | --- |
| 文件 | `RECEIVED → INSPECTING → PARSING → VALIDATING → PARSED`；检查阶段可进 `WAITING_PASSWORD / NEEDS_REPLACEMENT / FAILED`；补件重新排队；旧文件可 `SUPERSEDED` |
| 文件身份 | `UNVERIFIED → MATCHED / MANUALLY_CONFIRMED / MISMATCH`，独立于 PARSED；MISMATCH 不能直接人工改确认 |
| 解析/生成任务 | `QUEUED → RUNNING → SUCCEEDED`；暂时故障 `RETRY_WAIT → QUEUED`；永久/耗尽重试 `FAILED`；撤销 `CANCELLED` |
| 报告 | `BUILDING → READY / FAILED / SUPERSEDED`；过期输入任务标 SUPERSEDED 不发布；已 READY 的旧版本仍 READY，通过 current 指针区分；删除 `REVOKED` |
| 采集单 | `WAITING_FILES → PROCESSING → ACTION_REQUIRED / READY`；重新补件时 PROCESSING；终止 CLOSED。另带 `current_report_id` 和 `latest_attempt_status` |
| 通知 | `PENDING → DELIVERED`；失败 RETRY_WAIT，超限 DEAD_LETTER，人工补发留痕 |

允许生成条件：所要求平台的采用文件均 PARSED、核验通过、身份 MATCHED/MANUALLY_CONFIRMED、有效授权、期间符合要求或有批准调整、输入修订未过期。单平台例外需要有效决定 ID。至少一份真实解析成功材料，不出空白“成功报告”。

## 5. 错误及重试

| code | HTTP/阶段 | 行为 |
| --- | --- | --- |
| `SESSION_EXPIRED` | 401 | 重新获取采集会话 |
| `RESOURCE_NOT_FOUND` | 404 | 无资源或无对象权限统一响应 |
| `CONSENT_REQUIRED` | 422 | 完成有效授权 |
| `FILE_TOO_LARGE` | 413 | 提示上限、重新导出 |
| `UNSUPPORTED_FORMAT` | 422 / 异步文件错误 | 选择支持的证明版式 |
| `FILE_PASSWORD_REQUIRED/INVALID` | 异步文件状态 | 补密码，不无限自动重试 |
| `IDENTITY_MISMATCH` | 异步身份状态 | 阻断合并、纠正材料 |
| `PERIOD_INCOMPLETE` | 异步文件/采集单状态 | 补足期间或审批调整 |
| `RECONCILIATION_FAILED` | 异步核验状态 | 不发布；技术诊断或补件 |
| `REVISION_CONFLICT/IDEMPOTENCY_CONFLICT` | 409 | 刷新版本/使用正确请求键 |
| `RESOURCE_LIMIT_EXCEEDED` | 异步文件状态 | 页数、解压、行数限制；不截断成功 |
| `RATE_LIMITED` | 429 | 返回 Retry-After，按会话/业务/代理校验后的 IP 限流 |
| `DEPENDENCY_UNAVAILABLE` | 503 或任务状态 | 可自动重试，保留已有受理结果 |

解析基础设施故障建议最多自动重试 3 次，退避 1/5/15 分钟；解析版式错误、密码、身份、金额核验失败不做盲重试。超限时展示失败和责任入口，不永久循环。

## 6. 业务系统回调

一期只回调到公司登记的固定地址；客户不能设置 URL。事件类型 `cashflow.report.ready`、`cashflow.case.action_required`、`cashflow.report.failed`、`cashflow.report.revoked`。回调不含交易明细/密码/证件，业务系统收到后通过鉴权 API 查询。

```json
{
  "event_id": "evt_demo_001",
  "event_type": "cashflow.report.ready",
  "occurred_at": "2026-09-29T14:00:00+08:00",
  "case_id": "case_demo_001",
  "business_id": "biz_demo_001",
  "report_id": "report_demo_002",
  "report_version": 2,
  "input_revision": 3,
  "status": "READY",
  "schema_version": "1.0"
}
```

优先沿用公司服务认证/事件总线；HTTP 回调如需签名，定义 `X-Key-Id`、`X-Timestamp`、`X-Event-Id`、`X-Signature`：签名为 HMAC-SHA256(key, timestamp + `\n` + event_id + `\n` + 原始 UTF-8 body)，十六进制编码。接收端常量时间比较、建议 5 分钟时间窗、event_id 去重，支持密钥轮换；每次重试重新签当前时间，同一事件 ID 不变。

返回 2xx 表示已持久接收；建议 1 分钟、5 分钟、30 分钟、2 小时、6 小时重试后进入死信，允许人工重发。先到 V2 后到 V1 的回调不能回退 current 指针；按输入修订、报告版本检查并查询服务器权威状态。报告 READY 与通知 DELIVERED 分别监控。
