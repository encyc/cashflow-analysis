# 01 · 项目现状与交接

日期：2026-09-29。以下为代码核查结果，不将设计文档中的计划当作已实现功能。

## 1. 当前两条独立流程

```text
客户 → collector H5 → FastAPI 接收 → 本地 inbox 留档 → SMTP / outbox 邮件

人工把文件放入 template → Python 解析/合并/分析 → JSON + 独立 HTML → 本地浏览器
```

两条流程尚未自动连接，没有生产数据库、业务单状态管理、报告权限或稳定报告 API。

## 2. 目录与职责

| 路径 | 用途 | 接手方式 |
| --- | --- | --- |
| `prototype/build_report.py` | 微信 XLSX 解析、金额汇总与分类 | 复用计算逻辑；封装输入输出契约 |
| `prototype/pdf_parser.py` | 微信证明 PDF 表格提取与逐页检查 | 保留严格版式检查，扩充样本 |
| `prototype/alipay_parser.py` | 支付宝证明 PDF 提取与检查 | 同上，不代表支持支付宝全部账单格式 |
| `prototype/merge_reports.py` | PDF 证明身份配对、双平台合并 | 当前扫描特定文件名，改为业务任务显式传文件 |
| `prototype/scene_analysis.py`、`*_rules.json` | 分类、场景、画像规则 | 规则版本化，命中依据持久化 |
| `prototype/render_report.py`、`report.html`、`*-ui.js/css` | 独立 HTML 报告 | 复用样式和交互，生产改用鉴权数据接口 |
| `prototype/test_*.py`、`verify_*.py` | 算法与样本校验 | 回归基线，补充生产接口/权限/并发用例 |
| `collector/web/` | 上传引导与授权文案原型 | 改造业务单绑定、授权留痕、补件状态 |
| `collector/server.py`、`storage.py`、`mailer.py` | 上传、磁盘留档、邮件 | 仅采集原型；生产替换存储/任务/凭据策略 |
| `template/` | 本地真实样本 | 私有，不随源码交付；以受控方式提供验收样本 |
| `outputs/wechat-prototype/` | 带真实流水的 HTML、JSON | 私有，不放公共静态目录 |
| `docs/archive/` | 原型历史记录 | 仅内部参考，含历史样本统计 |
| `docs/handoff/` | 本次公司开发需求包 | 开发评审主入口 |
| `tmp/` | 本地临时验证与备份 | 非交付代码；未执行删除 |

## 3. 格式支持实况

| 格式 | 当前解析支持 | 一期目标 |
| --- | --- | --- |
| 微信个人对账 XLSX（现有表头） | 已验证一份 | 保留；昵称不能自动当实名认证 |
| 微信交易明细证明 PDF（文本表格） | 已验证三份 | 保留，按文件内容识别版式 |
| 支付宝交易明细证明 PDF（固定 8 列） | 已验证两份 | 保留，其他版式明确报不支持 |
| ZIP | 采集端接受，但没有解密解压到解析的流程 | 新增，内含格式仍受上述白名单限制 |
| XLS、支付宝 Excel、CSV | 采集端部分允许选择，解析未实现 | 一期前后端统一拒绝，并提示正确导出格式 |
| 扫描 PDF、图片、银行流水 | 未实现 | 提示重新导出可解析证明；后续评估 |

`build_report.py` 的 PDF 命令入口默认走微信解析，不是自动识别平台的通用 CLI。`merge_reports.py` 当前只匹配 `*20251001*.pdf`，每人要求一份微信和一份支付宝。两个脚本均不能直接拿来作为多用户生产接口。

## 4. 已有报告与关键限制

已具备整体交易组合图（笔数折线、收入/支出柱）、收支趋势、租赁渠道流水、网贷周期、回收、画像标签、交易对手、付款方式、账单筛选、分页与详情追溯。审核版已删除解析质量和来源覆盖展示区，但后台核验信息仍保留。

场景主要依赖关键词和规则，没有外部机构完整词库。营销红包不是借款，租赁支出不等于在租设备数量，回收收入不等于套现，信用卡支付不是未还余额。未知项保留原文和待核状态。单页打印仅打印当前页和已展开内容，不是全量导出。

现有 HTML 内嵌完整交易数据，拿到文件就能看到数据。生产禁止把这些文件放到公网静态目录，即使 URL 很长也不构成访问控制。

## 5. 已发现的产品化差距

- 上传声明成功只表示落盘；服务端没有核验授权勾选记录，也没有绑定可信业务单。
- 文件先整段读入内存再判断大小，未做完整内容检测、ZIP 资源限制和隔离执行。
- 解压密码在 `meta.json` 和邮件正文中明文保存，日志还保留前两位；生产应完全移除密码日志和邮件传输，采用短期加密凭据。
- 信任任意请求的 `X-Forwarded-For`；生产只信任公司网关写入的代理头，并使用共享限流。
- SMTP 同步调用并重试，会占用请求处理时间；生产改异步状态通知，默认不发附件。
- 缺少组织/业务单级权限、数据库事务、任务租约、幂等、版本锁定、自动清理和备份恢复。
- 根项目此前没有 Git 仓库；新增 `.gitignore` 只是防止今后误提交，不会撤销已经复制出去的数据。
- `collector/mailer.py` 使用顶层 `from config import Config`，包模式启动需整理导入路径；已验证的启动方式为在 `collector/` 内执行 `python server.py`。
- Excel 原型按交易单号去重，PDF 合并按来源位置去重。生产需统一为 04 中的事件和来源模型，不能直接照搬为全局订单唯一约束。

## 6. 本地运行与复现

在项目根目录使用独立虚拟环境；`prototype/requirements.txt` 记录本机验证过的直接依赖版本，不是全部传递依赖锁，也不代表已通过生产依赖审计。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r prototype/requirements.txt
.venv/bin/python -m unittest discover -s prototype -p 'test_*.py'
.venv/bin/python -m http.server 8765 --bind 127.0.0.1 --directory outputs/wechat-prototype
```

浏览器打开 `http://127.0.0.1:8765/combined.html`。没有私有输出文件的源码包不能直接展示真实报告，开发需准备授权测试材料或脱敏合成样本。

采集端本地启动：

```sh
cd collector
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
.venv/bin/python server.py
```

采集端现监听 `0.0.0.0:8000`，用于受控本地测试；不应直接对公网开放。SMTP 未配置时写本地 `.eml`，不要为演示配置真实邮箱。

在拥有现有私有样本时可运行 `build_report.py`、`merge_reports.py`；只刷新报告使用 `refresh_reports.py`。这些脚本会覆盖现有输出，请先备份。完整历史操作见 `docs/archive/2026-09-29-prototype-history.md`。

## 7. 本次核验记录

| 检查 | 2026-09-29 结果 |
| --- | --- |
| `prototype` 单元测试 | 22 项通过（Python 3.12） |
| `collector/tests` | 26 项通过（采集端现有 Python 3.14 虚拟环境） |
| `verify_report.py` | 原 Excel/PDF 金额、明细、来源、内嵌数据及 JS 语法通过 |
| `verify_combined.py` | 两人合并报告校验通过 |
| `verify_scenes.py` | 四份报告场景、画像及周期校验通过 |

采集测试出现 TestClient/httpx 弃用提示及部分上传文件未关闭警告，需在统一运行时、锁定依赖时解决。通用 Python 3.12 环境没有 FastAPI，首次采集测试未能加载 API 测试；换用采集端已有环境后通过。未开展生产部署、容量压测、真实手机兼容或灾备演练，不将上述通过等同生产就绪。
