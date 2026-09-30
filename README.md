# 个人流水分析项目

解析微信、支付宝账单，生成面向审核人员的个人流水分析报告。同一审核对象的两平台材料可合并，支持整体交易、租赁渠道、独立借还款/信用履约周期、薪资线索、重点交易、资金流向、回收、画像标签及明细追溯。

当前为已验证样本的本地原型，包含独立的客户采集 H5；两者尚未串联为生产系统。公司接入需求已经整理，**H5 仅用于客户上传，报告由公司 PC 审核平台查看**。

## 开发交接入口

先读 [公司系统接入需求包](docs/handoff/README.md)，再按职责查看：

- [项目现状与运行方式](docs/handoff/01-project-inventory.md)
- [平台与客户采集 H5 产品需求](docs/handoff/02-product-requirements.md)
- [生产架构与部署](docs/handoff/03-architecture-deployment.md)
- [数据库、身份与统计口径](docs/handoff/04-data-model.md)
- [接口、状态机与回调](docs/handoff/05-api-contract.md)
- [开发拆分、验收与待确认事项](docs/handoff/06-delivery-acceptance.md)

这是开发评审稿，接口、生产部署和数据库是待开发目标，不是现成服务。公司技术栈、业务主键、权限接口和保留期限需评审确认。

## 项目结构

```text
prototype/         解析、规则、合并、报告模板和回归检查
collector/         客户上传 H5、接收/本地留档/邮件原型
  web/             H5 静态页面
  tests/           采集端单元测试
docs/handoff/      本次开发需求与交接文档
docs/superpowers/  历史采集设计（生产目标以 handoff 为准）
docs/archive/      本地历史成果记录（含样本统计，不随源码提交）
template/          私有原始账单，不提交 Git
outputs/           私有报告和结构化结果，不提交 Git
tmp/               本地临时文件，不作为交付代码
```

现有运行目录保留，没有迁移原始账单或改变解析/展示逻辑。`.gitignore` 防止今后误提交私有材料；不代表已扫描或清除历史外发内容。

## 本地预览

已有生成结果时，在根目录运行：

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory outputs/wechat-prototype
```

打开 [合并报告目录](http://127.0.0.1:8765/combined.html)。HTML 包含完整流水，只在受控本地演示，不放公网静态目录。源码交接包默认没有真实样本和输出，需要另行准备授权测试材料。

依赖安装、重建、采集 H5 启动见 [项目现状](docs/handoff/01-project-inventory.md)。原型直接依赖固定在 `prototype/requirements.txt`；采集依赖见 `collector/requirements.txt`。生产交付需统一运行时并补齐传递依赖锁。

## 当前核验结果

2026-09-30：解析端 32 项单元测试、采集端 26 项单元测试通过；前端汇总测试（`node prototype/test_review_metrics.js`）、原报告、合并报告、场景及新增分析检查通过。采集端仍有依赖弃用与文件资源警告。未进行生产压测、部署和恢复演练，详见 [核验记录](docs/handoff/01-project-inventory.md)。

报告不提供信用评分、审批结论或已确认剩余债务。场景命中展示规则依据；缺失信息和待核渠道保留，不靠猜测补全。
