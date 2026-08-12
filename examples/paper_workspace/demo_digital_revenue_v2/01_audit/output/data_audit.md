# 数据审计报告（Schema V2）

- 状态：**WARN**
- 扫描方式：全量确定性扫描
- 原始数据：只读，未修改

## 数据表

| 文件 | Sheet | 行数 | 列数 | 完全重复行 |
|---|---|---:|---:|---:|
| examples/demo_case/data.xlsx | data | 180 | 13 | 0 |
| examples/demo_case/data.xlsx | variable_dictionary | 13 | 5 | 0 |
| examples/demo_case/data.xlsx | README | 15 | 2 | 1 |

## 主分析表与观测单位

- 主分析表：`examples/demo_case/data.xlsx::data`
- 观测单位：企业

## 变量画像与语义映射

| 列 | 存储类型 | 缺失 | 唯一值 | 语义类型 | 角色 | 状态 |
|---|---|---:|---:|---|---|---|
| firm_id | string | 0 | 180 | identifier | observation_id, entity_id | confirmed |
| industry | string | 0 | 5 | nominal | control, fixed_effect, group | confirmed |
| region | string | 0 | 4 | nominal | control, fixed_effect, group | confirmed |
| revenue_growth_pct | float | 0 | 168 | continuous | outcome | confirmed |
| digital_score | float | 0 | 153 | continuous | predictor | confirmed |
| firm_age_years | integer | 0 | 17 | count | control | confirmed |
| employees | integer | 0 | 111 | count | control | confirmed |
| rd_intensity_pct | float | 0 | 162 | proportion | control | confirmed |
| marketing_intensity_pct | float | 0 | 153 | proportion | control | confirmed |
| manager_edu_years | integer | 0 | 6 | count | control | confirmed |
| export_dummy | integer | 0 | 2 | binary | control | confirmed |
| financing_constraint | integer | 0 | 5 | ordinal | control | confirmed |
| labor_productivity | float | 0 | 172 | continuous | auxiliary | confirmed |

## 数据质量与待确认事项

- **WARN** `duplicate_rows`：存在完全重复行；证据：`{"source_path": "examples/demo_case/data.xlsx", "sheet": "README", "count": 1}`

## 方法条件（不作模型推荐）

- panel_structure：字段条件不完整
- policy_evaluation：字段条件不完整
- instrumental_variables：字段条件不完整
- regression_discontinuity：字段条件不完整
- efficiency_analysis：字段条件不完整

> 具体候选模型、推荐模型和解释边界由 Stage 2 决定。
