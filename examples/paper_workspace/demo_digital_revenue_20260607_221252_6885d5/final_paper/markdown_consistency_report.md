# Markdown 验证报告

## 总览

- ✅ **格式检查**: pass
- ✅ **图片路径**: pass
- ✅ **图表编号**: pass
- ✅ **引用编号**: pass
- ✅ **公式语法**: pass
- ❌ **占位符**: block
- ✅ **LaTeX 残留**: pass
- ✅ **数字一致性**: pass
- ✅ **字数**: pass

## 详细发现

### 占位符

- 发现 8 个占位符

### 字数统计

- 估算字数：5748
- 目标：8000


## 结构化数字一致性

### 总体结论
❌ BLOCK

### 已匹配数字

| value | key | label |
|---|---|---|
| 5.724 | descriptive.revenue_growth_pct.mean | 营业收入增长率(%)均值 |
| 49.039 | descriptive.digital_score.mean | 数字化能力指数均值 |
| 5.428 | descriptive.firm_age_years.mean | 企业成立年限均值 |
| 5.273 | descriptive.rd_intensity_pct.mean | 研发投入强度(%)均值 |
| 6.093 | descriptive.marketing_intensity_pct.mean | 营销投入强度(%)均值 |
| 0.244 | descriptive.export_dummy.mean | 是否出口均值 |
| 0.132 | main.digital_score.coef | 数字化能力指数回归系数（模型3） |
| 0.337 | main.r2 | 模型3 R² |
| 0.277 | main.adj_r2 | 模型3 调整R² |
| 180 | main.n_obs | 样本量 |
| 0.132 | robustness.log_employees.digital_score.coef | 稳健性：对数变换员工后数字化能力系数 |
| 0.132 | robustness.trimmed.digital_score.coef | 稳健性：剔除极端值后数字化能力系数 |

### 缺失 must_report 数字

- descriptive.employees.mean: 108.161 (员工人数均值)
- descriptive.manager_edu_years.mean: 14.850 (管理者受教育年限均值)
- descriptive.financing_constraint.mean: 2.833 (融资约束程度均值)
- descriptive.labor_productivity.mean: 50.290 (人均产出指数均值)
- main.digital_score.se: 0.035 (数字化能力指数标准误（模型3）)
- main.digital_score.p: 0.000 (数字化能力指数p值（模型3）)


> 已提供 results.json，数字一致性以 results.json 为准；results_summary.md 不作为 blocking 数字真源。
