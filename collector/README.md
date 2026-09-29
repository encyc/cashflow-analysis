# collector — 客户流水采集 H5

> 本文说明本地采集原型。公司部署与接入目标请以 [开发需求包](../docs/handoff/README.md) 为准：需要替换明文密码/邮件附件流程，增加业务绑定、授权留痕、异步解析和公司存储。下文旧部署要点不构成生产上线验收标准。

客户在手机上（主要是微信内置浏览器）打开页面，按引导自行导出微信 / 支付宝流水，上传文件并填写解压密码；服务端把文件作为附件发到你指定的邮箱，同时在 `inbox/` 留档。设计与验收口径见 `docs/superpowers/specs/2026-09-28-collector-h5-design.md`。

## 本地运行

```sh
cd collector
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python server.py            # 监听 0.0.0.0:8000
```

浏览器打开 `http://127.0.0.1:8000`；手机与电脑同一局域网时，用 `http://<电脑局域网IP>:8000` 在手机上实测。

默认**未配置 SMTP = dry-run 模式**：不联网，邮件以 `.eml` 文件写入 `outbox/`，双击即可用邮件客户端打开预览（附件、密码齐全）。

## 配置

复制 `.env.example` 为 `.env` 并填写。关键字段：

| 字段 | 说明 |
| --- | --- |
| `SMTP_HOST/PORT/SSL/USER/PASS` | 发信邮箱。QQ 邮箱：`smtp.qq.com` / `465` / `true`，`PASS` 填设置里生成的**授权码**（不是登录密码） |
| `MAIL_TO` | 接收流水的邮箱 |
| `MAIL_FROM` | 发件人显示地址，留空则用 `SMTP_USER` |
| `MAX_UPLOAD_MB` | 上传上限，默认 100MB；改动后需同步 `web/app.js` 里的 `MAX_MB` |
| `MAIL_ATTACH_LIMIT_MB` | 超过此大小不发附件、改发摘要邮件（文件仍在服务器留档），默认 45MB |
| `RATE_LIMIT_PER_IP` | 每 IP 时间窗口内最大提交次数，0 关闭 |

## 留档结构

```
inbox/20260929/103052_张三_1234/
├── 微信支付交易明细证明(20250928-20260928)….zip   # 原始文件，保留原文件名
└── meta.json                                       # 客户信息、解压密码、sha256、mail_status
```

`mail_status` 取值：`sent` / `dry-run` / `failed: 原因`。邮件发送失败不影响客户提交成功，文件已在本地，按 meta 补发即可。

## 测试

```sh
cd collector
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

## 部署到服务器（要点）

1. 同上安装依赖，`python server.py` 托管于 systemd / supervisor 保持常驻；
2. 前置 nginx 或 caddy 做 HTTPS 反代（例如 caddy：`example.com { reverse_proxy 127.0.0.1:8000 }` 自动签发证书）；
3. 反代开启后，服务端已读取 `X-Forwarded-For` 做限流统计；
4. 国内服务器域名需 ICP 备案——**未备案域名在微信内打开可能被拦截**，这是客户主要入口，务必先备案；
5. 上线前替换 `web/index.html`、`web/consent.html` 中的【机构名称】【联系电话】等占位文本；
6. QQ 邮箱附件上限约 50MB；更大的文件依赖摘要邮件 + 服务器留档，或改配企业邮箱。

## 安全说明

- 解压密码只出现在邮件正文与 `meta.json`，不进 URL；日志中手机号打码、密码只留前 2 位、IP 只留哈希前 8 位；
- `inbox/`、`outbox/` 不在静态目录内，无法通过 URL 访问；
- 全程不接触客户微信 / 支付宝的登录密码与支付密码——只收客户自行导出的文件及其解压密码。
