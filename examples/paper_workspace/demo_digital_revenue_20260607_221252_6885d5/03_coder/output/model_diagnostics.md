## 模型诊断

### 数据质量
- 样本量: 180
- 数据结构: 截面数据
- 缺失值: 0
- 面板平衡性: 不适用（非面板数据）

### 模型适用性

#### 多重共线性（VIF）
| 变量 | VIF |
| --- | --- |
| digital_score | 1.424 |
| firm_age_years | 1.069 |
| employees | 1.117 |
| rd_intensity_pct | 1.365 |
| marketing_intensity_pct | 1.122 |
| manager_edu_years | 1.135 |
| export_dummy | 1.093 |
| financing_constraint | 1.121 |
| ind_商务服务 | 1.527 |
| ind_文创服务 | 1.400 |
| ind_软件服务 | 1.891 |
| ind_零售业 | 1.567 |
| reg_东部 | 3.670 |
| reg_中部 | 3.103 |
| reg_西部 | 2.757 |

VIF 最大值: 3.670（无严重共线性）

#### 异方差检验（Breusch-Pagan）
- LM 统计量: 16.029
- p 值: 0.380
- 结论: 不存在显著异方差

#### 残差正态性（Jarque-Bera）
- JB 统计量: 0.061
- p 值: 0.970
- 结论: 残差近似正态分布

### 问题与降级
- 无
