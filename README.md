# 微信 / 支付宝流水分析项目

> **交接给产品经理和 IT 的快速说明**｜更新：2026-09-30
>
> 本项目已完成流水解析、分析规则和报告展示原型。下一步由 IT 接手解析代码，结合公司技术栈适配、改造和部署，并完成客户上传 H5 与公司中台报告页面。

## 1. 这个项目做什么

客户上传自己导出的微信、支付宝流水，系统解析为结构化交易数据，将同一个人的两平台流水合并，生成供审核人员查看的报告。

报告目前包含：整体交易（笔数折线、收入/支出柱状图）、租赁渠道及流水、借还款周期、信用履约、回收交易、薪资收入线索、大额与夜间交易、资金流向、交易画像和标签，并支持筛选、明细下钻及原文件页/行追溯。

**本期只做微信和支付宝，暂不做银行流水。** 报告提供交易分析和核查线索，不自动给出信用评分或审批结论。

## 2. 已约定的交付分工

| 工作 | 本项目提供 | IT 负责落地 |
| --- | --- | --- |
| 客户上传 H5 | 上传引导、页面及交互原型，供参考 | 实现公司正式 H5，关联客户/业务单，完成上传、补件和状态反馈 |
| 流水解析与分析 | Python 解析、合并、统计和识别规则，附测试代码 | 接收代码，适配文件输入、任务调用和公司技术栈，封装为可部署服务 |
| 报告查看 | 已可演示的报告样式、模块、筛选与下钻交互 | 在**公司中台新增报告页面**，接入公司登录、权限和业务单入口 |
| 数据与部署 | 数据口径、接口及部署需求文档 | 原文件进入公司私有存储，结构化交易和报告结果进入公司数据库；完成部署、监控及维护 |

**H5 只用于客户上传流水，审核人员在公司中台查看报告。** `collector/` 是参考原型，正式 H5 由 IT 实现；其中旧的邮件投递流程不是生产接入要求。

目标流程：

```text
公司业务单 → 客户上传 H5 → 服务端接收 / 解析 / 按人合并
                         → 公司数据库与文件存储 → 中台报告页面
```

当前上传原型与解析原型仍是两条独立流程，尚未自动串联，也没有接入公司数据库、权限或生产环境。交付的是可复用代码和报告原型，IT 仍需完成上述产品化工作。

## 3. 文件怎么找

先看 `prototype/` 中的核心代码和 `docs/handoff/` 中的需求；`collector/` 可用于理解客户上传体验。

| 目录 / 文件 | 作用 |
| --- | --- |
| `prototype/` | 核心交接代码：解析、分析、合并、报告展示和测试 |
| `prototype/build_report.py` | 微信 Excel（XLSX）解析入口，同时提供收支、月度等基础汇总 |
| `prototype/pdf_parser.py` / `alipay_parser.py` | 分别解析微信、支付宝交易明细证明 PDF，保留来源定位并核对数据 |
| `prototype/merge_reports.py` | 按证明身份核对、合并同一人的微信和支付宝数据，生成个人报告与目录页 |
| `prototype/category_rules.json` / `scene_rules.json` | 消费分类、场景识别词表和规则版本 |
| `prototype/scene_analysis.py` / `review_analysis.py` | 场景、画像、借还款/信用周期，以及薪资、大额、夜间和资金流向分析 |
| `prototype/render_report.py` / `report.html` | 将分析数据装入报告模板，生成可独立打开的 HTML |
| `prototype/combined-ui.js`、`scene-ui.js/css`、`review-ui.js`、`review-metrics.js` | 合并报告展示、场景筛选、图表、前端汇总和明细下钻 |
| `prototype/refresh_reports.py` | 用已有解析 JSON 刷新报告和分析结果，无需重新读取 PDF；当前针对本地四份样稿 |
| `prototype/test_*.py`、`test_review_metrics.js`、`verify_*.py` | 规则和聚合测试、真实样本回归核对；部分核对脚本需本地样本及生成结果 |
| `prototype/requirements.txt` | 解析原型的 Python 直接依赖版本 |
| `collector/web/` | 客户上传 H5 页面原型及导出引导 |
| `collector/server.py`、`storage.py`、`mailer.py` | 原型上传接收、本地留档和邮件逻辑；仅供 IT 理解既有流程 |
| `docs/handoff/` | 给产品、开发和测试的正式交接需求包 |
| `template/` / `outputs/wechat-prototype/` | 本地原始流水 / 生成的 JSON、HTML 报告；不随 Git 源码提交 |

`prototype/compare_reports.py`、`vendor_review.json` 和 `docs/superpowers/` 是早期对照验证与设计材料，初次接手可跳过，不能作为当前功能清单。`tmp/`、`docs/archive/` 为本地临时或历史资料。

## 4. 产品经理先看什么

1. **先看报告效果**：有本地样稿时，按下一节打开报告，了解模块、筛选和明细下钻。
2. **再看产品范围**：[02 产品需求](docs/handoff/02-product-requirements.md) 与 [07 报告增强](docs/handoff/07-report-enhancements.md)。
3. **与 IT 拆分工作和验收**：[06 开发拆分与验收](docs/handoff/06-delivery-acceptance.md)。

IT 的详细入口：[01 代码现状与运行](docs/handoff/01-project-inventory.md)、[03 架构与部署](docs/handoff/03-architecture-deployment.md)、[04 数据与统计口径](docs/handoff/04-data-model.md)、[05 接口与状态](docs/handoff/05-api-contract.md)。完整索引见 [交接需求包](docs/handoff/README.md)。

这些文档中的生产接口、数据库和部署方案是待落地需求。最终技术选型由 IT 结合公司系统确定；本次明确采用公司中台页面展示报告。

## 5. 怎么快速看效果

如果交接材料中已单独提供生成报告，在项目根目录运行：

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory outputs/wechat-prototype
```

浏览器打开 [报告目录](http://127.0.0.1:8765/combined.html)，选择审核对象查看。它只是本地演示入口，报告 HTML 内含流水数据，不作为生产公开链接。

如果只有源码、没有 `outputs/`，暂时无法直接展示样稿，需要准备授权样本并生成报告。依赖安装和解析步骤见 [01 运行说明](docs/handoff/01-project-inventory.md)；H5 原型运行方法见 [collector/README.md](collector/README.md)。

## 6. IT 接手时需要知道的边界

- **格式有范围**：已验证微信 XLSX、微信和支付宝的文本版证明 PDF；扫描件、银行流水、支付宝 Excel 等未实现。ZIP 接收与解密解析尚未串联。
- **脚本需要适配**：合并脚本目前依赖特定样本文件名，刷新脚本使用固定报告路径；需要改为按业务任务传入文件和输出位置，不能直接充当多客户服务。
- **合并需要身份核对**：不能仅凭姓名或微信昵称自动合并；当前 PDF 配对已核对证明姓名与证件号码，生产还需关联公司的客户及业务单。
- **统计口径要保留**：金额使用整数分，保留原交易方向和退款、中性记录；同人合并不等于自动抵扣跨平台转账。

最近一次核验（2026-09-30）：解析端 32 项、采集端 26 项测试通过，前端汇总及四份报告的数据检查通过。生产部署、压测和公司系统联调尚未开展，详细记录见 01。

## 7. 打包交接建议

主交接包包含：`README.md`、`prototype/`、`collector/`、`docs/handoff/` 和 `.gitignore`。真实样本、生成报告可按公司内部数据管理要求单独提供，用于演示和验收。

直接压缩整个文件夹时，`.gitignore` **不会自动排除文件**。请排除 `.git/`、虚拟环境、缓存、`tmp/`、`.env`、`collector/inbox/`、`collector/outbox/`；`template/`、`outputs/` 和 `docs/archive/` 含真实流水或历史数据，不默认装入源码包。
