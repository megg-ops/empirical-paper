# 阶段间数据传递合约

本文件定义各 Stage 之间传递数据的格式规范。每个 Stage 的输出必须满足下游 Stage 的输入要求。

---

## Stage 0 → Stage 1

### manifest.json

```json
{
  "run_id": "string — 运行唯一标识（UUID 或时间戳）",
  "workspace_root": "string — 工作空间根目录路径",
  "project_title": "string — 项目/论文标题",
  "created_at": "string — ISO 8601 创建时间",
  "framework_file": "string — 研究框架文件路径",
  "data_file": "string — 数据文件路径",
  "template_file": "string | null — LaTeX 模板路径",
  "word_template_file": "string | null — Word 模板路径",
  "output_format": "string — latex | docx（当两种模板都存在时由用户确认）",
  "references_dir": "string | null — 参考文献目录路径",
  "selection_notes": {
    "字段名": "string — 选择该文件的理由"
  }
}
```

**必填字段**：run_id, workspace_root, project_title, created_at, framework_file, data_file, output_format
**可选字段**：template_file, word_template_file, references_dir, selection_notes

**新增字段**（pandoc 依赖检测）：

```json
{
  "tool_paths": {
    "pandoc": "auto"
  },
  "dependency_status": {
    "pandoc": "found/missing"
  },
  "warnings": []
}
```

检测逻辑：`shutil.which("pandoc")` 或 `pypandoc.get_pandoc_path()`。找不到时记录 `missing`，Stage 0 给出 WARN。不写入任何用户本机绝对路径，除非用户显式通过 `--pandoc` 或 `PANDOC_PATH` 提供。

---

## Stage 1 → Stage 2

### data_audit.md

必须包含以下章节：

1. **基本信息**：文件格式、样本量、变量数
2. **关键字段**：时间字段、个体字段、行业字段
3. **缺失值**：每列缺失数和比例
4. **重复样本**：完全重复数、entity-year 重复数
5. **异常极值**：各变量 min/max/mean/std
6. **变量匹配结果**：框架变量 vs 数据列名的匹配表
7. **推荐模型**：数据结构判断 + 推荐模型

### variable_map.json

```json
{
  "data_structure": "string — cross_section | time_series | panel",
  "n_entities": "number | null",
  "n_years": "number | null",
  "year_range": "[start, end] | null",
  "dependent_variable": {
    "paper_name": "string",
    "data_column": "string",
    "status": "matched | unmatched",
    "match_type": "exact | fuzzy"
  },
  "core_independent_variable": {
    "paper_name": "string",
    "data_column": "string",
    "status": "matched | unmatched",
    "match_type": "exact | fuzzy"
  },
  "controls": [
    {
      "paper_name": "string",
      "data_column": "string",
      "status": "matched | unmatched",
      "match_type": "exact | fuzzy"
    }
  ],
  "fixed_effects": {
    "year": "string | null",
    "entity": "string | null"
  },
  "recommended_model": "string",
  "unmatched_variables": ["string"]
}
```

**必填字段**：data_structure, dependent_variable, core_independent_variable, recommended_model

---

## Stage 2 → Stage 3

### model_plan.md

必须包含以下章节：

1. **数据结构判断**：类型、优势、局限
2. **变量设定**：被解释变量、核心解释变量、控制变量、固定效应
3. **推荐主模型**：模型公式、选择原因
4. **可选扩展分析**：列表
5. **不建议做的分析**：列表 + 原因

### 实证设计.md

必须包含：

1. 模型公式（LaTeX 格式）
2. 每个变量的定义
3. 模型的经济含义
4. 模型的限制
5. 是否支持因果解释

### method_fit_check.md

方法-数据匹配检查，必须包含：

1. **数据结构判断**：类型、判断依据、是否支持推荐模型
2. **因变量类型判断**：因变量、类型、是否匹配推荐模型
3. **识别条件判断**：政策冲击、处理组/对照组、时间维度、断点、工具变量、固定效应、结论
4. **推荐模型**：模型、适配理由、必要诊断
5. **不推荐模型**：模型与不推荐原因的表格
6. **解释边界**：是否支持因果解释、允许/禁止的表述
7. **Stage 2 判定**：PASS / WARN / BLOCKER

   必须使用以下三者之一：
   - **PASS**：方法与数据匹配，可以进入用户确认
   - **WARN**：存在限制，但可在论文局限中说明，可以进入用户确认
   - **BLOCKER**：方法与数据不匹配，不得进入用户确认，不得写 `user_confirmed.flag`

   若为 BLOCKER，必须写明：
   - `blocker_reason`: 不匹配的具体原因
   - `required_fix`: 用户需要修改什么（研究问题/变量/数据/模型）
   - `allowed_next_actions`: 允许的后续操作（如"重新选择模型""补充数据""修改研究问题"）

8. **用户确认事项**

**门控规则**：Stage 2 判定 = BLOCKER 时，不得进入 Stage 3。即使用户确认，也不能写入 `user_confirmed.flag`。只有 PASS 或 WARN 才能进入用户确认流程并写 flag。

---

## Stage 3 → Stage 4

### results.json schema

```json
{
  "meta": {
    "method": "string",
    "sample_size": 0,
    "notes": []
  },
  "reportable_values": [
    {
      "key": "string",
      "label": "string",
      "value_raw": 0,
      "value_display": "string",
      "precision": 3,
      "allowed_text_forms": [],
      "source": "string",
      "must_report": true
    }
  ],
  "warnings": []
}
```

`reportable_values` 不得为空。若为空，Stage 3 不得通过。

详见 `references/results_schema.md`。

### results_summary.md

必须按章节组织，包含：

1. **描述性统计**：各变量均值、标准差、最小值、最大值
2. **主模型结果**：系数、标准误、p 值、显著性
3. **其他分析结果**：异质性、稳健性等

**格式要求**：
- 每个统计量保留 3 位小数
- p 值保留 3 位小数
- 显著性标注：`*` p<0.1, `**` p<0.05, `***` p<0.01
- 每个数字必须可追溯到 analysis.py 的输出

### tables/*.tex

- 文件命名：`tab_01_desc_stats.tex` 格式（两位数字 + 英文下划线描述，如 `tab_03_baseline.tex`、`tab_05_robustness.tex`）
- 每个文件是独立的 table 环境
- 使用 booktabs 包（\toprule, \midrule, \bottomrule）

### figures/*.png

- 文件命名有意义
- 中文标签（标题、坐标轴、图例）
- 分辨率足够（≥150 dpi）

### model_diagnostics.md

必须包含：

1. **数据质量**：样本量、面板平衡性
2. **模型适用性**：检验结果（如 Hausman 检验、VIF）
3. **问题与降级**：如果有问题，说明降级方案

---

## Stage 4 → Stage 5

### paper_draft.tex（LaTeX 输出时）

必须包含：

1. 完整的 LaTeX 文档结构（documentclass → end{document}）
2. 所有章节（摘要、引言、文献综述、研究设计、实证分析、结论）
3. 所有表格用 \input{} 引用
4. 参考文献用 thebibliography 环境或 enumerate（取决于引用格式选择）
5. 每个 \cite{} 都有对应的 bibitem（如选择交叉引用格式）

### paper_draft.md / paper_draft.docx（Word 输出时）

必须包含：

1. 所有章节（摘要、引言、文献综述、研究设计、实证分析、结论）
2. 公式用 LaTeX 语法（`$...$` 行内，`$$...$$` 块级）
3. 表格用 markdown 表格或引用 .tex 文件路径
4. 图片用相对路径引用 figures/ 目录下的 .png 文件
5. 参考文献列表在文末

### references_used.md

必须包含：

1. 用户提供的文献列表（编号、cite key、引用信息、使用位置、来源）
2. 补充的文献列表（编号、cite key、引用信息、使用位置、来源、状态）
3. 引用统计（用户数、补充数、总数）

### writing_checklist.md

必须包含所有检查项的勾选状态。

---

## Stage 4 可选输出

### policy_references.md（可选）

如果 writer 执行了政策搜索，必须包含：

1. 搜索关键词
2. 搜索时间
3. 找到的政策列表（政策名称、发布时间、来源、验证状态）
4. 三重验证结果（来源多样性、内容一致性、原文可达性）
5. 融入论文的具体政策信息

---

## Stage 5 → Stage 6

### 输入要求

Stage 6（独立专家审稿）需要以下输入：

1. `<workspace>/final_paper/paper_final.tex`（或 `paper_final.docx`）
2. `references/ai_patterns_zh.md`
3. `references/writing_standards.md`
4. `references/latex_formatting.md`
5. `references/independent_review_rubric.md`

**不传递任何中间产物**（如 `analysis.py`、`results_summary.md`、`model_plan.md` 等）。

---

## quality_check.md schema

```markdown
# Quality Check Report

## 1. Final Verdict

Final Verdict: PASS / PASS_WITH_MINOR / WARN / FAIL / INCOMPLETE

Reason:

## 2. Gate Summary

| Gate | Source Report | Status | Highest Severity |
|---|---|---|---|
| Method Fit | method_fit_check.md | PASS/WARN/BLOCKER/MISSING | ... |
| Method Implementation | analysis.py / results_summary.md / reviewer check | PASS/WARN/BLOCKER/MISSING | ... |
| Structured Results | results.json / verify_consistency.py | PASS/WARN/BLOCKER/MISSING | ... |
| Document Format | docx_validation_report.md / LaTeX compile log | PASS/WARN/BLOCKER/MISSING | ... |
| Citation & References | consistency report | PASS/WARN/BLOCKER/MISSING | ... |
| Writing Quality | reviewer check | PASS/WARN/BLOCKER/MISSING | ... |

## 3. BLOCKER

- ...

## 4. MAJOR

- ...

## 5. MINOR

- ...

## 6. LIMITATION

- ...

## 7. Required Fixes Before PASS

- ...

## 8. Reviewer Notes

- ...
```

规则：

- 若存在任一 BLOCKER，Final Verdict 必须为 FAIL；
- 若必要报告缺失导致无法判断，Final Verdict 必须为 INCOMPLETE；
- 若无 BLOCKER 但有 MAJOR，Final Verdict 必须为 WARN；
- 若无 BLOCKER、无 MAJOR，可为 PASS 或 PASS_WITH_MINOR。

---

## Stage 6 输出

### expert_review_report.md

必须包含：

1. 审查概览（4 个维度的评级 + AI 味总分）
2. 方法设计审查（模型选择、假设检验、变量设定、方法-数据匹配）
3. 统计原理审查（统计检验正确性、显著性解释、统计错误、因果推断）
4. 格式审查（论文结构、表格格式、参考文献、图表编号）
5. AI 味评分（4 维度 16 项逐项打分 + 总分 + 安全判定）
6. 主要建议（3-5 条优先级排序）
7. 审稿人声明

## Stage 5 输出

### paper_final.tex（LaTeX 输出时）

- 在 paper_draft.tex 基础上修正所有 block 级问题
- 更新引用、表格路径、字数

### paper_final.docx（Word 输出时）

- 在 paper_draft.docx 基础上修正所有 block 级问题
- 如需重新转换，从修正后的 .md 或 .tex 重新生成

### quality_check.md

必须包含：

1. 6 维度检查结果（pass/warn/block）
2. verify_consistency.py 的运行结果
3. 已知局限列表
4. 需要用户确认的事项
