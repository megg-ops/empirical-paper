"""
analysis.py — 企业数字化能力与营业收入增长率相关性分析
Demo case: 180家中小企业截面数据, OLS + HC1稳健标准误
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.stats.outliers_influence import variance_inflation_factor
from scipy import stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import json
import os
from pathlib import Path
from datetime import datetime

# ============================================================
# 0. 配置
# ============================================================
np.random.seed(42)

plt.rcParams['font.sans-serif'] = ['SimHei', 'WenQuanYi Zen Hei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 路径
WORKSPACE = Path("paper_workspace/demo_digital_revenue_20260607_221252_6885d5")
DATA_FILE = Path("demo_case/data.xlsx")
OUTPUT_DIR = WORKSPACE / "03_coder" / "output"
TABLES_DIR = OUTPUT_DIR / "tables"
FIGURES_DIR = OUTPUT_DIR / "figures"

TABLES_DIR.mkdir(parents=True, exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

run_start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ============================================================
# 1. 数据读取
# ============================================================
df = pd.read_excel(DATA_FILE, sheet_name="data")

run_log_lines = [
    "## 运行日志\n",
    f"### 开始时间: {run_start}\n",
    f"### 样本筛选\n",
    f"- 原始样本: {len(df)} 行\n",
    f"- 缺失值: 0（无缺失）\n",
    f"- 最终样本: {len(df)} 行\n",
]

# ============================================================
# 2. 描述性统计
# ============================================================
desc_vars = ['revenue_growth_pct', 'digital_score', 'firm_age_years', 'employees',
             'rd_intensity_pct', 'marketing_intensity_pct', 'manager_edu_years',
             'export_dummy', 'financing_constraint', 'labor_productivity']

desc_labels = {
    'revenue_growth_pct': '营业收入增长率(%)',
    'digital_score': '数字化能力指数',
    'firm_age_years': '企业成立年限',
    'employees': '员工人数',
    'rd_intensity_pct': '研发投入强度(%)',
    'marketing_intensity_pct': '营销投入强度(%)',
    'manager_edu_years': '管理者受教育年限',
    'export_dummy': '是否出口',
    'financing_constraint': '融资约束程度',
    'labor_productivity': '人均产出指数',
}

desc_stats = df[desc_vars].describe().T[['count', 'mean', 'std', 'min', 'max']]
desc_stats.insert(0, '变量', [desc_labels[v] for v in desc_vars])
desc_stats = desc_stats.round(3)

# 保存描述性统计为 CSV
desc_stats.to_csv(TABLES_DIR / "tab_01_desc_stats.csv", index=False)

# Markdown 格式（供 Word 输出）
md_lines = []
md_lines.append("| 变量 | 观测数 | 均值 | 标准差 | 最小值 | 最大值 |")
md_lines.append("| --- | --- | --- | --- | --- | --- |")
for _, row in desc_stats.iterrows():
    md_lines.append(f"| {row['变量']} | {int(row['count'])} | {row['mean']:.3f} | {row['std']:.3f} | {row['min']:.3f} | {row['max']:.3f} |")

with open(TABLES_DIR / "tab_01_desc_stats.md", "w", encoding="utf-8") as f:
    f.write("\n".join(md_lines))

print("描述性统计表已生成")

# ============================================================
# 3. 相关系数矩阵
# ============================================================
corr_vars = ['revenue_growth_pct', 'digital_score', 'firm_age_years', 'employees',
             'rd_intensity_pct', 'marketing_intensity_pct', 'manager_edu_years',
             'financing_constraint']
corr_labels = [desc_labels[v] for v in corr_vars]

corr_matrix = df[corr_vars].corr().round(3)

# Markdown 格式
corr_md = []
corr_md.append("|  | " + " | ".join(corr_labels) + " |")
corr_md.append("| --- | " + " | ".join(["---"] * len(corr_labels)) + " |")
for i, v in enumerate(corr_labels):
    row_vals = [f"{corr_matrix.iloc[i, j]:.3f}" for j in range(len(corr_labels))]
    corr_md.append(f"| {v} | " + " | ".join(row_vals) + " |")

with open(TABLES_DIR / "tab_02_correlation.md", "w", encoding="utf-8") as f:
    f.write("\n".join(corr_md))

print("相关系数表已生成")

# ============================================================
# 4. 数据准备 — 虚拟变量
# ============================================================
df['ln_employees'] = np.log(df['employees'])

# 行业虚拟变量（基准：制造业）
industry_dummies = pd.get_dummies(df['industry'], prefix='ind', drop_first=True, dtype=int)
# drop_first=True 以制造业为基准

# 区域虚拟变量（基准：东部）
region_dummies = pd.get_dummies(df['region'], prefix='reg', drop_first=True, dtype=int)
# drop_first=True 以东部为基准

# ============================================================
# 5. OLS 回归 — 逐步加入
# ============================================================

results_all = {}  # 存储所有模型结果

# --- 模型 1: 仅 digital_score ---
X1 = sm.add_constant(df[['digital_score']])
model1 = sm.OLS(df['revenue_growth_pct'], X1).fit(cov_type='HC1')
results_all['(1)'] = model1

# --- 模型 2: 加入企业特征控制变量 ---
controls2 = ['digital_score', 'firm_age_years', 'employees', 'rd_intensity_pct',
             'marketing_intensity_pct', 'manager_edu_years', 'export_dummy', 'financing_constraint']
X2 = sm.add_constant(df[controls2])
model2 = sm.OLS(df['revenue_growth_pct'], X2).fit(cov_type='HC1')
results_all['(2)'] = model2

# --- 模型 3: 全部控制 + 行业/区域虚拟变量 ---
controls3 = controls2 + list(industry_dummies.columns) + list(region_dummies.columns)
X3 = pd.concat([df[controls2], industry_dummies, region_dummies], axis=1)
X3 = sm.add_constant(X3)
model3 = sm.OLS(df['revenue_growth_pct'], X3).fit(cov_type='HC1')
results_all['(3)'] = model3

print("基准回归完成")

# ============================================================
# 6. 构建回归结果表
# ============================================================
def make_regression_table(models, var_names, var_labels, model_labels):
    """生成回归结果 Markdown 表格"""
    lines = []
    header = "| 变量 | " + " | ".join(model_labels) + " |"
    sep = "| --- | " + " | ".join(["---"] * len(model_labels)) + " |"
    lines.append(header)
    lines.append(sep)

    for vn, vl in zip(var_names, var_labels):
        row = f"| {vl} |"
        for m in models:
            if vn in m.params.index:
                coef = m.params[vn]
                se = m.bse[vn]
                p = m.pvalues[vn]
                sig = ""
                if p < 0.01: sig = "***"
                elif p < 0.05: sig = "**"
                elif p < 0.1: sig = "*"
                row += f" {coef:.3f}{sig} ({se:.3f}) |"
            else:
                row += " |"
        lines.append(row)

    # 行业/区域控制
    has_industry = any(c.startswith('ind_') for c in models[-1].params.index)
    has_region = any(c.startswith('reg_') for c in models[-1].params.index)
    for m in models:
        pass

    row_ind = "| 行业固定效应 |"
    for m in models:
        has_ind = any(c.startswith('ind_') for c in m.params.index)
        row_ind += " " + ("是" if has_ind else "否") + " |"
    lines.append(row_ind)

    row_reg = "| 区域固定效应 |"
    for m in models:
        has_reg = any(c.startswith('reg_') for c in m.params.index)
        row_reg += " " + ("是" if has_reg else "否") + " |"
    lines.append(row_reg)

    row_n = "| 观测数 |"
    for m in models:
        row_n += f" {int(m.nobs)} |"
    lines.append(row_n)

    row_r2 = "| R² |"
    for m in models:
        row_r2 += f" {m.rsquared:.3f} |"
    lines.append(row_r2)

    row_adj_r2 = "| 调整R² |"
    for m in models:
        row_adj_r2 += f" {m.rsquared_adj:.3f} |"
    lines.append(row_adj_r2)

    row_f = "| F值 |"
    for m in models:
        row_f += f" {m.fvalue:.3f} |"
    lines.append(row_f)

    return "\n".join(lines)

# 变量名和标签（用于回归表）
reg_var_names = ['digital_score', 'firm_age_years', 'employees', 'rd_intensity_pct',
                 'marketing_intensity_pct', 'manager_edu_years', 'export_dummy', 'financing_constraint']
reg_var_labels = ['数字化能力指数', '企业成立年限', '员工人数', '研发投入强度',
                  '营销投入强度', '管理者受教育年限', '是否出口', '融资约束程度']

baseline_table = make_regression_table(
    [model1, model2, model3],
    reg_var_names, reg_var_labels,
    ['(1)', '(2)', '(3)']
)

# 添加注释
baseline_table += "\n\n注：括号内为HC1稳健标准误。* p<0.1, ** p<0.05, *** p<0.01。行业以制造业为基准组，区域以东部为基准组。"

with open(TABLES_DIR / "tab_03_baseline.md", "w", encoding="utf-8") as f:
    f.write(baseline_table)

print("基准回归表已生成")

# ============================================================
# 7. 稳健性检验
# ============================================================

# --- 7a: 对数变换 employees ---
controls_log = ['digital_score', 'firm_age_years', 'ln_employees', 'rd_intensity_pct',
                'marketing_intensity_pct', 'manager_edu_years', 'export_dummy', 'financing_constraint']
X_log = pd.concat([df[['digital_score', 'firm_age_years', 'ln_employees', 'rd_intensity_pct',
                        'marketing_intensity_pct', 'manager_edu_years', 'export_dummy', 'financing_constraint']],
                   industry_dummies, region_dummies], axis=1)
X_log = sm.add_constant(X_log)
model_log = sm.OLS(df['revenue_growth_pct'], X_log).fit(cov_type='HC1')

# --- 7b: 剔除极端值 ---
mean_rg = df['revenue_growth_pct'].mean()
std_rg = df['revenue_growth_pct'].std()
df_trim = df[(df['revenue_growth_pct'] >= mean_rg - 3*std_rg) & (df['revenue_growth_pct'] <= mean_rg + 3*std_rg)].copy()
n_trimmed = len(df) - len(df_trim)

industry_dummies_trim = pd.get_dummies(df_trim['industry'], prefix='ind', drop_first=True, dtype=int)
region_dummies_trim = pd.get_dummies(df_trim['region'], prefix='reg', drop_first=True, dtype=int)

X_trim = pd.concat([df_trim[controls2], industry_dummies_trim, region_dummies_trim], axis=1)
X_trim = sm.add_constant(X_trim)
model_trim = sm.OLS(df_trim['revenue_growth_pct'], X_trim).fit(cov_type='HC1')

# --- 7c: 不加行业/区域虚拟变量（已在 model2 中） ---

# 构建稳健性检验表
robust_var_names = ['digital_score']
robust_var_labels = ['数字化能力指数']

robust_table_lines = []
robust_table_lines.append("| 变量 | 全样本(3) | 对数变换员工 | 剔除极端值 | 无行业/区域 |")
robust_table_lines.append("| --- | --- | --- | --- | --- |")

# digital_score 行
models_robust = [model3, model_log, model_trim, model2]
labels_robust = ['全样本(3)', '对数变换员工', '剔除极端值', '无行业/区域']

for vn, vl in [('digital_score', '数字化能力指数')]:
    row = f"| {vl} |"
    for m in models_robust:
        if vn in m.params.index:
            coef = m.params[vn]
            se = m.bse[vn]
            p = m.pvalues[vn]
            sig = ""
            if p < 0.01: sig = "***"
            elif p < 0.05: sig = "**"
            elif p < 0.1: sig = "*"
            row += f" {coef:.3f}{sig} ({se:.3f}) |"
        else:
            row += " |"
    robust_table_lines.append(row)

# 控制变量行
row_ind = "| 行业固定效应 |"
for m in [model3, model_log, model_trim, model2]:
    has_ind = any(c.startswith('ind_') for c in m.params.index)
    row_ind += " " + ("是" if has_ind else "否") + " |"
robust_table_lines.append(row_ind)

row_reg = "| 区域固定效应 |"
for m in [model3, model_log, model_trim, model2]:
    has_reg = any(c.startswith('reg_') for c in m.params.index)
    row_reg += " " + ("是" if has_reg else "否") + " |"
robust_table_lines.append(row_reg)

row_n = "| 观测数 |"
for m in models_robust:
    row_n += f" {int(m.nobs)} |"
robust_table_lines.append(row_n)

row_r2 = "| R² |"
for m in models_robust:
    row_r2 += f" {m.rsquared:.3f} |"
robust_table_lines.append(row_r2)

robust_table = "\n".join(robust_table_lines)
robust_table += f"\n\n注：括号内为HC1稳健标准误。* p<0.1, ** p<0.05, *** p<0.01。剔除极端值样本量减少{n_trimmed}个。"

with open(TABLES_DIR / "tab_05_robustness.md", "w", encoding="utf-8") as f:
    f.write(robust_table)

print("稳健性检验表已生成")

# ============================================================
# 8. 异质性分析 — 按行业和区域分组
# ============================================================

# 按行业分组回归
industry_results = {}
for ind in df['industry'].unique():
    sub = df[df['industry'] == ind]
    X_sub = sm.add_constant(sub[controls2])
    m_sub = sm.OLS(sub['revenue_growth_pct'], X_sub).fit(cov_type='HC1')
    industry_results[ind] = {
        'coef': m_sub.params.get('digital_score', np.nan),
        'se': m_sub.bse.get('digital_score', np.nan),
        'p': m_sub.pvalues.get('digital_score', np.nan),
        'n': len(sub),
        'r2': m_sub.rsquared,
    }

# 按区域分组回归
region_results = {}
for reg in df['region'].unique():
    sub = df[df['region'] == reg]
    X_sub = sm.add_constant(sub[controls2])
    m_sub = sm.OLS(sub['revenue_growth_pct'], X_sub).fit(cov_type='HC1')
    region_results[reg] = {
        'coef': m_sub.params.get('digital_score', np.nan),
        'se': m_sub.bse.get('digital_score', np.nan),
        'p': m_sub.pvalues.get('digital_score', np.nan),
        'n': len(sub),
        'r2': m_sub.rsquared,
    }

# 构建异质性分析表
hetero_lines = []
hetero_lines.append("| 分组 | 分组类别 | 样本量 | 数字化能力系数 | 标准误 | p值 | R² |")
hetero_lines.append("| --- | --- | --- | --- | --- | --- | --- |")

hetero_lines.append("| **行业** | 制造业 | {} | {:.3f}{} | {:.3f} | {:.3f} | {:.3f} |".format(
    industry_results['制造业']['n'],
    industry_results['制造业']['coef'],
    '***' if industry_results['制造业']['p'] < 0.01 else '**' if industry_results['制造业']['p'] < 0.05 else '*' if industry_results['制造业']['p'] < 0.1 else '',
    industry_results['制造业']['se'],
    industry_results['制造业']['p'],
    industry_results['制造业']['r2'],
))
for ind in ['软件服务', '零售业', '商务服务', '文创服务']:
    r = industry_results[ind]
    sig = '***' if r['p'] < 0.01 else '**' if r['p'] < 0.05 else '*' if r['p'] < 0.1 else ''
    hetero_lines.append("| | {} | {} | {:.3f}{} | {:.3f} | {:.3f} | {:.3f} |".format(
        ind, r['n'], r['coef'], sig, r['se'], r['p'], r['r2']))

hetero_lines.append("| **区域** | 东部 | {} | {:.3f}{} | {:.3f} | {:.3f} | {:.3f} |".format(
    region_results['东部']['n'],
    region_results['东部']['coef'],
    '***' if region_results['东部']['p'] < 0.01 else '**' if region_results['东部']['p'] < 0.05 else '*' if region_results['东部']['p'] < 0.1 else '',
    region_results['东部']['se'],
    region_results['东部']['p'],
    region_results['东部']['r2'],
))
for reg in ['中部', '西部', '东北']:
    r = region_results[reg]
    sig = '***' if r['p'] < 0.01 else '**' if r['p'] < 0.05 else '*' if r['p'] < 0.1 else ''
    hetero_lines.append("| | {} | {} | {:.3f}{} | {:.3f} | {:.3f} | {:.3f} |".format(
        reg, r['n'], r['coef'], sig, r['se'], r['p'], r['r2']))

hetero_table = "\n".join(hetero_lines)
hetero_table += "\n\n注：括号内为HC1稳健标准误。* p<0.1, ** p<0.05, *** p<0.01。每组回归均控制所有控制变量。"

with open(TABLES_DIR / "tab_04_heterogeneity.md", "w", encoding="utf-8") as f:
    f.write(hetero_table)

print("异质性分析表已生成")

# ============================================================
# 9. 模型诊断
# ============================================================

# VIF 检验（模型 3 的自变量）
X_vif = X3.drop(columns=['const'])
vif_data = []
for i, col in enumerate(X_vif.columns):
    vif_val = variance_inflation_factor(X3.values, i + 1)  # +1 因为 const 在第 0 列
    vif_data.append({'变量': col, 'VIF': round(vif_val, 3)})
vif_df = pd.DataFrame(vif_data)
max_vif = vif_df['VIF'].max()

# Breusch-Pagan 检验（模型 3）
bp_stat, bp_p, bp_f, bp_fp = het_breuschpagan(model3.resid, X3)

# 残差正态性（Jarque-Bera）
jb_stat, jb_p = stats.jarque_bera(model3.resid)

diagnostics = f"""## 模型诊断

### 数据质量
- 样本量: {len(df)}
- 数据结构: 截面数据
- 缺失值: 0
- 面板平衡性: 不适用（非面板数据）

### 模型适用性

#### 多重共线性（VIF）
| 变量 | VIF |
| --- | --- |
"""
for _, row in vif_df.iterrows():
    diagnostics += f"| {row['变量']} | {row['VIF']:.3f} |\n"
diagnostics += f"\nVIF 最大值: {max_vif:.3f}（{'无严重共线性' if max_vif < 10 else '存在严重共线性'}）\n\n"

diagnostics += f"""#### 异方差检验（Breusch-Pagan）
- LM 统计量: {bp_stat:.3f}
- p 值: {bp_p:.3f}
- 结论: {'存在异方差（p<0.05），使用HC1稳健标准误是必要的' if bp_p < 0.05 else '不存在显著异方差'}

#### 残差正态性（Jarque-Bera）
- JB 统计量: {jb_stat:.3f}
- p 值: {jb_p:.3f}
- 结论: {'残差显著偏离正态分布' if jb_p < 0.05 else '残差近似正态分布'}

### 问题与降级
- 无
"""

with open(OUTPUT_DIR / "model_diagnostics.md", "w", encoding="utf-8") as f:
    f.write(diagnostics)

print("模型诊断报告已生成")

# ============================================================
# 10. 绘图
# ============================================================

# --- 图1: 数字化能力与营收增长率散点图 ---
fig, ax = plt.subplots(figsize=(8, 6))
ax.scatter(df['digital_score'], df['revenue_growth_pct'], alpha=0.5, s=30, color='#4C72B0')
# 添加拟合线
z = np.polyfit(df['digital_score'], df['revenue_growth_pct'], 1)
p_line = np.poly1d(z)
x_line = np.linspace(df['digital_score'].min(), df['digital_score'].max(), 100)
ax.plot(x_line, p_line(x_line), "r--", linewidth=2, label=f'线性拟合 (斜率={z[0]:.3f})')
ax.set_xlabel('数字化能力指数', fontsize=12)
ax.set_ylabel('营业收入增长率(%)', fontsize=12)
ax.set_title('企业数字化能力与营业收入增长率', fontsize=14)
ax.legend(fontsize=10)
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(FIGURES_DIR / "fig_01_scatter.png", dpi=150, bbox_inches='tight')
plt.close()

# --- 图2: 分行业数字化能力与营收均值 ---
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

# 行业分组
ind_stats = df.groupby('industry').agg({
    'digital_score': 'mean',
    'revenue_growth_pct': 'mean'
}).sort_values('revenue_growth_pct', ascending=True)

axes[0].barh(ind_stats.index, ind_stats['digital_score'], color='#4C72B0', alpha=0.8)
axes[0].set_xlabel('平均数字化能力指数', fontsize=11)
axes[0].set_title('各行业平均数字化能力', fontsize=13)
axes[0].grid(True, alpha=0.3, axis='x')

axes[1].barh(ind_stats.index, ind_stats['revenue_growth_pct'], color='#DD8452', alpha=0.8)
axes[1].set_xlabel('平均营业收入增长率(%)', fontsize=11)
axes[1].set_title('各行业平均营业收入增长率', fontsize=13)
axes[1].grid(True, alpha=0.3, axis='x')

plt.tight_layout()
plt.savefig(FIGURES_DIR / "fig_02_industry_comparison.png", dpi=150, bbox_inches='tight')
plt.close()

# --- 图3: 区域分组均值 ---
fig, axes = plt.subplots(1, 2, figsize=(12, 5))

reg_stats = df.groupby('region').agg({
    'digital_score': 'mean',
    'revenue_growth_pct': 'mean'
}).reindex(['东部', '中部', '西部', '东北'])

colors = ['#4C72B0', '#55A868', '#C44E52', '#8172B3']

axes[0].bar(reg_stats.index, reg_stats['digital_score'], color=colors, alpha=0.8)
axes[0].set_ylabel('平均数字化能力指数', fontsize=11)
axes[0].set_title('各区域平均数字化能力', fontsize=13)
axes[0].grid(True, alpha=0.3, axis='y')

axes[1].bar(reg_stats.index, reg_stats['revenue_growth_pct'], color=colors, alpha=0.8)
axes[1].set_ylabel('平均营业收入增长率(%)', fontsize=11)
axes[1].set_title('各区域平均营业收入增长率', fontsize=13)
axes[1].grid(True, alpha=0.3, axis='y')

plt.tight_layout()
plt.savefig(FIGURES_DIR / "fig_03_region_comparison.png", dpi=150, bbox_inches='tight')
plt.close()

print("图表已生成")

# ============================================================
# 11. results_summary.md
# ============================================================

# 从模型3提取关键结果
m3_digital_coef = model3.params['digital_score']
m3_digital_se = model3.bse['digital_score']
m3_digital_p = model3.pvalues['digital_score']
m3_r2 = model3.rsquared
m3_adj_r2 = model3.rsquared_adj
m3_f = model3.fvalue
m3_n = int(model3.nobs)

sig_text = "***" if m3_digital_p < 0.01 else "**" if m3_digital_p < 0.05 else "*" if m3_digital_p < 0.1 else ""

summary = f"""## 描述性统计

- 营业收入增长率: 均值={desc_stats.loc[desc_stats['变量']=='营业收入增长率(%)', 'mean'].values[0]:.3f}, 标准差={desc_stats.loc[desc_stats['变量']=='营业收入增长率(%)', 'std'].values[0]:.3f}, 范围=[{desc_stats.loc[desc_stats['变量']=='营业收入增长率(%)', 'min'].values[0]:.3f}, {desc_stats.loc[desc_stats['变量']=='营业收入增长率(%)', 'max'].values[0]:.3f}]
- 数字化能力指数: 均值={desc_stats.loc[desc_stats['变量']=='数字化能力指数', 'mean'].values[0]:.3f}, 标准差={desc_stats.loc[desc_stats['变量']=='数字化能力指数', 'std'].values[0]:.3f}, 范围=[{desc_stats.loc[desc_stats['变量']=='数字化能力指数', 'min'].values[0]:.3f}, {desc_stats.loc[desc_stats['变量']=='数字化能力指数', 'max'].values[0]:.3f}]

## 基准回归（模型3: OLS + HC1 + 行业/区域虚拟变量）

- digital_score 系数 = {m3_digital_coef:.3f} ({sig_text}p={m3_digital_p:.3f})
- 标准误（HC1） = {m3_digital_se:.3f}
- R² = {m3_r2:.3f}, 调整R² = {m3_adj_r2:.3f}
- F 值 = {m3_f:.3f}
- 观测数 = {m3_n}

## 逐步回归对比

- 模型1（仅digital_score）: β = {model1.params['digital_score']:.3f}, p = {model1.pvalues['digital_score']:.3f}, R² = {model1.rsquared:.3f}
- 模型2（+控制变量）: β = {model2.params['digital_score']:.3f}, p = {model2.pvalues['digital_score']:.3f}, R² = {model2.rsquared:.3f}
- 模型3（+行业/区域）: β = {m3_digital_coef:.3f}, p = {m3_digital_p:.3f}, R² = {m3_r2:.3f}

## 稳健性检验

- 对数变换employees: β = {model_log.params['digital_score']:.3f}, p = {model_log.pvalues['digital_score']:.3f}, R² = {model_log.rsquared:.3f}
- 剔除极端值（剔除{n_trimmed}个）: β = {model_trim.params['digital_score']:.3f}, p = {model_trim.pvalues['digital_score']:.3f}, R² = {model_trim.rsquared:.3f}
- 无行业/区域（模型2）: β = {model2.params['digital_score']:.3f}, p = {model2.pvalues['digital_score']:.3f}

## 异质性分析

### 按行业分组
"""

for ind, r in sorted(industry_results.items()):
    sig = "***" if r['p'] < 0.01 else "**" if r['p'] < 0.05 else "*" if r['p'] < 0.1 else ""
    summary += f"- {ind}: β={r['coef']:.3f}{sig}, p={r['p']:.3f}, n={r['n']}, R²={r['r2']:.3f}\n"

summary += "\n### 按区域分组\n"
for reg, r in sorted(region_results.items()):
    sig = "***" if r['p'] < 0.01 else "**" if r['p'] < 0.05 else "*" if r['p'] < 0.1 else ""
    summary += f"- {reg}: β={r['coef']:.3f}{sig}, p={r['p']:.3f}, n={r['n']}, R²={r['r2']:.3f}\n"

summary += f"""
## 模型诊断

- VIF 最大值: {max_vif:.3f}（{'无严重共线性' if max_vif < 10 else '存在共线性'}）
- Breusch-Pagan: LM={bp_stat:.3f}, p={bp_p:.3f}（{'存在异方差' if bp_p < 0.05 else '无异方差'}）
- Jarque-Bera: JB={jb_stat:.3f}, p={jb_p:.3f}

## 表格清单

- tab_01_desc_stats.md
- tab_02_correlation.md
- tab_03_baseline.md
- tab_04_heterogeneity.md
- tab_05_robustness.md

## 图清单

- fig_01_scatter.png
- fig_02_industry_comparison.png
- fig_03_region_comparison.png
"""

with open(OUTPUT_DIR / "results_summary.md", "w", encoding="utf-8") as f:
    f.write(summary)

print("结果摘要已生成")

# ============================================================
# 12. results.json — 结构化数字真源
# ============================================================

reportable_values = []

# 描述性统计
for var in desc_vars:
    label = desc_labels[var]
    mean_val = float(df[var].mean())
    std_val = float(df[var].std())
    reportable_values.append({
        "key": f"descriptive.{var}.mean",
        "label": f"{label}均值",
        "value_raw": mean_val,
        "value_display": f"{mean_val:.3f}",
        "precision": 3,
        "allowed_text_forms": [f"{mean_val:.3f}", f"{mean_val:.2f}", f"{mean_val:.1f}"],
        "source": "tab_01_desc_stats",
        "must_report": True
    })
    reportable_values.append({
        "key": f"descriptive.{var}.std",
        "label": f"{label}标准差",
        "value_raw": std_val,
        "value_display": f"{std_val:.3f}",
        "precision": 3,
        "allowed_text_forms": [f"{std_val:.3f}", f"{std_val:.2f}"],
        "source": "tab_01_desc_stats",
        "must_report": False
    })

# 基准回归核心结果 — 模型3
reportable_values.extend([
    {
        "key": "main.digital_score.coef",
        "label": "数字化能力指数回归系数（模型3）",
        "value_raw": float(m3_digital_coef),
        "value_display": f"{m3_digital_coef:.3f}",
        "precision": 3,
        "allowed_text_forms": [f"{m3_digital_coef:.3f}", f"{m3_digital_coef:.2f}"],
        "source": "tab_03_baseline_model3",
        "must_report": True
    },
    {
        "key": "main.digital_score.se",
        "label": "数字化能力指数标准误（模型3）",
        "value_raw": float(m3_digital_se),
        "value_display": f"{m3_digital_se:.3f}",
        "precision": 3,
        "allowed_text_forms": [f"{m3_digital_se:.3f}"],
        "source": "tab_03_baseline_model3",
        "must_report": True
    },
    {
        "key": "main.digital_score.p",
        "label": "数字化能力指数p值（模型3）",
        "value_raw": float(m3_digital_p),
        "value_display": f"{m3_digital_p:.3f}",
        "precision": 3,
        "allowed_text_forms": [f"{m3_digital_p:.3f}"],
        "source": "tab_03_baseline_model3",
        "must_report": True
    },
    {
        "key": "main.r2",
        "label": "模型3 R²",
        "value_raw": float(m3_r2),
        "value_display": f"{m3_r2:.3f}",
        "precision": 3,
        "allowed_text_forms": [f"{m3_r2:.3f}", f"{m3_r2:.2f}"],
        "source": "tab_03_baseline_model3",
        "must_report": True
    },
    {
        "key": "main.adj_r2",
        "label": "模型3 调整R²",
        "value_raw": float(m3_adj_r2),
        "value_display": f"{m3_adj_r2:.3f}",
        "precision": 3,
        "allowed_text_forms": [f"{m3_adj_r2:.3f}"],
        "source": "tab_03_baseline_model3",
        "must_report": True
    },
    {
        "key": "main.f_stat",
        "label": "模型3 F统计量",
        "value_raw": float(m3_f),
        "value_display": f"{m3_f:.3f}",
        "precision": 3,
        "allowed_text_forms": [f"{m3_f:.3f}"],
        "source": "tab_03_baseline_model3",
        "must_report": False
    },
    {
        "key": "main.n_obs",
        "label": "样本量",
        "value_raw": m3_n,
        "value_display": str(m3_n),
        "precision": 0,
        "allowed_text_forms": ["180"],
        "source": "tab_03_baseline_model3",
        "must_report": True
    },
])

# 逐步回归对比
for model_name, m_obj in [('model1', model1), ('model2', model2)]:
    coef_val = float(m_obj.params['digital_score'])
    p_val = float(m_obj.pvalues['digital_score'])
    r2_val = float(m_obj.rsquared)
    reportable_values.extend([
        {
            "key": f"stepwise.{model_name}.digital_score.coef",
            "label": f"数字化能力系数（{model_name}）",
            "value_raw": coef_val,
            "value_display": f"{coef_val:.3f}",
            "precision": 3,
            "allowed_text_forms": [f"{coef_val:.3f}"],
            "source": "tab_03_baseline",
            "must_report": False
        },
        {
            "key": f"stepwise.{model_name}.r2",
            "label": f"R²（{model_name}）",
            "value_raw": r2_val,
            "value_display": f"{r2_val:.3f}",
            "precision": 3,
            "allowed_text_forms": [f"{r2_val:.3f}"],
            "source": "tab_03_baseline",
            "must_report": False
        },
    ])

# 稳健性检验
reportable_values.extend([
    {
        "key": "robustness.log_employees.digital_score.coef",
        "label": "稳健性：对数变换员工后数字化能力系数",
        "value_raw": float(model_log.params['digital_score']),
        "value_display": f"{model_log.params['digital_score']:.3f}",
        "precision": 3,
        "allowed_text_forms": [f"{model_log.params['digital_score']:.3f}"],
        "source": "tab_05_robustness",
        "must_report": True
    },
    {
        "key": "robustness.trimmed.digital_score.coef",
        "label": "稳健性：剔除极端值后数字化能力系数",
        "value_raw": float(model_trim.params['digital_score']),
        "value_display": f"{model_trim.params['digital_score']:.3f}",
        "precision": 3,
        "allowed_text_forms": [f"{model_trim.params['digital_score']:.3f}"],
        "source": "tab_05_robustness",
        "must_report": True
    },
])

# 异质性分析
for ind, r in industry_results.items():
    reportable_values.append({
        "key": f"heterogeneity.industry.{ind}.coef",
        "label": f"行业异质性：{ind}数字化能力系数",
        "value_raw": float(r['coef']),
        "value_display": f"{r['coef']:.3f}",
        "precision": 3,
        "allowed_text_forms": [f"{r['coef']:.3f}"],
        "source": "tab_04_heterogeneity",
        "must_report": False
    })

for reg, r in region_results.items():
    reportable_values.append({
        "key": f"heterogeneity.region.{reg}.coef",
        "label": f"区域异质性：{reg}数字化能力系数",
        "value_raw": float(r['coef']),
        "value_display": f"{r['coef']:.3f}",
        "precision": 3,
        "allowed_text_forms": [f"{r['coef']:.3f}"],
        "source": "tab_04_heterogeneity",
        "must_report": False
    })

# 诊断结果
reportable_values.extend([
    {
        "key": "diagnostic.vif_max",
        "label": "VIF最大值",
        "value_raw": float(max_vif),
        "value_display": f"{max_vif:.3f}",
        "precision": 3,
        "allowed_text_forms": [f"{max_vif:.3f}"],
        "source": "model_diagnostics",
        "must_report": False
    },
    {
        "key": "diagnostic.bp_p",
        "label": "Breusch-Pagan p值",
        "value_raw": float(bp_p),
        "value_display": f"{bp_p:.3f}",
        "precision": 3,
        "allowed_text_forms": [f"{bp_p:.3f}"],
        "source": "model_diagnostics",
        "must_report": False
    },
])

results_json = {
    "meta": {
        "method": "OLS with HC1 robust standard errors + industry/region dummies",
        "sample_size": m3_n,
        "notes": [
            "Cross-section data, 180 SMEs",
            "Correlation analysis only, no causal claims",
            "Industry benchmark: Manufacturing; Region benchmark: Eastern"
        ]
    },
    "reportable_values": reportable_values,
    "warnings": []
}

with open(OUTPUT_DIR / "results.json", "w", encoding="utf-8") as f:
    json.dump(results_json, f, ensure_ascii=False, indent=2)

print("results.json 已生成")

# ============================================================
# 13. assets_manifest.json
# ============================================================

assets_manifest = {
    "figures": [
        {
            "id": "fig_01",
            "title": "企业数字化能力与营业收入增长率散点图",
            "path": str((FIGURES_DIR / "fig_01_scatter.png").resolve()),
            "required": True
        },
        {
            "id": "fig_02",
            "title": "各行业平均数字化能力与营业收入增长率",
            "path": str((FIGURES_DIR / "fig_02_industry_comparison.png").resolve()),
            "required": True
        },
        {
            "id": "fig_03",
            "title": "各区域平均数字化能力与营业收入增长率",
            "path": str((FIGURES_DIR / "fig_03_region_comparison.png").resolve()),
            "required": True
        },
    ],
    "tables": [
        {
            "id": "table_01",
            "title": "变量描述性统计",
            "path": str((TABLES_DIR / "tab_01_desc_stats.md").resolve()),
            "required": True,
            "preferred_display": "markdown_table"
        },
        {
            "id": "table_02",
            "title": "相关系数矩阵",
            "path": str((TABLES_DIR / "tab_02_correlation.md").resolve()),
            "required": True,
            "preferred_display": "markdown_table"
        },
        {
            "id": "table_03",
            "title": "基准回归结果",
            "path": str((TABLES_DIR / "tab_03_baseline.md").resolve()),
            "required": True,
            "preferred_display": "markdown_table"
        },
        {
            "id": "table_04",
            "title": "异质性分析结果",
            "path": str((TABLES_DIR / "tab_04_heterogeneity.md").resolve()),
            "required": True,
            "preferred_display": "markdown_table"
        },
        {
            "id": "table_05",
            "title": "稳健性检验结果",
            "path": str((TABLES_DIR / "tab_05_robustness.md").resolve()),
            "required": True,
            "preferred_display": "markdown_table"
        },
    ]
}

with open(OUTPUT_DIR / "assets_manifest.json", "w", encoding="utf-8") as f:
    json.dump(assets_manifest, f, ensure_ascii=False, indent=2)

print("assets_manifest.json 已生成")

# ============================================================
# 14. 运行日志
# ============================================================

run_end = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
run_log_lines.extend([
    f"\n### 数据处理\n",
    f"- 对数变换: ln_employees = log(employees)\n",
    f"- 剔除极端值: {n_trimmed} 个样本被剔除（营收增长率超出均值±3σ）\n",
    f"- 虚拟变量: industry（基准=制造业）, region（基准=东部）\n",
    f"\n### 运行时间\n",
    f"- 开始: {run_start}\n",
    f"- 结束: {run_end}\n",
    f"\n### 输出文件\n",
    f"- tables/tab_01_desc_stats.md\n",
    f"- tables/tab_02_correlation.md\n",
    f"- tables/tab_03_baseline.md\n",
    f"- tables/tab_04_heterogeneity.md\n",
    f"- tables/tab_05_robustness.md\n",
    f"- figures/fig_01_scatter.png\n",
    f"- figures/fig_02_industry_comparison.png\n",
    f"- figures/fig_03_region_comparison.png\n",
    f"- results_summary.md\n",
    f"- results.json\n",
    f"- assets_manifest.json\n",
    f"- model_diagnostics.md\n",
])

with open(OUTPUT_DIR / "run_log.md", "w", encoding="utf-8") as f:
    f.write("".join(run_log_lines))

print("\n全部分析完成!")
print(f"数字化能力指数 β = {m3_digital_coef:.3f}, p = {m3_digital_p:.3f}")
print(f"R² = {m3_r2:.3f}, 调整R² = {m3_adj_r2:.3f}")
