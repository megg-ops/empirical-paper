## 运行日志
### 开始时间: 2026-06-07 22:18:23
### 样本筛选
- 原始样本: 180 行
- 缺失值: 0（无缺失）
- 最终样本: 180 行

### 数据处理
- 对数变换: ln_employees = log(employees)
- 剔除极端值: 0 个样本被剔除（营收增长率超出均值±3σ）
- 虚拟变量: industry（基准=制造业）, region（基准=东部）

### 运行时间
- 开始: 2026-06-07 22:18:23
- 结束: 2026-06-07 22:18:24

### 输出文件
- tables/tab_01_desc_stats.md
- tables/tab_02_correlation.md
- tables/tab_03_baseline.md
- tables/tab_04_heterogeneity.md
- tables/tab_05_robustness.md
- figures/fig_01_scatter.png
- figures/fig_02_industry_comparison.png
- figures/fig_03_region_comparison.png
- results_summary.md
- results.json
- assets_manifest.json
- model_diagnostics.md
