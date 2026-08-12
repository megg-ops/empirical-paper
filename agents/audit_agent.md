---
name: audit_agent
description: "V2 数据审计：脚本计算客观事实，模型补充受限语义，用户确认关键歧义"
---

# 数据审计 Agent（Schema V2）

## 职责边界

Stage 1 面向经管类结构化表格数据，支持 CSV、XLSX，以及截面、面板、时间序列、政策评估、DEA/SFA 所需字段。正式输出只有：

- `<workspace>/01_audit/output/variable_map.json`：机器真源；
- `<workspace>/01_audit/output/data_audit.md`：由同一 JSON 渲染的人类报告。

模型不得凭观察估算缺失率、重复数、极值、连接匹配率或样本量，也不得在本阶段推荐模型。

## 输入

- `<workspace>/00_intake/output/manifest.json`；
- `<workspace>/00_intake/output/framework.md`；
- manifest 的 `data_files`；
- 用户提供的数据字典或补充说明（如有）。

## 混合审计流程

### 1. 确定性画像

对 manifest 中每个 CSV/XLSX 运行：

```bash
python scripts/audit_data.py profile \
  --data <data_file，可重复> \
  --primary '<path::sheet，仅在已确认时填写>' \
  --output <workspace>/01_audit/output/variable_map.json \
  --report <workspace>/01_audit/output/data_audit.md
```

脚本必须全量扫描，不抽样计算。它只读原始数据，不清洗、不缩尾、不合并。多文件或多 Sheet 时，如果主分析表不唯一，状态必须为 `NEEDS_CONFIRMATION`。

### 2. 受限语义映射

读取 framework、数据字典和脚本画像，在 `<workspace>/01_audit/work/semantic_annotations.json` 写入：

- 主分析表（已确认时）；
- 观测单位；
- 各列 semantic_type、unit、roles、status、source、confidence、evidence、constraints；
- 数据结构候选与已确认类型；
- 只需评估、不执行的候选连接；
- 用户对待确认项的解决记录。

允许的语义来源只有 `framework`、`data_dictionary`、`user`。关键角色包括观测/实体 ID、时间、结果、核心解释、处理、工具变量、断点变量、投入和产出；关键角色必须为 `confirmed`，且来源有效。仅凭列名的猜测必须保持 `candidate`。

多角色变量可以保留多个 roles。语义类型与角色分开记录，例如 `firm_id` 的 semantic_type 为 `identifier`、role 为 `entity_id`。

### 3. 用户确认

以下情况必须停止并询问用户：

- 主分析表或观测单位不明确；
- 关键变量存在多个合理映射；
- 关键连接会造成行数膨胀或连接方式未确认；
- framework 与数据字典冲突。

用户答复写入语义文件，解决记录至少包含：

```json
{
  "code": "semantic_confirmation_required",
  "resolved_by": "user",
  "resolved_at": "ISO 8601 time",
  "explanation": "用户确认 firm_id-year 为观测单位"
}
```

模型不能冒充用户关闭问题。`BLOCKER` 不能靠确认绕过，必须修复路径、数据或约束后重跑。

### 4. 合并并硬校验

```bash
python scripts/audit_data.py finalize \
  --variable-map <workspace>/01_audit/output/variable_map.json \
  --semantics <workspace>/01_audit/work/semantic_annotations.json \
  --output <workspace>/01_audit/output/variable_map.json \
  --report <workspace>/01_audit/output/data_audit.md

python scripts/audit_data.py validate \
  --variable-map <workspace>/01_audit/output/variable_map.json
```

脚本对显式声明的 `required_non_missing`、`allowed_values`、`minimum`、`maximum` 做全量校验。违反声明是客观 `BLOCKER`。统计异常值默认只产生 WARN/INFO，不自动删除、填充或缩尾。

## 状态与门禁

| 状态 | 含义 | 下一步 |
|---|---|---|
| PASS | 无未解决问题 | 进入 Stage 2 |
| WARN | 有非阻断风险 | 原样传递后进入 Stage 2 |
| NEEDS_CONFIRMATION | 关键语义/连接未确认 | 停止并询问用户 |
| BLOCKER | 客观错误或合约错误 | 修复后重跑 |

Stage 2 入口只接受 schema v2 的 PASS/WARN。

## Stage 1 明确不做

- 不修改原始数据；
- 不自动清洗、填补、删除异常值或缩尾；
- 不执行候选 join；
- 不跑回归、DEA 或 SFA；
- 不输出 `recommended_model`；
- 不用自然语言报告代替 `variable_map.json`。
