# 客户流水采集 H5 — 设计文档

> 历史原型设计，后续已实现独立采集端。本文的“待实现”状态及邮件/密码等约定保留作历史记录；当前事实见 [项目现状](../../handoff/01-project-inventory.md)，公司生产化目标见 [需求包](../../handoff/README.md)。本文早期所称 ZIP 解析能力不成立：现有 collector 只接收 ZIP，自动解密解压仍待开发。

日期：2026-09-28
状态：设计经用户口头确认，待实现
所属仓库：/Users/mac/cashflow-analysis（新增 `collector/` 子项目，不改动现有 `prototype/`）

## 1. 背景与目标

现有 `prototype/` 管线已能解析客户提供的微信/支付宝流水（加密 zip / PDF / Excel）。目前文件由人工渠道收取。本项目构建一个 H5 采集页：客户在手机上（主要是微信内置浏览器）打开链接，按引导自行导出微信/支付宝流水，上传文件并填写解压密码，后端将文件作为附件发送到指定邮箱并在服务器留档。

成功标准：

1. 客户在微信内置浏览器完成 4 步流程并看到成功页；
2. 服务器 `inbox/` 出现原始文件与 `meta.json`（含解压密码），邮件（或 dry-run `.eml`）含附件与密码；
3. 缺字段、错误文件类型、超大文件被友好拒绝；
4. unittest 全部通过。

不在本期范围（Out of scope）：

- 对象存储 / 管理后台 / 客户名单管理；
- 与 `prototype/` 解析管线的自动串联（inbox 结构已预留文件 sha256，便于未来衔接）；
- 银行流水导出引导；
- 微信/支付宝真实界面截图素材（引导用结构化文字步骤 + CSS 样式呈现；`web/img/` 预留目录，用户可自行补充截图）；
- 静态文件层面的 HTTPS（由部署层反代承担，README 提供说明）。

## 2. 架构与目录

单体服务：FastAPI 一个进程同时托管静态 H5 与接收接口。前端无框架、无构建步骤（原生 HTML/CSS/JS，XMLHttpRequest 实现上传进度，兼容微信 WebView）。

```
collector/
├── server.py          # FastAPI 应用：静态托管、POST /api/submissions、限流、日志脱敏
├── storage.py         # 落盘留档、meta.json、文件名清洗、sha256
├── mailer.py          # 构建邮件 + SMTP 发送；SMTP_HOST 为空时 dry-run 生成 .eml 到 outbox/
├── config.py          # 读取 .env（环境变量），集中暴露配置项
├── requirements.txt   # fastapi、uvicorn、python-multipart（邮件用标准库 smtplib）
├── .env.example       # 配置模板（见 §6）
├── web/               # H5 前端
│   ├── index.html     # 4 步向导（单页，JS 切换步骤）
│   ├── consent.html   # 《授权协议》全文页（占位文本，用户自行修改）
│   ├── style.css      # 移动端优先，max-width 480px 居中
│   ├── app.js         # 步骤流转、表单校验、XHR 上传进度
│   └── img/           # 预留截图目录（本期为空）
├── tests/
│   ├── test_api.py
│   ├── test_storage.py
│   └── test_mailer.py
├── inbox/             # 留档（运行时生成，gitignore）
└── outbox/            # dry-run .eml 输出（运行时生成，gitignore）
```

## 3. 前端设计（web/index.html）

单页 4 步向导，步骤条显示进度，禁止跳步返回时丢失已填内容：

1. **首页**：标题与说明（品牌名留 `【机构名称】` 占位）、《授权协议》勾选框 + 链接（`consent.html` 新窗口打开）。未勾选时"开始"按钮禁用。
2. **选择平台**：两张卡片"微信 / 支付宝"，单选后进入对应引导。
3. **导出引导**（按平台显示结构化文字步骤）：
   - 微信：我 → 服务 → 钱包 → 账单 → 常见问题 → 下载账单 → 用于个人对账 → 填邮箱接收；解压密码在微信支付公众号 / 服务通知中查看。
   - 支付宝：我的 → 账单 → 开具交易流水证明 → 用于个人借款/签证等（非报销）→ 填邮箱接收；解压密码由短信下发。
   - 通用提示：iPhone 需先在邮件 App 中把附件存储到"文件"，再回到本页上传；安卓可直接从文件管理器选择。
   - 底部按钮"我已导出，去上传"。
4. **上传提交**：
   - 文件选择：`accept=".zip,.pdf,.xlsx,.xls"`，前端校验扩展名与大小（超过上限直接提示，不发请求）；选中后显示文件名与大小。
   - 表单：解压密码（必填，1–64 字符，右侧眼睛图标切换明文）、姓名（必填 2–30 字符）、手机号（必填，11 位 `1\d{10}` 校验）、业务单号（选填，≤32 字符）。
   - 提交：XHR 显示上传进度条；期间按钮禁用。服务端错误在表单上方整条显示（不区分内部细节）。
   - 成功页：显示提交编号、提示"已收到，请勿重复提交"、按钮"再提交一份"（回到步骤 2，保留姓名/手机号，清空文件与密码）。

界面文案全部中文；不调用任何微信 JS-SDK（纯链接打开即可用）。

## 4. 后端设计

### 4.1 接口

`POST /api/submissions`（`multipart/form-data`）：

| 字段 | 类型 | 必填 | 校验 |
| --- | --- | --- | --- |
| file | 文件 | 是 | 扩展名 zip/pdf/xlsx/xls；大小 ≤ MAX_UPLOAD_MB |
| password | 文本 | 是 | 1–64 字符 |
| platform | 文本 | 是 | `wechat` 或 `alipay` |
| name | 文本 | 是 | 2–30 字符 |
| phone | 文本 | 是 | `^1\d{10}$` |
| order_no | 文本 | 否 | ≤32 字符 |

- 成功 `200`：`{"ok": true, "submission_id": "..."}`。
- 校验失败 `422`：`{"ok": false, "error": "中文友好提示"}`。
- 触发限流 `429`：同上格式。

### 4.2 落盘（storage.py）

`inbox/YYYYMMDD/HHMMSS_{name}_{phone后4位}/` 目录内（同一秒重名时目录追加 `_2`、`_3` 序号）。`submission_id` 即该目录相对 `inbox/` 的路径（如 `20260928/143052_张三_1234`），接口返回与成功页展示都用它。`received_at` 为服务器本地时间的 ISO 8601 字符串。

- 原始上传文件：保留客户原始文件名，仅清洗（去路径分隔符与控制字符，保留中文名；重名追加序号）；
- `meta.json`：`submission_id、platform、name、phone、order_no、password、original_filename、file_size、sha256、received_at、ip_hash、mail_status`。

`mail_status` 由邮件模块回写：`sent / dry-run / failed: 原因`。邮件失败不影响接口返回成功（文件已留档），失败原因记日志与 meta。

### 4.3 邮件（mailer.py）

- 主题：`【流水采集】{name}-{平台}-{MMDD HHMM}`；正文包含姓名、手机、业务单号、平台、**解压密码**、文件名、大小、sha256、留档路径、提交时间。
- 附件：文件大小 ≤ MAIL_ATTACH_LIMIT_MB 时附带原文件；超过则只发摘要邮件（正文注明"文件超附件上限，已在服务器留档"）。
- SMTP_HOST 为空 → dry-run：把完整邮件（含附件）写成 `.eml` 放 `outbox/`，不联网。
- 发送使用标准库 `smtplib` + `email.mime`，SSL/STARTTLS 由 SMTP_SSL 配置决定，3 次重试。

### 4.4 限流与日志（server.py）

- 内存级每 IP 限流：默认 10 分钟窗口内最多 5 次提交（`RATE_LIMIT_PER_IP=0` 关闭），超限返回 429。进程重启即清零（可接受）。
- 日志脱敏：手机号 `138****1234`，密码只记前 2 位，IP 记 sha256 前 8 位；密码绝不写入任何日志全量。
- 静态资源仅从 `web/` 托管；`inbox/`、`outbox/` 不在静态目录内、不可被 URL 访问。不加 CORS（同源）。

## 5. 安全与合规

- 授权协议勾选是进入流程的前置条件；`consent.html` 为占位文本，包含【机构名称】【用途】【保存期限（建议 30 天）】【联系方式】标记，由用户上线前自行替换。
- 解压密码仅出现在邮件正文与 `meta.json`，不进 URL、不进前端成功页、日志脱敏。
- HTTPS、ICP 备案为部署事项，README 说明：本地 HTTP 跑通；生产用 nginx/caddy 反代 TLS；国内服务器域名需备案，否则微信内打开可能被拦截。
- `.gitignore`（仓库级新增）：`collector/inbox/`、`collector/outbox/`、`collector/.env`。

## 6. 配置（.env.example）

```
PORT=8000
INBOX_DIR=inbox
OUTBOX_DIR=outbox
MAX_UPLOAD_MB=100
MAIL_ATTACH_LIMIT_MB=45
SMTP_HOST=
SMTP_PORT=465
SMTP_SSL=true
SMTP_USER=
SMTP_PASS=
MAIL_FROM=
MAIL_TO=
RATE_LIMIT_PER_IP=5
RATE_LIMIT_WINDOW_MIN=10
```

路径配置相对于 `collector/` 目录解析。未配置 SMTP 时系统照常运行（dry-run 模式）。

## 7. 测试计划

unittest（与现有 `prototype` 的 `python -m unittest discover` 风格一致）：

- `test_storage.py`：文件名清洗（路径穿越、控制字符、中文名保留、重名追加序号）、目录布局、meta.json 字段完整、sha256 正确。
- `test_mailer.py`：邮件主题/正文包含密码与客户信息且仅出现一次、按大小决定是否带附件、dry-run 写出 `.eml` 且内容可解析。
- `test_api.py`：缺各必填字段、非法扩展名、超大小（临时调小上限）、非法手机号 → 422；合法提交（现场构造小 zip）→ 200 且 inbox/meta 落盘正确；连续提交超过限流阈值 → 429。

端到端人工验收：启动服务 → 浏览器走完 4 步 → 用 `template/微信支付交易明细证明...zip` 真实提交 → 核对 inbox 文件可解压、`.eml` 可用邮件客户端打开且附件密码齐全。

## 8. 部署要点（README 收录）

- 本地：`pip install -r collector/requirements.txt && python collector/server.py`（内部以 uvicorn 启动并读取 PORT）。
- 生产：同命令托管于 systemd/supervisor；前置 nginx/caddy 负责 TLS；提醒附件走 SMTP 的发件邮箱自身限额（QQ 邮箱约 50MB，超限部分依赖摘要邮件 + 留档）。
- 微信内传播使用已备案域名链接。

## 9. 已确认的决策记录

- 技术栈：Python FastAPI（与 prototype 同语言）。
- 交付：邮件附件 + 本地留档双通道。
- SMTP：暂不配置，dry-run 先行；配置项留好。
- 采集字段：姓名 + 手机号（必填）、业务单号（选填）、平台（流程自带）。
- 邮件失败不影响客户提交成功；超附件上限自动降级为摘要邮件。
