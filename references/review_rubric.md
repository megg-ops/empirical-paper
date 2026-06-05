# Review Rubric

本文件定义最终审查分级规则。reviewer_agent 和 expert_reviewer_agent 必须使用本规则。

## 1. 分级定义

### BLOCKER

不修不能进入下一阶段或不能提交的问题。

出现 BLOCKER 时：

- `quality_check.md` 最终结论必须为 FAIL；
- 不得写 PASS；
- 不得写"基本通过"；
- 必须列出修复动作。

典型 BLOCKER：

- 方法与数据结构不匹配；
- Stage 2 已判定 BLOCKER 但仍进入 Stage 3；
- 代码实现与 model_plan / method_fit_check 不一致；
- 论文解释超出 method_fit_check 的解释边界；
- results.json 缺失或 reportable_values 为空；
- 关键数字无法匹配 results.json；
- must_report=true 的数字未出现在论文中；
- verify_consistency.py 返回非 0；
- docx 无法打开；
- Word 公式丢失或残留 LaTeX 原文；
- 图片缺失；
- 表格结构严重错位；
- 正文引用不存在的图表或参考文献；
- 存在 TODO / 待补 / 占位符；
- 关键文件缺失导致无法完成审查。

### MAJOR

明显影响论文质量或评分，但不一定导致文件不可提交的问题。

出现 MAJOR 时：

- 最终结论不得是完全 PASS；
- 可判定为 WARN；
- 必须列出建议修复项。

典型 MAJOR：

- 方法说明不够完整；
- 稳健性检验较弱但已声明局限；
- 表格格式不够规范但可读；
- 参考文献格式不完全统一；
- 写作中有明显重复或表达不自然；
- 局限性说明不足；
- 变量解释不够清晰。

### MINOR

小型格式、措辞或排版问题，不影响核心提交。

出现 MINOR 时：

- 可 PASS_WITH_MINOR；
- 应列出可选修复建议。

典型 MINOR：

- 个别标点不统一；
- 个别表述略啰嗦；
- 小范围格式不一致；
- 图表标题措辞可优化。

### LIMITATION

研究设计或数据本身的合理局限。只要已在论文中说明，不应当作错误。

典型 LIMITATION：

- 数据期数较短；
- 样本量有限；
- 只能做相关性解释；
- 替代模型能力有限；
- 指标构造存在主观性；
- 工具变量或自然实验条件不足。

LIMITATION 不导致 FAIL，但必须在论文局限或结论中被诚实说明。

### PASS

不存在 BLOCKER，且 MAJOR 数量为 0。允许存在少量 MINOR 或已说明的 LIMITATION。

---

## 2. 最终结论规则

最终结论只能使用以下五种之一：

| 最终结论 | 条件 |
|---|---|
| PASS | 无 BLOCKER，无 MAJOR，MINOR 很少，LIMITATION 已说明 |
| PASS_WITH_MINOR | 无 BLOCKER，无 MAJOR，仅有少量 MINOR |
| WARN | 无 BLOCKER，但存在 MAJOR 或较多 MINOR |
| FAIL | 存在任一 BLOCKER |
| INCOMPLETE | 缺少必要检查报告，无法判断 |

禁止使用模糊结论：

- 基本通过；
- 大体可用；
- 问题不大；
- 可以提交但有严重问题；
- 总体 PASS 但存在 BLOCKER。

---

## 3. 优先级规则

当不同检查结果冲突时，按最高严重等级判定：

BLOCKER > MAJOR > MINOR > LIMITATION > PASS

例如：

- docx_validation_report.md = PASS
- markdown_consistency_report.md = BLOCKER

最终必须 FAIL。

---

## 4. reviewer 责任边界

reviewer_agent 不得覆盖脚本结论。

如果脚本报告存在 BLOCKER/FAIL，reviewer_agent 只能：

1. 解释原因；
2. 汇总影响；
3. 给出修复建议。

不得把 BLOCKER 降级为 MAJOR 或 MINOR，除非明确指出脚本误报，并给出证据。
