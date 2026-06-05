# AI 故障模式清单

本文件定义 5 种 AI 在实证论文写作中常见的故障模式。Stage 5 reviewer 必须按此清单逐项审查。

---

## M1: 编造统计结果

### 症状
- paper 中出现了 results_summary.md 里找不到的数字
- 统计检验（如 Wilcoxon、t 检验）在 analysis.py 中没有对应代码
- 回归系数、p 值、R² 等与代码输出不一致
- 出现"约""大约""近似"等模糊修饰词掩盖不精确

### 诊断
1. 提取 paper 中所有阿拉伯数字和百分比
2. 在 results_summary.md 中逐一查找来源
3. 检查每个统计检验是否在 analysis.py 中有实现

### 修复
- 删除无来源的数字
- 如果需要该统计量，在 analysis.py 中补充对应代码并重新运行
- 用 results_summary.md 中的实际数字替换

### 防范
coder_agent 红线：**禁止在代码外生成任何统计数字。paper 中引用的每个数字必须来自 results_summary.md。**

---

## M2: 编造引用

### 症状
- \cite{key} 对应的 bibitem 不存在
- 参考文献的作者、年份、题名、期刊无法在用户提供的 PDF 或验证列表中找到
- "标准文献"被添加但未验证真实性
- 文献标记为"待确认"但 paper 中已当作确定引用使用

### 诊断
1. 提取 paper 中所有 \cite{} 的 key
2. 检查每个 key 是否在 thebibliography 环境中存在
3. 检查每条 bibitem 是否在用户提供的 References.txt 或 PDF 中有来源

### 修复
- 删除无来源的引用
- 从用户 PDF 中提取真实引用信息
- 未验证文献标注"[待确认]"并在 references_used.md 中记录

### 防范
writer_agent 红线：**不得编造作者、年份、题名、期刊。无法确认的文献只能写入"待补充参考文献"。**

---

## M3: 代码-论文不一致

### 症状
- paper 中 \input{tables/tab_xx.tex} 引用的文件不存在
- paper 中引用的图（\includegraphics）文件不存在
- paper 声称"见表X"但表格编号与实际不符
- results_summary.md 中有某个表格但 paper 没有引用

### 诊断
1. 提取 paper 中所有 \input{} 和 \includegraphics{} 路径
2. 检查对应文件是否在 output/ 目录中存在
3. 检查 results_summary.md 中的表格是否都在 paper 中被引用

### 修复
- 修正文件路径
- 补充缺失的表格引用
- 删除引用不存在文件的内容

### 防范
coder_agent 和 writer_agent 的交接必须基于 handoff_schemas.md 定义的格式。

---

## M4: 方法误用

### 症状
- 数据是截面的但用了面板模型
- 因变量不是 0/1 但用了 Logit
- 数据不支持 DID 的平行趋势假设但强行使用
- 把效率值或综合评价排名解释为"绝对实力排名"
- 把相关性结论写成因果性

### 诊断
1. 检查 model_plan.md 中的模型选择理由
2. 对照 data_audit.md 中的数据结构
3. 检查 paper 中的结论是否超出模型能力

### 修复
- 降级到数据支持的模型
- 修改结论措辞，区分相关性和因果性
- 在局限性中说明模型限制

### 防范
modeler_agent 必须在 model_plan.md 中明确说明"不建议做的分析"。coder_agent 必须在 model_diagnostics.md 中报告模型适用性。

---

## M5: 字数/结构不达标

### 症状
- 论文总字数远低于要求（如目标 8000 字，实际 6000 字）
- 缺少必要章节（如没有文献综述、没有结论）
- 实证分析部分过于简略
- 政策建议与实证结果脱节

### 诊断
1. 统计 paper_draft.tex 的字数（不含 LaTeX 命令和参考文献）
2. 检查是否包含必要章节
3. 检查各章节字数比例是否合理

### 修复
- 扩展字数不足的章节
- 补充缺失章节
- 确保政策建议对应实证结果

### 防范
writer_agent 必须按 writing_standards.md 的字数分配写作。

---

## M6: 凭记忆续跑

### 症状
- 进入 Stage 时未执行 self-check，直接开始执行
- session_state.md 中的阶段与实际执行阶段不符
- 上游 flag 文件不存在但仍继续执行

### 诊断
1. 检查进入 Stage 前是否运行了 `stage_guard.py`
2. 检查 session_state.md 是否与当前 workspace 状态一致

### 修复
- 停止当前执行，运行 self-check 恢复上下文
- 若无法恢复，读取 SKILL.md 从头确认阶段

### 防范
进入任何 Stage 前必须执行 self-check 三项确认（当前阶段、上游 flag、输入路径）。

---

## M7-M12: Word 输出管线红线

以下红线与 Word 生成流程相关，由 `gen_docx.py`、`validate_docx.py` 和 `verify_consistency.py` 自动检查：

| 编号 | 红线 | 检查脚本 |
|------|------|---------|
| M7 | Word 输出不得绕过 Markdown+pandoc | gen_docx.py |
| M8 | 禁止 python-docx 生成或重写公式 | validate_docx.py |
| M9 | 禁止非法 OOXML 拼接 | validate_docx.py |
| M10 | 三线表边框必须复用 tcBorders | validate_docx.py |
| M11 | docx 未验证不得通过 | validate_docx.py + verify_consistency.py |
| M12 | 禁止硬编码本机依赖路径 | gen_docx.py（仅使用 shutil.which/pypandoc 自动发现） |

### 症状
- Word 文件无法打开或公式显示为空白/LaTeX 原文
- 表格边框重复或格式错乱
- 脚本中硬编码了 `/usr/local/bin/pandoc` 等路径

### 诊断
运行验证脚本链：
```bash
python scripts/verify_consistency.py --format markdown --skip-word-count ...
python scripts/gen_docx.py ...
python scripts/validate_docx.py ...
python scripts/verify_consistency.py --format docx --skip-word-count ...
```

### 修复
- 公式问题：检查 Markdown 中的 LaTeX 语法，确保 pandoc 可识别
- 边框问题：确认 tcBorders 复用逻辑，不要重复 append
- 路径问题：使用 `shutil.which()` 或 `pypandoc.get_pandoc_path()` 自动发现

---

## M13-M24: 流程与质量红线

以下红线覆盖模型选择、结果溯源、审查独立性和写作质量：

| 编号 | 红线 | 检查时机 |
|------|------|---------|
| M13 | modeler 不得跳过模型选择树 | Stage 2 |
| M14 | 方法-数据匹配必须前置 | Stage 2 |
| M15 | 必须列出不推荐模型 | Stage 2 |
| M16 | 解释边界必须前置确认 | Stage 2 |
| M17 | 结构化结果为数字真源 | Stage 3→4→5 |
| M18 | 关键数字必须可追溯 | Stage 4→5 |
| M19 | reviewer 不得主观放行 | Stage 5 |
| M20 | 最终 PASS 必须经过门禁脚本 | Stage 5 |
| M21 | 审查结论必须使用统一枚举 | Stage 5 |
| M22 | 禁止高频 AI 模板表达 | Stage 4→5 |
| M23 | 自然表达不得牺牲准确性 | Stage 4→5 |
| M24 | Stage 5 禁止修改上游产出 | Stage 5 |

### 症状
- modeler 跳过了 `model_selection_tree.md` 直接写公式
- 论文中数字在 results.json 中找不到
- reviewer 在脚本报告 BLOCKER 时仍给 PASS
- quality_check.md 使用了非标准结论（如"基本通过"）
- writer 使用了 ai_patterns_zh.md 中标记为 HARD 的禁用表达

### 诊断
1. 检查 `method_fit_check.md` 是否存在且 Stage 2 判定非 BLOCKER
2. 运行 `verify_consistency.py --format markdown` 检查数字一致性
3. 运行 `final_quality_gate.py` 检查门禁
4. 检查 `quality_check.md` 的 Final Verdict 是否使用标准枚举

### 修复
- 模型选择问题：回到 Stage 2 重做模型选择树定位
- 数字不一致：检查 results.json 的 reportable_values，确认 value_display
- 审查结论不标准：统一改为 PASS/PASS_WITH_MINOR/WARN/FAIL/INCOMPLETE
- AI 模板表达：按 ai_patterns_zh.md 规则改写
- Stage 5 改了上游产出：回退到对应 Stage 修复

## Stage 5 Reviewer 审查清单

reviewer_agent 必须按以下顺序逐项检查：

| 序号 | 检查项 | 对应故障模式 | 严重度 |
|------|--------|-------------|--------|
| 1 | paper 中每个数字是否有 results_summary.md 来源 | M1 | block |
| 2 | 每个 \cite{} 是否在参考文献列表中存在 | M2 | block |
| 3 | 每条 bibitem 是否有用户来源或标注"待确认" | M2 | block |
| 4 | \input{} 引用的表格文件是否存在 | M3 | warn |
| 5 | 图片引用文件是否存在 | M3 | warn |
| 6 | 模型选择是否与数据结构匹配 | M4 | block |
| 7 | 结论是否超出模型能力 | M4 | block |
| 8 | 论文字数是否达标 | M5 | warn |
| 9 | 是否包含所有必要章节 | M5 | warn |
| 10 | 政策建议是否对应实证结果 | M5 | warn |

**严重度说明**：
- **block**: 必须修复，不修复不能输出最终版
- **warn**: 应该修复，但可以在"已知局限"中说明后放行
