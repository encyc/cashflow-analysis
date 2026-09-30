# 04 · 数据库、身份与统计口径

本章为逻辑模型，由公司 DBA 转成现用关系数据库 DDL。不要未经评审更换公司数据库。所有业务表带内部随机 `id`、`org_id`、创建/更新时间；关联表按表中要求增加唯一键和外键。业务主数据仍归公司系统。

## 1. 存储边界

| 存储 | 保存内容 | 禁止做法 |
| --- | --- | --- |
| 公司关系数据库 | 业务绑定、授权、文件元数据、任务、交易、汇总、命中、报告版本、审计 | 只保存 HTML URL；用 float 存金额 |
| 公司私有对象存储 | 原始文件、必要的不可变结果快照 | 公共读、用姓名/证件作为对象路径、公开原件 URL |
| 短期凭据存储 | 解压/打开密码密文及 TTL/密钥引用 | 明文数据库、邮件、日志、长期保留 |
| Worker 临时目录 | 隔离解压内容和中间产物 | 长期留存、多个客户混用目录 |

逐笔交易和核心汇总需要结构化落库；JSON 可保存可变展示字段和快照，但不替代可索引的业务、时间、方向、金额、平台和来源列。

## 2. 逻辑表

| 表 | 关键字段 | 约束/说明 |
| --- | --- | --- |
| `analysis_case` | `business_id, subject_id, required_platforms, expected_start/end, input_revision, current_report_id, status` | 唯一 `(org_id,business_id,subject_id)`；一期一业务单一个审核主体 |
| `collection_session` | `case_id, token_hash, expires_at, revoked_at, verified_subject_id, last_seen_at` | 令牌仅存摘要；客户绑定由服务端决定 |
| `consent_record` | `case_id, subject_id, session_id, policy_version, policy_hash, agreed_at, revoked_at, verification_ref` | 留存文本版本和证据引用；有效同意必须可核验 |
| `source_file` | `case_id, submission_id, platform_declared/detected, object_key, sha256, byte_size, format_version, period_start/end, parent_archive_id, status, identity_status, received_at` | 文件不可变；原文件名按隐私规则保存；ZIP 与内部文件均可溯源 |
| `file_credential` | `source_file_id, encrypted_secret, key_ref, expires_at, destroyed_at` | 独立权限；清理时删除密文，不只改状态 |
| `parse_artifact` | `source_file_id, parser_version, schema_version, status, checks_summary, identity_evidence_ref, record_count` | 唯一 `(source_file_id,parser_version,schema_version)`；重试同版本不重复产物 |
| `transaction_event` | `parse_artifact_id, platform, order_no, merchant_order_no, occurred_at, direction, amount_cents, kind, merchant, item, payment, status_raw, note, raw_direction, refund_indicator` | `id` 是独立事件 ID；订单号文本且不唯一；源文本加密/脱敏按公司策略 |
| `transaction_source` | `transaction_id, source_file_id, source_locator, page_no, sheet_name, row_no` | 唯一 `(parse_artifact_id,source_locator)`（关联中冗余产物 ID）；定位不能为空，可用稳定页/表/行编码 |
| `report_version` | `case_id, version_no, input_revision, status, cutoff_at, parser_versions, category_rule_version, scene_rule_version, metric_version, schema_version, renderer_version, input_digest, snapshot_key, generated_at, ready_at` | 唯一 `(case_id,version_no)`；同逻辑请求用幂等键，不以排序文件名命名 |
| `report_source` | `report_id, source_file_id, parse_artifact_id, platform` | 唯一 `(report_id,platform)`；一期每平台一个有效账单；保存全部输入版本 |
| `report_transaction` | `report_id, transaction_id, display_seq, category, category_rule_id, category_evidence` | 唯一 `(report_id,transaction_id)`；报告明细集合与分类固定，规则升级不改原交易 |
| `report_metric` | `report_id, metric_key, dimension_key, count_value, amount_cents, payload` | 唯一 `(report_id,metric_key,dimension_key)`；存总览、月度、周期等 |
| `scene_match` | `report_id, transaction_id, scene, channel_key, channel_label, event_type, rule_id, rule_version, evidence, inferred` | 命中依据不只有标签；可多条依据但指标按事件去重计数 |
| `profile_match` | `report_id, transaction_id, tag_key, evidence, rule_version` | 一笔可有多个画像；标签总额不可相加当总额 |
| `processing_job` | `case_id, source_file_id/report_id, input_revision, job_type, status, attempt, next_attempt_at, lease_owner, lease_expires_at, error_code, idempotency_key` | 唯一逻辑幂等键；阶段重试不覆盖源记录 |
| `review_record` | `case_id, report_id, adopted_by, adopted_at, comment, verification_ref` | 审核采用明确版本；修改追加历史，不改交易 |
| `outbox_event` | `event_id, event_type, aggregate_id, payload, next_attempt_at, attempts, delivered_at` | 事件 ID 唯一，和 READY 发布事务写入 |
| `audit_log` | `actor_id, action, case_id, report_id, resource_id, outcome, reason, trace_id, occurred_at` | 追加写；不存密码/全量流水正文 |
| `deletion_request` | `case_id, scope, requested_by, approved_by, status, hold_reason, completed_at` | 追踪数据库、对象、缓存、任务及备份到期处理 |

任务尝试的详细阶段历史可独立 `job_attempt` 表，或在任务日志服务中通过稳定 `job_id` 留存。身份确认/单平台例外必须有不可变业务决策记录，可扩展 `review_record` 的决策类型，不用一段自由文本直接替代状态控制。

建议索引：`analysis_case(org_id,status,updated_at)`；`source_file(case_id,status)`；`processing_job(status,next_attempt_at)`；`transaction_event(parse_artifact_id,occurred_at,id)`；`report_transaction(report_id,display_seq)`；场景/画像 `(report_id,scene或tag_key,transaction_id)`；`outbox_event(delivered_at,next_attempt_at)`。实施 DDL 时用执行计划验证，不预建所有组合索引。

## 3. 身份与业务单归属（P0）

1. 业务单的 `subject_id` 来源于公司系统，不接受前端任意改写。客户在 H5 填的姓名、手机号只作补充联系信息。
2. 有完整身份的证明材料：提取姓名/证件，在受控内存中和公司身份服务校验，两平台身份须一致。文件文字一致只能证明材料字段一致，不代表官方真伪认证。
3. 昵称版 XLSX 没有可信证件信息：标记 `UNVERIFIED`，必须有权限人员核对公司身份并留理由/证据后才能用于正式报告。禁止凭昵称相同自动合并。
4. 证件明确冲突：`MISMATCH`，阻断。补正确材料或由公司业务系统纠正归属后新建修订；不能一键跳过冲突。
5. 若需保存可比对标识，使用公司身份服务的稳定匿名标识，或带密钥 HMAC 的证件指纹并记录密钥版本；不能只做普通 SHA256 当成匿名化。证件原文无必要不入本项目库，严禁进入普通报告/日志。

## 4. 重复上传、重复事件和补件

- 同一逻辑上传重试：以 `(org_id,case_id,idempotency_key)` 返回原受理结果。相同键但内容摘要不同返回冲突。
- 同一业务单同平台同字节文件：服务端算 SHA256，复用原文件/解析产物引用，记录再次提交，不增加交易笔数。跨客户不向用户暴露文件命中情况。
- 不同字节文件但账期重叠：一期选择一个作为该平台当前材料，另一份标“未采用/已替换”，不把两份直接叠加。
- 交易事件不以订单号唯一：付款、退款、取消可能共用订单号且金额/方向不同，必须保留。
- 同来源位置重复提取且字段相同才可去重；相同位置字段冲突则失败。不仅凭时间、金额、名称去重。
- 微信转支付宝等跨平台流转暂不自动抵扣，保留各平台原始统计；本期报告不宣称个人资金净新增或跨账户净现金流。
- 报告 `input_digest` 由有序文件摘要、产物版本、确认决定、统计/规则版本构成，不含解压密码。重复生成相同输入/版本可返回已有报告；补件或换规则形成新版本。

## 5. 字段约定与现有 JSON 映射

| 当前字段 | 生产字段 | 规则 |
| --- | --- | --- |
| `records[].row` | `display_seq` | 当前报告序号，不能当跨报告交易主键 |
| `id` / `merchant_id` | `order_no` / `merchant_order_no` | 文本，保留前导零、长串和后缀 |
| `time` | `occurred_at` | 北京时间解释，持久化含明确时区；API ISO8601 `+08:00` |
| `cents` | `amount_cents` | 非负整数分，数据库 BIGINT；API 用十进制字符串避免 JS 大整数损失 |
| `direction` | `INCOME/EXPENSE/NEUTRAL` | 单独字段表示方向，不用金额负号编码；已确认模板中的“其他/中性交易/不计收支/”映射 NEUTRAL，保留原文，未知值拒绝 |
| `refund` / `refund_indicator` | `refund_indicator` + 退款归类 | 原型两者意义并不完全相同；同时保留依据和原方向 |
| `source_page/source_row/source_ref` | `transaction_source` | 保存原位置，显示序号改变不影响来源 |
| `category/rule`、`insights.matches` | 分类/场景/画像命中 | 保存规则版本、证据，禁止只存展示标签 |
| `meta/summary/monthly/checks` | 报告/指标/核验产物 | 核验数据仍存后台，普通报告不恢复技术核验模块 |

数量用整数；缺字段用 `null`，明确的零用 0/`"0"`，不能互换。字符串按 Unicode 保存，不改写原商户文字。前端仅做格式化，人民币展示两位小数；聚合、金额排序由后端完成。`schema_version` 控制兼容性，不依赖 HTML 内全局变量 D 作为正式接口。

## 6. 统计口径（metric-v1 目标契约）

| 指标 | 计算方式/边界 |
| --- | --- |
| 总笔数 | 采用明细集合事件数，含收入、支出、中性/不计收支事件 |
| 收入/支出 | 分别累计对应方向金额；零金额事件也计笔数 |
| 不计收支 | 微信其他/中性、支付宝不计收支独立汇总，不加进收入或支出 |
| 原始收支差额 | 收入减支出；不能命名为已去重净现金流或可支配收入 |
| 收入退款 | 仅对收入方向且退款依据成立的事件求和；收入含退款需标注 |
| 不计收支退款线索 | 单独计数/金额，不从原始支出直接抵扣，不与收入退款混算 |
| 非退款收入 | 原始收入减收入退款；不等于工资或稳定收入 |
| 月度图 | 月分组；笔数含中性，收/支柱只含各自方向，空月补零 |
| 完整月份 | 所采用平台材料均完整覆盖的自然月；用材料声明覆盖区间而非第一/末笔交易判断 |
| 月均 | 完整月份对应合并金额/完整月份数量；无完整月返回 null。输出分按 Decimal HALF_UP，记录 metric_version |
| 借还款 / 信用履约周期 | 截止日 D，近 N 天为北京时间 D-(N-1) 的 00:00:00 至 D 次日 00:00:00 前，并受材料实际截止时刻限制 |
| 自定义日期 | UI 双端日期含首尾日，服务端转 `[开始日00:00,结束日次日00:00)` 并裁剪到报告范围 |
| 渠道 | 原文和已验证别名分组，不把所有待核商户合成一个已确认机构；数量为渠道分组数 |
| 场景/画像 | 主要场景优先级为租赁→明确借贷产品→信用产品→其他借还款文字/机构→回收；画像多标签可重叠，分别下钻 |

窗口 7/15/30/90/180 天相互重叠，不能求和；截止日固定为该报告材料的截止日，不能随查看日期移动。渠道/整体交易跟随场景自定义日期，借还款与信用履约周期仅跟随平台并显示窗口锚点。无某平台数据不补成已覆盖的零。

注意与原型差别：原型部分完整月逻辑只比较日期，月均使用 Python `round`。生产 metric-v1 应按声明精确时间验证整月，材料某月末提前导出不能当完整月份；金额舍入统一 Decimal HALF_UP。必须增加月底截止、0.5 分均值等边界用例，记录版本，不静默改旧报告。

## 7. 原子发布、历史和生命周期

核验类型必须区分：Excel 可核对导出文件列出的笔数/金额；现有 PDF 主要以不同提取路径核对页内笔数与金额，若文件未提供官方汇总，就不能声称已核对官方总额。两种检查都不证明账单真伪。后台保存核验方法、参考值、计算值和失败位置；没有源汇总的字段显示“无源汇总可比”，不能伪造通过项。

报告 READY 前必须校验明细数量、金额、指标、命中引用与输入摘要一致。明细/指标可以分批暂存，但读取接口只返回已发布版本。数据和 READY 指针、通知 outbox 同事务提交；数据库失败则全部不发布。

升级规则默认只影响新报告。重跑旧材料需显式创建新版本；旧版本不被覆盖，审核采用记录固定 `report_id`。保存 parser、规则、schema、metric、renderer 版本及实际输入文件引用，才能解释历史结果。

上线前由公司确定原文件、交易、报告、授权证据、审计、备份各自保存期限和负责人；没有确认不能默认永久存储。到期或获准删除：撤销访问和任务→清除在线数据/对象/缓存/凭据→记录删除结果→按备份策略到期清除。备份恢复后先重放删除清单，防止已删除客户数据重新可见；有合法留存要求时通过公司审批记录 hold，不自行判断法律义务。

## 9. 微信支付宝报告增强数据

新增 `insights.credit_periods` 与 `insights.review`；后者包含 salary、large、night、flows，聚合均保存原记录 ID 集合，金额仍为整数分。薪资保留关键词证据、月度及按平台/对方原文分组来源；报告发布需同时固定分类与 review 规则版本。生产数据库应把这些衍生结果与 report_id、rule_version 关联，不能覆盖原交易方向。完整计算边界、空值和下钻要求见 [07](07-report-enhancements.md)。
