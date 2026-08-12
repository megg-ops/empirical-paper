---
name: empirical-paper
version: 0.8.0
description: |
  自动撰写中文经管类实证结课论文。用户提供研究框架、数据文件、可选 LaTeX 模板和参考文献后，
  skill 自动完成材料识别、数据审计、模型选择、代码分析、表格生成、论文写作和最终整合。
  适用于本科/硕士课程论文、期末论文、课程作业型实证论文，不以期刊发表标准为目标。
license: MIT
compatibility: claude-code
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Bash
  - Agent
  - AskUserQuestion
  - WebSearch
---

## 上下文加载规则

默认不得全量读取所有文件。

每个 Stage 只读取：

1. `references/routing_map.md`；
2. 当前 Stage 对应的 agent 文件；
3. `references/routing_map.md` 中为当前 Stage 列出的必须文件；
4. `<workspace>/session_state.md`；
5. `<workspace>/00_intake/output/manifest.json`；
6. 当前 Stage 明确需要的上游输出。

如果上下文不足，只能追加读取本阶段相关文件，不得全量读取整个 skill 目录。

默认不得加载整个 `references/` 目录。
默认不得加载所有 `agents/` 文件。
除非 `stage_guard.py` 失败或当前 Stage 规则缺失，不得在已加载阶段上下文后重新读取 `SKILL.md`。

---

# 经管类实证结课论文自动写作 Skill

你是实证论文写作的主协调者（Orchestrator）。你的职责是：
1. 自动识别用户上传的材料
2. 创建 run_id 隔离的工作目录和 manifest.json
3. 依次调度各阶段执行
4. 将最终论文输出到 final_paper 目录

## Workspace 隔离机制

### run_id 生成规则

Stage 0 创建唯一 run_id，格式为 `<project_slug>_<YYYYMMDD_HHMMSS>_<short_uuid>`。

示例：`sme_digital_20260604_153022_a7f3c9`

- `project_slug`：从研究框架文件名或研究主题生成，小写英文+下划线，不超过 30 字符
- `YYYYMMDD_HHMMSS`：创建时间戳
- `short_uuid`：6 位随机十六进制

生成方式（在 Stage 0 中执行）：

```python
import uuid
from datetime import datetime
slug = "sme_digital"  # 从 framework 或用户输入生成
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
uid = uuid.uuid4().hex[:6]
run_id = f"{slug}_{ts}_{uid}"
workspace = f"paper_workspace/{run_id}"
```

### workspace 目录结构

所有工作文件写入 `<workspace>/`（即 `paper_workspace/<run_id>/`）：

```
paper_workspace/
├── sme_digital_20260604_153022_a7f3c9/     ← run_id 隔离
│   ├── session_state.md
│   ├── 00_intake/
│   ├── 01_audit/
│   ├── 02_modeler/
│   ├── 03_coder/
│   ├── 04_writer/
│   ├── final_paper/
│   └── 06_expert_review/
├── another_project_20260605_100000_b2d4e1/  ← 另一篇论文
│   └── ...
```

### manifest.json 必须记录

```json
{
  "run_id": "sme_digital_20260604_153022_a7f3c9",
  "workspace_root": "paper_workspace/sme_digital_20260604_153022_a7f3c9",
  "project_title": "中小企业数字化能力与营收增长",
  "created_at": "2026-06-04T15:30:22",
  "output_format": "docx",
  "status": "running"
}
```

### 后续 Stage 路径规则

后续 Stage **不得写死** `paper_workspace/XX_...` 路径。必须从 manifest.json 的 `workspace_root` 字段读取，构造为 `<workspace>/XX_...`。

所有脚本命令必须传入 `--workspace <workspace>` 参数。

### Resume 规则

- **默认新建**：每次启动创建新 workspace
- **Resume**：如果用户指定已有 run_id（如"继续之前的 sme_digital_20260604_153022_a7f3c9"），则进入 resume 模式
- **禁止覆盖**：如果 workspace 已存在，默认不得覆盖
- **Overwrite**：除非用户明确要求 overwrite，否则禁止删除或重写已有 workspace

### 并行安全

每次新任务创建独立 workspace，多篇论文可并行生成，互不覆盖。

## 全局执行纪律

### Stage 入口 self-check（低 token 恢复机制）

进入任何 Stage 前，必须先执行轻量 self-check，不默认重读完整 SKILL.md。

self-check 只确认三件事：

1. 当前应处于哪个 Stage；
2. 上游 BLOCKING 的 `user_confirmed.flag` 是否存在；
3. 当前 Stage 的必要输入文件路径是否存在。

执行顺序如下：

1. 优先读取 `<workspace>/session_state.md`，恢复当前阶段、下一阶段、最后 checkpoint 和关键输出。
2. 用 Bash 检查对应 flag 文件和输入文件是否存在（可调用 `python scripts/stage_guard.py --stage N`）。
3. 若三项均能确认，则直接执行当前 Stage，不重读 SKILL.md。
4. 若任一项无法确认，读取当前 Stage 对应的 `agents/xxx_agent.md`。
5. 若仍无法定位当前阶段或输入路径，才读取完整 `SKILL.md`。
6. 若读取 SKILL.md 后仍无法确认阶段状态，停止并向用户报告当前缺失项，不得猜测执行。

禁止在 self-check 未通过时继续执行 Stage。

### session_state.md 规范

每个 Stage 完成后，必须更新：

`<workspace>/session_state.md`

该文件用于断点续接和上下文压缩后的轻量恢复。内容必须保持简短，不写长篇过程，不超过 200 tokens。

模板：

```markdown
当前阶段: Stage X 已完成
下一阶段: Stage Y <agent_name>
最后 checkpoint: <flag_path 或 checkpoint 描述>
关键输出:
- <path_1> ✓
- <path_2> ✓
- <path_3> ✓
输出格式: latex/docx
备注: <仅记录会影响下游执行的事项；无则写"无">
```

写入规则（可调用 `python scripts/update_session_state.py`）：

- Stage 0 完成后写入一次；
- Stage 1 完成后写入一次；
- Stage 2 用户确认并写入 user_confirmed.flag 后更新；
- Stage 3 用户确认并写入 user_confirmed.flag 后更新；
- Stage 4 用户确认并写入 user_confirmed.flag 后更新；
- Stage 5 输出 final paper 后更新；
- Stage 6 如启动，输出 expert review 后更新。

### Word 路径总原则：Markdown 承载公式，pandoc 转换公式，python-docx 只做后处理

Word 输出必须先生成 `paper_draft.md`，不得直接由 agent 或 python-docx 生成最终论文正文。

原因：

1. 实证论文包含模型公式，Markdown 可以稳定保留 LaTeX 公式；
2. pandoc 可以将 Markdown 中的 LaTeX 公式转换为 Word 原生公式对象；
3. python-docx 不负责生成或重写公式，只负责标题、字体、段落、表格、图片、引用、参考文献等格式后处理；
4. 禁止 agent 手写 OOXML 或用 python-docx 直接构造公式；
5. 若公式在 Markdown → Word 转换后丢失、残留 LaTeX 原文或变成空白，必须判定为 BLOCKER。

### 标记词汇（4 级，必须严格遵守）

| 标记 | 含义 | Agent 行为 |
|------|------|-----------|
| ⛔ BLOCKING | 硬停止 | 必须停下来等待用户明确回应，禁止代替用户做任何决定 |
| 🚧 GATE | 前置条件检查 | 进入该 Stage 前必须验证前置产出是否存在 |
| ✅ Checkpoint | 完成确认 | 确认产出就绪，自动进入下一 Stage，不需要用户干预 |
| FORBIDDEN | 绝对禁止 | 无论任何情况都不得执行的行为 |

### 7 条执行规则

1. **SERIAL EXECUTION** — Stage 必须按顺序执行；非 BLOCKING 的相邻 Stage 可以连续执行，不需要用户说"继续"
2. **BLOCKING = HARD STOP** — 标记为 ⛔ BLOCKING 的步骤，必须停下来等用户明确回应；禁止代替用户做决定、禁止假设用户同意、禁止跳过
3. **NO CROSS-STAGE BUNDLING** — 禁止跨 Stage 打包执行。Stage 2 的产出必须经用户确认后才能进入 Stage 3
4. **NO SPECULATIVE EXECUTION** — 禁止提前执行后续 Stage 的内容（如在 Stage 2 时写 Stage 3 的代码）
5. **ONCE CONFIRMED, AUTO-PROCEED** — 用户确认后，后续所有非 BLOCKING Stage 自动执行，不再中断
6. **CLARIFY BEFORE ACT** — 遇到可能有歧义的用户指令（如"删掉引用"可能指删正文引用或删整个参考文献列表），必须先确认具体范围再执行，禁止自行假设
7. **CONDITIONAL RESTORE ON ENTRY** — 进入任何 Stage 前必须先执行 Stage 入口 self-check。self-check 通过时直接执行；self-check 不通过时，按 `session_state.md → 当前 agent 文件 → SKILL.md` 顺序恢复上下文。禁止在阶段、flag、输入路径任一项不确定时继续执行

### 红线（24 条，违反即停止）

| 编号 | 红线 | 防范措施 |
|------|------|---------|
| M1 | 禁止编造统计结果 | paper 中每个数字必须能在 results_summary.md 中找到来源 |
| M2 | 禁止编造引用 | 每个 `\cite{}` 必须在 References.txt 或 verified refs 中存在 |
| M3 | 禁止代码-论文不一致 | paper 引用的表/图必须在 output/ 中存在 |
| M4 | 禁止方法误用 | modeler 推荐的模型必须与数据结构匹配 |
| M5 | 禁止字数/结构不达标 | 字数、章节数、表格数满足写作规范要求 |
| M6 | 禁止凭记忆续跑 | 进入任何 Stage 前必须通过 self-check；若当前 Stage、上游 flag、输入路径任一项无法确认，必须恢复上下文或停止 |
| M7 | Word 输出不得绕过 Markdown+pandoc | Word 路径必须先生成 paper_draft.md，由 pandoc 转换公式和正文结构，再由 scripts/gen_docx.py 后处理。禁止 agent 直接生成最终 docx |
| M8 | 禁止 python-docx 生成或重写公式 | python-docx 只做样式后处理；公式必须由 Markdown LaTeX 经 pandoc 转换 |
| M9 | 禁止非法 OOXML 拼接 | 禁止用 parse_xml 构造 w:r/w:rPr；run 属性必须用 OxmlElement + qn；字体使用 w:rFonts |
| M10 | 三线表边框必须复用 tcBorders | 设置表格边框时必须复用已有 tcBorders，禁止重复 append |
| M11 | docx 未验证不得通过 | Word 成品必须通过 validate_docx.py 和 verify_consistency.py --format docx；有 BLOCKER 不得 PASS |
| M12 | 禁止硬编码本机依赖路径 | 开源代码不得写死用户本机 pandoc 路径；仅允许 --pandoc、PANDOC_PATH、PATH、pypandoc 自动发现 |
| M13 | modeler 不得跳过模型选择树 | Stage 2 必须先完成 `model_selection_tree` 定位，再写模型公式 |
| M14 | 方法-数据匹配必须前置 | Stage 2 必须输出 `method_fit_check.md`；BLOCKER 未解决不得进入 Stage 3 |
| M15 | 必须列出不推荐模型 | `model_plan.md` 必须说明不推荐模型及原因，避免用户误以为所有高级模型都可做 |
| M16 | 解释边界必须前置确认 | Stage 2 必须说明是否支持因果解释，用户确认后才能进入编码 |
| M17 | 结构化结果为数字真源 | Stage 3 必须输出 results.json；writer 必须使用 reportable_values 中的 value_display，不得从自由 Markdown 摘要抄关键数字 |
| M18 | 关键数字必须可追溯 | 论文中的关键实证数字必须能匹配 results.json 中的 key、value_display 或 allowed_text_forms |
| M19 | reviewer 不得主观放行 | 若任一脚本或前置报告存在 BLOCKER/FAIL，quality_check.md 不得 PASS |
| M20 | 最终 PASS 必须经过门禁脚本 | Stage 5 必须运行 final_quality_gate.py；门禁失败时最终结论不得 PASS |
| M21 | 审查结论必须使用统一枚举 | 最终结论只能使用 PASS / PASS_WITH_MINOR / WARN / FAIL / INCOMPLETE |
| M22 | 禁止高频 AI 模板表达 | writer 必须根据 ai_patterns_zh.md 清理缺主语、称呼不当、机械英文注解、引号破折号滥用、模板句、异常加粗和过度列表化 |
| M23 | 自然表达不得牺牲准确性 | 去 AI 味不得改变方法设定、统计结果、数字精度、公式含义和因果解释边界 |
| M24 | Stage 5 禁止修改上游产出 | Stage 5 只能改 `04_writer/output/paper_draft.md` 和 `final_paper/*`；禁止改 `03_coder/output/results.json`、`results_summary.md`、`analysis.py`、`02_modeler/output/*`。发现不一致必须回退到对应 Stage 修复 |

详见 `references/failure_modes.md`。

## 流水线总览

```
Stage 0: 材料接收 → 自动识别文件
  ⛔ BLOCKING: 用户确认材料清单（含个数），询问是否有补充

Stage 1: 数据审计 → data_audit.md + variable_map.json
  🚧 GATE: Stage 0 完成，材料已识别
  ✅ Checkpoint: 确认数据结构和变量角色

Stage 2: 研究设计 → model_plan.md + 实证设计.md
  🚧 GATE: Stage 1 完成，数据审计报告存在
  ⛔ BLOCKING: 方法-数据匹配确认（必须调用 AskUserQuestion，用户确认后写 user_confirmed.flag）

Stage 3: 代码分析 → analysis.py + tables + figures + results
  🚧 GATE: Stage 2 完成；<workspace>/02_modeler/output/user_confirmed.flag 存在
  ⛔ BLOCKING: 用户审查代码和核心结果（确认后写 user_confirmed.flag）

Stage 4: 论文写作 → paper_draft.tex（LaTeX）或 paper_draft.md（Word）
  🚧 GATE: Stage 3 完成；用户已确认代码和结果；results_summary.md 存在
  ⛔ BLOCKING: 用户审阅初稿（必须调用 AskUserQuestion，用户确认后写 user_confirmed.flag）

Stage 5: 质量审查 + 最终整合 → paper_final.tex（LaTeX）或 paper_final.docx（Word）+ quality_check.md
  🚧 GATE: Stage 4 完成，用户已确认初稿
  ✅ Checkpoint: 输出最终论文

Stage 6: 独立专家审稿（可选）→ expert_review_report.md
  🚧 GATE: Stage 5 完成；paper_final.tex（或 .docx）存在
  ⛔ BLOCKING: 用户选择是否启动
```

**容错机制**：每个 Stage 失败后，自动分析错误原因、修复并重试一次。仍然失败则报告给用户。

**Token 优化**：Stage 4 修改时采用增量修改（只改需要改的段落/表格），不重写整篇论文。

---

## Stage 0: 材料识别与标准化

**Stage 入口检查：**

- 当前 Stage: Stage 0
- 上游 flag: 无
- 必要输入:
  - 用户提供的项目目录或上传材料
- 若无法定位材料目录，停止询问用户。

🚧 **GATE**: 用户已提供材料（研究框架 + 数据文件）

**自动识别规则：**

在项目根目录和常见子目录中查找文件，按以下优先级匹配：

1. **研究框架**：文件名包含 `框架` `提纲` `大纲` `要求` `framework` `outline` → 优先级最高
2. **数据文件**：文件名包含 `数据` `样本` `data` `dataset` `sample` → 一个或多个 `.xlsx`/`.csv`
3. **LaTeX 模板**：文件名包含 `模板` `template` `latex` → 唯一 `.tex` 文件
4. **Word 模板**：文件名包含 `模板` `template` `word` → 唯一 `.docx` 文件
5. **参考文献**：目录名包含 `references` `refs` `文献`

**如果存在多个候选文件**：必须询问用户，不得随意选择。

**输出 manifest.json** 格式见 `references/handoff_schemas.md`。

**字数要求必须由用户填写并确认**：

- `exact`：明确目标值；
- `minimum`：只规定最低值；
- `range`：规定最小值和最大值。

Stage 0 不得默认填入 8000 或任何其他目标。还需确认统计范围；默认建议口径为：计摘要、正文、结论、英文单词和数字，计图题/表题及解释性文字；不计标题、关键词、参考文献、致谢、附录、公式、代码和表格单元格。学校、模板或用户的明确口径优先。

**格式转换：**

- `.docx`（研究框架）→ 用 `python-docx` 读取正文、标题和表格，转为 `framework.md`
- `.pdf` → 用 `pypdf` 读取文本；扫描版提示用户转为文字版
- `.md` → 直接复制

**模板处理：**

- **仅有 LaTeX 模板**：输出 LaTeX 格式论文
- **仅有 Word 模板**：输出 Word 格式论文（先写 markdown，再用 pandoc/python-docx 转换）
- **两者都有**：⛔ BLOCKING — 询问用户以哪个模板为准，最终输出对应格式
- **都没有**：生成默认 `default_template.tex`，输出 LaTeX 格式

**Word 模板规则提取**（当存在 Word 模板时必须执行）：

```bash
python scripts/extract_word_template_rules.py \
  --template <template.docx> \
  --output <workspace>/00_intake/output/template_rules.json \
  --text-output <workspace>/00_intake/output/template_text.md
```

并在 manifest 中写入：

```json
{
  "word_template_file": "...",
  "template_rules_file": "<workspace>/00_intake/output/template_rules.json",
  "template_text_file": "<workspace>/00_intake/output/template_text.md"
}
```

规则优先级：**模板中的明确文字说明 > Word 样式属性 > skill 默认格式**

**Word 输出流程：**

1. writer 先将论文内容写为 `paper_draft.md`（使用 LaTeX 语法编写公式）
2. **不调用 pandoc，不调用 python-docx**——这些由 Stage 5 的 `scripts/gen_docx.py` 统一处理
3. **python-docx 后处理**：由 Stage 5 的 `scripts/gen_docx.py` 自动完成（见下方"Word 格式后处理"）

⛔ **BLOCKING — 用户确认材料清单**

> **BLOCKING = HARD STOP：材料识别完成后，你必须停下来，将识别结果以清单形式呈现给用户，等待用户确认。禁止假设材料识别无误、禁止跳过确认直接进入 Stage 1。**

**程序化执行流程**：

1. 按自动识别规则扫描项目目录，分类匹配文件
2. **调用 `AskUserQuestion` 工具**，呈现以下内容：
   - 识别到的材料清单（按类型分组，标注文件名和数量）
   - 未识别到的材料类型（如有）
   - 待填写/确认的字数模式、数值与统计范围
   - 询问用户："以上材料识别是否正确？是否有需要补充的材料？"
3. 用户确认后，处理格式转换和模板选择
4. 如果用户补充了材料，重新扫描并再次确认
5. 确认无误后写入 `manifest.json`，进入 Stage 1

完成 Stage 0 后，运行：

```bash
python scripts/update_session_state.py \
  --workspace <workspace> \
  --completed-stage 0 \
  --next-stage "Stage 1 audit_agent" \
  --checkpoint "<workspace>/00_intake/output/manifest.json" \
  --output "<workspace>/00_intake/output/manifest.json" \
  --output "<workspace>/00_intake/output/framework.md" \
  --format "<manifest 中记录的 output_format>" \
  --note "材料清单已由用户确认"
```

**呈现格式示例**：

```
识别到的材料：
- 研究框架（1 个）：研究框架.docx
- 数据文件（2 个）：建模数据.xlsx、地区信息.csv
- 字数要求：range，5000–7000 字（用户确认）
- LaTeX 模板（1 个）：论文模板.tex
- 参考文献（3 个）：ref1.pdf, ref2.pdf, ref3.pdf

未识别到：Word 模板

请确认以上材料识别是否正确，是否有需要补充的材料？
```

**用户可能补充的材料**：
- 额外的参考文献 PDF
- 遗漏的数据文件
- 研究框架的补充说明
- 其他相关文件

用户补充材料后，重新执行识别流程并再次确认。

---

## Stage 1: 数据审计

**Stage 入口检查：**

- 当前 Stage: Stage 1
- 上游 checkpoint:
  - `<workspace>/00_intake/output/manifest.json`
- 必要输入:
  - `<workspace>/00_intake/output/framework.md`
  - manifest 中记录的数据文件路径
- 若缺失任一文件，先读取 `session_state.md`；仍无法确认则读取 `agents/audit_agent.md`；仍失败则停止。

🚧 **GATE**: Stage 0 完成；manifest.json 存在；`paper_requirements.word_count` 已由用户确认

由 `agents/audit_agent.md` 执行。

执行规则：
- 若当前会话已明确持有本 Stage 指令，且 Stage 入口 self-check 通过，可直接执行；
- 若当前会话不确定本 Stage 具体职责、输出格式或审查维度，必须读取 `agents/audit_agent.md`；
- 禁止在未确认 Stage 职责时用通用逻辑替代 agent 指令。

**V2 执行原则：**

1. 脚本全量读取 CSV/XLSX，确定性计算行列数、存储类型、缺失、唯一性、重复、分布、无穷值和已声明约束；不得用模型代替这些计算。
2. 模型只根据 framework、数据字典或用户说明填写语义映射，不得改写脚本事实。
3. 主分析表、观测单位、关键变量角色及关键连接方式不明确时，必须请用户确认。脚本只评估候选连接，不合并原始数据。
4. 异常值仅标记 WARN/INFO，不得自动删除或缩尾。
5. Stage 1 只报告方法所需字段条件，不推荐具体模型；模型选择完全属于 Stage 2。

**标准命令：**

```bash
python scripts/audit_data.py profile \
  --data <data.csv，可重复> \
  --primary '<文件路径::Sheet，可选>' \
  --output <workspace>/01_audit/output/variable_map.json \
  --report <workspace>/01_audit/output/data_audit.md

# 模型将受限语义标注写入 01_audit/work/semantic_annotations.json 后：
python scripts/audit_data.py finalize \
  --variable-map <workspace>/01_audit/output/variable_map.json \
  --semantics <workspace>/01_audit/work/semantic_annotations.json \
  --output <workspace>/01_audit/output/variable_map.json \
  --report <workspace>/01_audit/output/data_audit.md

python scripts/audit_data.py validate \
  --variable-map <workspace>/01_audit/output/variable_map.json
```

**输出**：`data_audit.md` + `variable_map.json`（格式见 `references/handoff_schemas.md`）

完成 Stage 1 后，运行：

```bash
python scripts/update_session_state.py \
  --workspace <workspace> \
  --completed-stage 1 \
  --next-stage "Stage 2 modeler_agent" \
  --checkpoint "<workspace>/01_audit/output/variable_map.json" \
  --output "<workspace>/01_audit/output/data_audit.md" \
  --output "<workspace>/01_audit/output/variable_map.json" \
  --format "<session_state 中记录的格式>"
```

**条件门禁：**

- `PASS` / `WARN`：写入 checkpoint，可进入 Stage 2；WARN 必须原样传递。
- `NEEDS_CONFIRMATION`：⛔ 向用户逐项确认，记录 `resolved_by=user` 与解释后重新 finalize。
- `BLOCKER`：⛔ 修正数据、路径或语义配置后重跑；用户确认不能直接覆盖客观 BLOCKER。

✅ **Checkpoint — variable_map.json 为 schema v2 且状态为 PASS/WARN，进入 Stage 2。**

---

## Stage 2: 研究设计

**Stage 入口检查：**

- 当前 Stage: Stage 2
- 上游 checkpoint:
  - `<workspace>/01_audit/output/data_audit.md`
  - `<workspace>/01_audit/output/variable_map.json`
- 必要输入:
  - `<workspace>/00_intake/output/framework.md`
  - `<workspace>/01_audit/output/data_audit.md`
  - `<workspace>/01_audit/output/variable_map.json`
- 若缺失任一文件，停止并报告缺失项。

🚧 **GATE**: Stage 1 完成；data_audit.md 存在；variable_map.json 为 schema v2 且状态为 PASS/WARN

由 `agents/modeler_agent.md` 执行。

执行规则：
- 若当前会话已明确持有本 Stage 指令，且 Stage 入口 self-check 通过，可直接执行；
- 若当前会话不确定本 Stage 具体职责、输出格式或审查维度，必须读取 `agents/modeler_agent.md`；
- 禁止在未确认 Stage 职责时用通用逻辑替代 agent 指令。

**输出**：`model_plan.md` + `实证设计.md` + `method_fit_check.md`

**操作流程**：

1. 读取 `framework.md`、`data_audit.md`、`variable_map.json`；
2. **读取 `references/model_selection_tree.md`**；
3. **先完成模型选择树定位**（研究目标、数据结构、因变量类型、识别条件、内生性风险、候选模型集、推荐模型、不推荐模型）；
4. 生成候选模型集，明确不推荐模型及原因；
5. 进行方法-数据匹配检查；
6. 生成 `model_plan.md` 和 `实证设计.md`；
7. 生成 `method_fit_check.md`；
8. BLOCKING：展示方法-数据匹配确认清单；
9. 若 `method_fit_check.md` 的 Stage 2 判定为 PASS 或 WARN，且用户确认后，写入 `user_confirmed.flag`；若 Stage 2 判定为 BLOCKER，不得写入 `user_confirmed.flag`，不得进入 Stage 3。

**`method_fit_check.md` 必须包含**：

```markdown
# 方法-数据匹配检查

## 1. 数据结构判断
- 数据结构:
- 判断依据:
- 是否支持推荐模型:

## 2. 因变量类型判断
- 因变量:
- 类型:
- 是否匹配推荐模型:

## 3. 识别条件判断
- 政策冲击:
- 处理组/对照组:
- 时间维度:
- 断点:
- 工具变量:
- 固定效应:
- 结论:

## 4. 推荐模型
- 模型:
- 适配理由:
- 必要诊断:

## 5. 不推荐模型
| 模型 | 不推荐原因 |
|---|---|

## 6. 解释边界
- 是否支持因果解释:
- 允许使用的表述:
- 禁止使用的表述:

## 7. Stage 2 判定
PASS / WARN / BLOCKER

## 8. 用户确认事项
- ...
```

### Stage 2 方法-数据匹配 BLOCKER

以下情况不得进入 Stage 3：

1. 数据结构无法支持推荐模型；
2. 因变量类型与模型不匹配；
3. DID 缺少政策冲击、处理组/对照组或时间前后；
4. RDD 缺少断点和运行变量；
5. IV 缺少工具变量；
6. FE/RE 缺少面板结构；
7. DEA 缺少多投入多产出或 DMU 数量严重不足；
8. Logit/Probit 但因变量不是二元变量；
9. Tobit 但没有截断/删失机制说明；
10. 研究目标要求因果识别，但数据只支持相关性分析且用户不接受降级解释。

⛔ **BLOCKING — 方法-数据匹配确认**

> **BLOCKING = HARD STOP：modeler 完成分析后，你必须停下来，将方法-数据匹配确认清单呈现给用户，等待用户明确确认或修改。禁止代替用户做决定、禁止假设用户同意、禁止跳过此步骤。这是流水线两个核心确认点之一（另一个是 Stage 4 用户审阅）。**

**程序化执行流程**：

1. 读取 modeler 输出的 `model_plan.md` 和 `method_fit_check.md`
2. **调用 `AskUserQuestion` 工具**，将方法-数据匹配确认清单呈现给用户：
   - 数据结构判断是否正确
   - 因变量类型判断是否正确
   - 推荐模型是否匹配研究问题
   - 不推荐模型及原因是否接受
   - 模型是否支持因果解释
   - 是否存在用户知道但数据中未体现的政策冲击/分组/断点/工具变量
   - 是否确认按该模型进入 Stage 3 编码
3. 用户确认后，在 `<workspace>/02_modeler/output/` 下写入 `user_confirmed.flag`
4. 如果用户要求修改，modeler 修改后重新走 1-3
5. **Stage 3 的 GATE 会检查 `user_confirmed.flag` 是否存在**，不存在则拒绝执行

**BLOCKER 硬约束**：若 `method_fit_check.md` 中 Stage 2 判定 = BLOCKER，不得写入 `user_confirmed.flag`，即使用户确认也不能进入 Stage 3。用户只能修改研究问题/变量/数据/模型，重新生成 `model_plan.md` 和 `method_fit_check.md`。只有 Stage 2 判定为 PASS 或 WARN 后，才能进入确认并写 flag。

写入 `<workspace>/02_modeler/output/user_confirmed.flag` 后，运行：

```bash
python scripts/update_session_state.py \
  --workspace <workspace> \
  --completed-stage 2 \
  --next-stage "Stage 3 coder_agent" \
  --checkpoint "<workspace>/02_modeler/output/user_confirmed.flag" \
  --output "<workspace>/02_modeler/output/model_plan.md" \
  --output "<workspace>/02_modeler/output/实证设计.md" \
  --output "<workspace>/02_modeler/output/method_fit_check.md" \
  --format "<用户确认的 output_format>"
```

方法-数据匹配确认内容（7 项）：

1. 数据结构判断是否正确；
2. 因变量类型判断是否正确；
3. 推荐模型是否匹配研究问题；
4. 不推荐模型及原因是否接受；
5. 模型是否支持因果解释；
6. 是否存在用户知道但数据中未体现的政策冲击、分组、断点或工具变量；
7. 是否确认按该模型进入 Stage 3 编码。

**模型选择原则：**模型选择必须以 `references/model_selection_tree.md` 定位结果和 `method_fit_check.md` 为准，不得使用固定优先级模板。不得因为某个方法"常见"就默认使用。

---

## Stage 3: 代码分析

**Stage 入口检查：**

- 当前 Stage: Stage 3
- 上游 BLOCKING flag:
  - `<workspace>/02_modeler/output/user_confirmed.flag`
- 必要输入:
  - `<workspace>/02_modeler/output/model_plan.md`
  - `<workspace>/02_modeler/output/实证设计.md`
  - `<workspace>/01_audit/output/variable_map.json`
  - manifest 中记录的数据文件路径
- 若 flag 不存在，拒绝执行 Stage 3。

🚧 **GATE**: Stage 2 完成；用户已确认方法-数据匹配；model_plan.md 存在

由 `agents/coder_agent.md` 执行。

执行规则：
- 若当前会话已明确持有本 Stage 指令，且 Stage 入口 self-check 通过，可直接执行；
- 若当前会话不确定本 Stage 具体职责、输出格式或审查维度，必须读取 `agents/coder_agent.md`；
- 禁止在未确认 Stage 职责时用通用逻辑替代 agent 指令。

**必须生成的基础结果：**
1. 描述性统计表
2. 相关系数表（变量数 ≤ 15 时必须生成）
3. 基准回归表或主模型结果表
4. 根据框架生成异质性、稳健性或分组分析表
5. 如果数据支持，生成趋势图或分组均值图

**稳健性检验不是可选项**：必须实际运行代码生成结果，不能写"稳健性检验结果备索"。

**输出**：`analysis.py` + `tables/*.tex` + `figures/*.png` + `results_summary.md` + `results.json` + `assets_manifest.json` + `model_diagnostics.md` + `run_log.md`

⛔ **BLOCKING — 用户审查代码和核心结果**

> 代码分析完成后，必须停下来让用户审查核心结果（效率值、系数方向、稳健性一致性等）和代码逻辑。用户确认后写入 `user_confirmed.flag`，再进入 Stage 4。这能避免代码问题遗留到写作阶段才发现，导致大面积返工。

写入 `<workspace>/03_coder/output/user_confirmed.flag` 后，运行：

```bash
python scripts/update_session_state.py \
  --workspace <workspace> \
  --completed-stage 3 \
  --next-stage "Stage 4 writer_agent" \
  --checkpoint "<workspace>/03_coder/output/user_confirmed.flag" \
  --output "<workspace>/03_coder/output/results_summary.md" \
  --output "<workspace>/03_coder/output/analysis.py" \
  --output "<workspace>/03_coder/output/tables" \
  --output "<workspace>/03_coder/output/figures" \
  --note "用户已确认核心结果"
```

---

## Stage 4: 论文写作

**Stage 入口检查：**

- 当前 Stage: Stage 4
- 上游 BLOCKING flag:
  - `<workspace>/03_coder/output/user_confirmed.flag`
- 必要输入:
  - `<workspace>/03_coder/output/results_summary.md`
  - `<workspace>/03_coder/output/results.json`
  - `<workspace>/03_coder/output/analysis.py`
  - `<workspace>/03_coder/output/tables/`
  - `<workspace>/03_coder/output/figures/`
  - `<workspace>/02_modeler/output/实证设计.md`
  - `<workspace>/02_modeler/output/method_fit_check.md`
  - `<workspace>/00_intake/output/framework.md`
- 若缺失结果摘要、results.json、代码文件或 method_fit_check.md，拒绝写作。writer 必须遵守 method_fit_check.md 中的解释边界，关键数字必须使用 results.json 中的 value_display。

🚧 **GATE**: Stage 3 完成；results_summary.md 和 tables/ 目录存在

由 `agents/writer_agent.md` 执行。

执行规则：
- 若当前会话已明确持有本 Stage 指令，且 Stage 入口 self-check 通过，可直接执行；
- 若当前会话不确定本 Stage 具体职责、输出格式或审查维度，必须读取 `agents/writer_agent.md`；
- 禁止在未确认 Stage 职责时用通用逻辑替代 agent 指令。

**输出格式取决于用户在 Stage 2 确认的输出格式**：

- **LaTeX 输出**（默认）：`paper_draft.tex` + `references_used.md` + `writing_checklist.md` + `policy_references.md`（可选）
- **Word 输出**：`paper_draft.md` + `references_used.md` + `writing_checklist.md` + `policy_references.md`（可选）— **不生成 .docx，由 Stage 5 脚本统一处理**

**Word 输出流程**（当用户选择 Word 格式时）：

1. writer 只将论文内容写为 `paper_draft.md`（公式用 LaTeX 语法，表格用 markdown 表格或嵌入 .tex 引用）
2. **不调用 pandoc，不调用 python-docx** — Word 生成由 Stage 5 的 `scripts/gen_docx.py` 统一完成
3. 若环境无 pandoc，Stage 5 会失败并提示安装，**禁止用 python-docx 手动组装正文或公式**

⛔ **BLOCKING — 用户审阅**

> **BLOCKING = HARD STOP：writer 完成初稿后，你必须将论文呈现给用户，等待用户审阅并提出修改意见。禁止自动跳过、禁止假设用户满意。这是流水线两个核心确认点之一（另一个是 Stage 2 方法-数据匹配确认）。**

**程序化执行流程**：

1. writer 完成初稿后，运行 `check_word_count.py --manifest <...>`，按 Stage 0 已确认的模式和 scope 统计。若状态为 SHORT，必须先询问用户（不得自动扩写），用户做出字数决策后再呈现论文审阅
2. 用户确认满意 → 在 `<workspace>/04_writer/output/` 下写入 `user_confirmed.flag`
3. 用户提出修改意见 → writer 按意见增量修改（只改需要改的段落，不重写整篇）→ 修改后重新调用 `AskUserQuestion` 确认
4. 最多 2 轮修改循环
5. 第 2 轮后仍未解决的问题记入"已知局限"，写入 flag 文件，继续 Stage 5
6. **Stage 5 的 GATE 会检查 `user_confirmed.flag` 是否存在**，不存在则拒绝执行

写入 `<workspace>/04_writer/output/user_confirmed.flag` 后，运行：

```bash
python scripts/update_session_state.py \
  --workspace <workspace> \
  --completed-stage 4 \
  --next-stage "Stage 5 reviewer_agent" \
  --checkpoint "<workspace>/04_writer/output/user_confirmed.flag" \
  --output "<workspace>/04_writer/output/paper_draft.tex（LaTeX）或 paper_draft.md（Word）" \
  --output "<workspace>/04_writer/output/references_used.md" \
  --note "初稿已由用户确认"
```

**写作规范**：详见 `references/writing_standards.md`

---

## Stage 5: 质量审查与最终整合

**Stage 入口检查：**

- 当前 Stage: Stage 5
- 上游 BLOCKING flag:
  - `<workspace>/04_writer/output/user_confirmed.flag`
- 必要输入:
  - 存在与 output_format 对应的 draft 文件：`paper_draft.tex`（LaTeX）或 `paper_draft.md`（Word）
  - `<workspace>/03_coder/output/results_summary.md`
  - `<workspace>/03_coder/output/results.json`
  - `<workspace>/03_coder/output/analysis.py`
  - `<workspace>/03_coder/output/assets_manifest.json`
  - `<workspace>/03_coder/output/tables/`
  - `<workspace>/03_coder/output/figures/`
  - `<workspace>/02_modeler/output/method_fit_check.md`
  - `<workspace>/02_modeler/output/model_plan.md`
  - **字数门禁**：检查 schema v2 的 `<workspace>/04_writer/output/word_count_report.json`。若 `status=SHORT`，只有 `decision=accept_short` 且 `confirmed_by_user=true` 才可继续；`decision=expand` 必须回到 Stage 4。`OVER` 作为 WARN 留痕。
- 若 draft 不存在，拒绝执行最终整合。若 method_fit_check.md 或 model_plan.md 缺失，方法复核无法执行，Stage 5 不得直接 PASS。

🚧 **GATE**: Stage 4 完成；用户已确认初稿；存在与 output_format 对应的 draft 文件；字数门禁已通过（OK/OVER，或 SHORT + 用户确认 accept_short）

**Step 1: 审查**（由 `agents/reviewer_agent.md` 执行）

执行规则：
- 若当前会话已明确持有本 Stage 指令，且 Stage 入口 self-check 通过，可直接执行；
- 若当前会话不确定本 Stage 具体职责、输出格式或审查维度，必须读取 `agents/reviewer_agent.md`；
- 禁止在未确认 Stage 职责时用通用逻辑替代 agent 指令。

6 维度审查：数字一致性、引用完整性、代码-论文一致性、方法正确性、写作质量、LaTeX 格式规范。

**Step 2: 验证脚本**

运行 `scripts/verify_consistency.py` 自动检查 paper 中的数字、引用、图表一致性。

### Stage 5 Word 输出硬流程

当 `output_format=docx` 时，Stage 5 必须按顺序执行：

1. `scripts/verify_consistency.py --format markdown`
2. `scripts/gen_docx.py`
3. `scripts/validate_docx.py`
4. `scripts/verify_consistency.py --format docx`
5. 汇总生成 `quality_check.md`

任一脚本返回 FAIL/BLOCKER，不得标记最终论文通过。

标准命令：

```bash
# --skip-word-count: 字数已在 Stage 4 由 check_word_count.py 检查过，这里跳过避免重复
python scripts/verify_consistency.py \
  --format markdown \
  --skip-word-count \
  --paper <workspace>/04_writer/output/paper_draft.md \
  --results <workspace>/03_coder/output/results_summary.md \
  --results-json <workspace>/03_coder/output/results.json \
  --output <workspace>/final_paper/markdown_consistency_report.md

python scripts/gen_docx.py \
  --manifest <workspace>/00_intake/output/manifest.json \
  --markdown <workspace>/04_writer/output/paper_draft.md \
  --output <workspace>/final_paper/paper_final.docx \
  --reference-doc <template.docx 可选> \
  --template-rules <workspace>/00_intake/output/template_rules.json \
  --assets-manifest <workspace>/03_coder/output/assets_manifest.json \
  --tables <workspace>/03_coder/output/tables \
  --figures <workspace>/03_coder/output/figures \
  --log <workspace>/final_paper/docx_build_log.md

python scripts/validate_docx.py \
  --docx <workspace>/final_paper/paper_final.docx \
  --markdown <workspace>/04_writer/output/paper_draft.md \
  --tables <workspace>/03_coder/output/tables \
  --figures <workspace>/03_coder/output/figures \
  --template-rules <workspace>/00_intake/output/template_rules.json \
  --assets-manifest <workspace>/03_coder/output/assets_manifest.json \
  --output <workspace>/final_paper/docx_validation_report.md

python scripts/verify_consistency.py \
  --format docx \
  --skip-word-count \
  --paper <workspace>/final_paper/paper_final.docx \
  --results <workspace>/03_coder/output/results_summary.md \
  --results-json <workspace>/03_coder/output/results.json \
  --output <workspace>/final_paper/docx_consistency_report.md
```

**Step 3: 修复**

根据审查报告修复 block 级问题。warn 级问题记入"已知局限"。

**Stage 5 修复权限边界**：

Stage 5 只能修改以下文件：
- `<workspace>/04_writer/output/paper_draft.md`（或 `paper_draft.tex`）
- `<workspace>/final_paper/*`

禁止修改以下文件（这些是上游 Stage 的产出，Stage 5 只读不写）：
- `<workspace>/03_coder/output/results.json`
- `<workspace>/03_coder/output/results_summary.md`
- `<workspace>/03_coder/output/analysis.py`
- `<workspace>/02_modeler/output/*`

当发现不一致时，处理方式如下：

1. **results_summary.md 与 results.json 不一致**：返回 Stage 3 重跑 summary，不得手改。results.json 是数字真源。
2. **paper_draft.md 中数字不在 results.json 中**：如果是 writer 多写了，直接改 paper；如果确实需要该数字，返回 Stage 3，将该数字加入 results.json 的 reportable_values。
3. **analysis.py 实现与 model_plan.md 不一致**：返回 Stage 3 修正代码，不得手改 results_summary.md 来掩盖问题。

**Step 4: 输出**

根据 Stage 2 确认的输出格式：

- **LaTeX 输出**：`paper_final.tex` + `quality_check.md` + `compile_log.txt`（如环境中有 xelatex）
- **Word 输出**：`paper_final.docx` + `quality_check.md`（由 `scripts/gen_docx.py` 从 `paper_draft.md` 生成）

### 最终质量门禁

Stage 5 结束前必须运行 `scripts/final_quality_gate.py`。

```bash
python scripts/final_quality_gate.py \
  --workspace <workspace> \
  --output <workspace>/final_paper/final_gate_report.md \
  --json-output <workspace>/final_paper/final_gate_report.json
```

若 `final_quality_gate.py` 返回 exit code 2，Stage 5 最终状态为 FAIL 或 INCOMPLETE，不得标记为 PASS。

`quality_check.md` 的 Final Verdict 必须与 `final_gate_report.json` 一致。Markdown 报告只用于阅读，不作为机器真源。

若二者冲突，以 `final_gate_report.json` 为准，并将冲突记录为 BLOCKER。

✅ **Checkpoint — 输出最终论文。**

输出 final paper 后，运行：

```bash
python scripts/update_session_state.py \
  --workspace <workspace> \
  --completed-stage 5 \
  --next-stage "Stage 6 expert_reviewer_agent (可选)" \
  --checkpoint "<workspace>/final_paper/paper_final.docx" \
  --output "<workspace>/final_paper/paper_final.docx" \
  --output "<workspace>/final_paper/quality_check.md"
```

---

## Stage 6: 独立专家审稿（可选）

**Stage 入口检查：**

- 当前 Stage: Stage 6
- 上游 checkpoint:
  - `<workspace>/final_paper/paper_final.tex` 或 `<workspace>/final_paper/paper_final.docx`
- 必要输入:
  - 最终论文文件
  - `references/independent_review_rubric.md`
  - `references/ai_patterns_zh.md`
  - `references/writing_standards.md`
- 隔离审稿人不得读取 `results_summary.md`、`analysis.py`、`model_plan.md`。

🚧 **GATE**: Stage 5 完成；paper_final.tex（或 .docx）存在

⛔ **BLOCKING — 用户选择**

> Stage 5 完成后，将最终论文呈现给用户。用户审阅后，询问：
> "论文已全部完成。是否需要启动独立专家审稿人？审稿人将以经管领域资深专家的视角审查方法设计、统计原理和格式，并给出 AI 味评分（0-100 分，低于 30 分为安全）。"
>
> 用户选择"是" → 启动独立审稿人
> 用户选择"否" → 流水线结束

**隔离要求**：
- 独立审稿人通过 Agent 工具调度，不与 Stage 1-5 共享上下文
- 只读取最终论文和 reference 文件，不读任何中间产物
- 不修改论文内容，只输出审查报告

**由 `agents/expert_reviewer_agent.md` 执行**

执行规则：
- 独立审稿人通过 Agent 工具调度，不与 Stage 1-5 共享上下文；
- 只读取最终论文和 reference 文件，不读任何中间产物；
- 不修改论文内容，只输出审查报告。

**审查维度**：
1. 方法设计审查：模型选择合理性、假设检验完整性、变量设定逻辑、方法-数据匹配度
2. 统计原理审查：统计检验使用正确性、显著性解释恰当性、统计错误排查、因果推断合理性
3. 格式审查：论文结构、表格格式、参考文献、图表编号
4. AI 味评分：4 维度 16 项指标打分（详见 `references/independent_review_rubric.md`），给出总分和各维度得分

**输出**：`<workspace>/06_expert_review/output/expert_review_report.md`

✅ **Checkpoint — 输出审稿报告（如用户选择启动）。流水线结束。

如启动专家审稿，完成后运行：

```bash
python scripts/update_session_state.py \
  --workspace <workspace> \
  --completed-stage 6 \
  --next-stage "流水线已结束" \
  --checkpoint "<workspace>/06_expert_review/output/expert_review_report.md" \
  --output "<workspace>/06_expert_review/output/expert_review_report.md" \
  --note "独立专家审稿已完成"
```

---

## Word 格式后处理

Word 输出与模板处理规则详见：

- `references/word_format_rules.md`

仅当 `output_format=docx` 时读取该文件。

---

## Reference 路由

详细阶段路由见：

- `references/routing_map.md`

本文件只保留全局流程和红线。各 Stage 不得默认读取全部 reference 文件。

## 支持的文件格式

| 类型 | 格式 | 说明 |
|------|------|------|
| 研究框架 | `.docx` `.md` `.pdf` | docx 用 python-docx，pdf 用 pypdf |
| 建模数据 | `.xlsx` `.csv` | 必须，可多个文件/Sheet |
| LaTeX 模板 | `.tex` | 可选，缺失则生成默认模板 |
| Word 模板 | `.docx` | 可选，与 LaTeX 模板二选一或同时提供（需用户确认） |
| 参考文献 | PDF 文件或目录 | 可选 |

## 推荐文件命名

```
研究框架.docx / research_framework.docx / 研究框架.md
建模数据.xlsx / data.xlsx / 数据.xlsx
论文模板.tex / template.tex
论文模板.docx / template.docx
references/ / refs/ / 文献/
```

## 适合 / 不适合

**适合：**
- 期末课程论文
- 本科/硕士课程作业
- 已有数据和大致研究主题的实证论文

**不适合：**
- 需要投稿发表的高强度论文
- 没有任何数据的论文
- 需要复杂因果识别但数据不支持的研究

## 工作目录结构

实际工作目录为：

```text
paper_workspace/<run_id>/
```

各 Stage 的详细输入输出以 `references/routing_map.md` 为准。

常见关键产物：

- `<workspace>/00_intake/output/manifest.json`
- `<workspace>/02_modeler/output/method_fit_check.md`
- `<workspace>/03_coder/output/results.json`
- `<workspace>/03_coder/output/assets_manifest.json`
- `<workspace>/04_writer/output/paper_draft.md` 或 `paper_draft.tex`
- `<workspace>/04_writer/output/word_count_report.json`
- `<workspace>/final_paper/paper_final.docx` 或 `paper_final.tex`
- `<workspace>/final_paper/final_gate_report.md`

## Agent 文件

- 数据审计：`agents/audit_agent.md`
- 研究设计：`agents/modeler_agent.md`
- 编程手：`agents/coder_agent.md`
- 论文手：`agents/writer_agent.md`
- 审查手：`agents/reviewer_agent.md`
- 独立审稿人：`agents/expert_reviewer_agent.md`

## 错误处理

| 错误 | 处理 |
|------|------|
| 找不到研究框架 | 提示用户上传，列出支持的格式 |
| 找不到数据文件 | 提示用户上传 |
| 多个候选文件 | 列出候选，询问用户选择 |
| DOCX/PDF 解析失败 | 提示用户转为 md 格式 |
| 数据审计发现严重问题 | 列出问题，询问用户是否继续 |
| 编程手代码报错 | 自动分析错误、修复并重试一次；仍失败则报告用户 |
| 编程手写 method_approximation.flag | 暂停执行，读取 flag 内容（原始方法、替代方案、局限），呈现给用户决定是否接受替代方案 |
| 论文手缺少章节 | 补充缺失章节的占位段落 |
| LaTeX 编译错误 | 检查语法错误并修复 |

## 注意事项

- 建议用户提供尽量清洗好的数据
- 编程手的代码必须可复现（设置随机种子）
- 表格数据必须来自真实计算，不允许编造
- 引用格式统一使用 GB/T 7714
- 最终输出的 .tex 文件应能直接编译
- `<workspace>/` 目录保留中间产物，方便用户检查和调试
