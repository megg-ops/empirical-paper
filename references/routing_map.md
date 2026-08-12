# 阶段引用路由表

本文件定义每个阶段必须读取的最小上下文。agent 不得默认读取整个 skill 目录。

## 通用读取规则

每个 Stage 默认只读取：

1. `<workspace>/session_state.md`
2. `<workspace>/00_intake/output/manifest.json`
3. 当前 Stage 对应的 agent 文件
4. 本文件列出的必须引用
5. 当前 Stage 明确需要的上游输出

如果上下文不足，只能读取本阶段相关文件，不得全量读取整个项目。

---

## Stage 0 材料识别

必须 agent：
- `SKILL.md`

必须引用：
- `references/handoff_schemas.md`

可选（仅当存在 Word 模板时）：
- `references/word_format_rules.md`

预期产出：
- `<workspace>/00_intake/output/manifest.json`
- `<workspace>/00_intake/output/framework.md`
- `<workspace>/00_intake/output/template_text.md`
- `<workspace>/00_intake/output/template_rules.json`

---

## Stage 1 数据审计

必须 agent：
- `agents/audit_agent.md`

必须上游产出：
- `<workspace>/00_intake/output/manifest.json`
- `<workspace>/00_intake/output/framework.md`
- manifest 的 `data_files`（CSV/XLSX）

必须脚本：
- `scripts/audit_data.py`（profile → 受限语义映射 → finalize → validate）

预期产出：
- `<workspace>/01_audit/output/data_audit.md`
- `<workspace>/01_audit/output/variable_map.json`（schema v2；仅 PASS/WARN 可下传）

---

## Stage 2 研究设计

必须 agent：
- `agents/modeler_agent.md`

必须引用：
- `references/model_selection_tree.md`
- `references/method_guardrails.md`

必须上游产出：
- `<workspace>/00_intake/output/framework.md`
- `<workspace>/01_audit/output/data_audit.md`
- `<workspace>/01_audit/output/variable_map.json`

预期产出：
- `<workspace>/02_modeler/output/model_plan.md`
- `<workspace>/02_modeler/output/实证设计.md`
- `<workspace>/02_modeler/output/method_fit_check.md`
- `<workspace>/02_modeler/output/user_confirmed.flag`

---

## Stage 3 代码分析

必须 agent：
- `agents/coder_agent.md`

必须引用：
- `references/results_schema.md`

必须上游产出：
- `<workspace>/00_intake/output/manifest.json`
- `<workspace>/01_audit/output/variable_map.json`
- `<workspace>/02_modeler/output/model_plan.md`
- `<workspace>/02_modeler/output/实证设计.md`
- `<workspace>/02_modeler/output/method_fit_check.md`

预期产出：
- `<workspace>/03_coder/output/analysis.py`
- `<workspace>/03_coder/output/results.json`
- `<workspace>/03_coder/output/results_summary.md`
- `<workspace>/03_coder/output/assets_manifest.json`
- `<workspace>/03_coder/output/tables/`
- `<workspace>/03_coder/output/figures/`
- `<workspace>/03_coder/output/model_diagnostics.md`
- `<workspace>/03_coder/output/run_log.md`

---

## Stage 4 论文写作

必须 agent：
- `agents/writer_agent.md`

必须引用：
- `references/writing_standards.md`
- `references/ai_patterns_zh.md`
- `references/results_schema.md`

可选引用：
- `references/latex_formatting.md`（仅当 output_format=latex）
- `references/policy_search_protocol.md`（仅当需要政策搜索）
- `references/word_format_rules.md`（仅当 output_format=docx）

必须上游产出：
- `<workspace>/00_intake/output/framework.md`
- `<workspace>/02_modeler/output/实证设计.md`
- `<workspace>/02_modeler/output/method_fit_check.md`
- `<workspace>/03_coder/output/results.json`
- `<workspace>/03_coder/output/results_summary.md`
- `<workspace>/03_coder/output/assets_manifest.json`
- `<workspace>/03_coder/output/tables/`
- `<workspace>/03_coder/output/figures/`

可选（仅当存在 Word 模板时）：
- `<workspace>/00_intake/output/template_text.md`
- `<workspace>/00_intake/output/template_rules.json`

预期产出：
- `<workspace>/04_writer/output/paper_draft.md` 或 `<workspace>/04_writer/output/paper_draft.tex`
- `<workspace>/04_writer/output/references_used.md`
- `<workspace>/04_writer/output/writing_checklist.md`
- `<workspace>/04_writer/output/word_count_report.json`
- `<workspace>/04_writer/output/user_wordcount_decision.json`（仅当用户做了字数决策）
- `<workspace>/04_writer/output/user_confirmed.flag`

---

## Stage 5 质量审查与最终整合

必须 agent：
- `agents/reviewer_agent.md`

必须引用：
- `references/review_rubric.md`
- `references/results_schema.md`
- `references/failure_modes.md`

可选引用：
- `references/latex_formatting.md`（仅当 output_format=latex）
- `references/word_format_rules.md`（仅当 output_format=docx）
- `references/ai_patterns_zh.md`（仅当审查写作风格时）

必须上游产出：
- `<workspace>/00_intake/output/manifest.json`
- `<workspace>/02_modeler/output/method_fit_check.md`
- `<workspace>/03_coder/output/results.json`
- `<workspace>/03_coder/output/assets_manifest.json`
- `<workspace>/04_writer/output/paper_draft.md` 或 `<workspace>/04_writer/output/paper_draft.tex`
- `<workspace>/04_writer/output/word_count_report.json`
- `<workspace>/04_writer/output/user_confirmed.flag`

可选（仅当存在 Word 模板时）：
- `<workspace>/00_intake/output/template_rules.json`

预期产出：
- `<workspace>/final_paper/paper_final.docx` 或 `<workspace>/final_paper/paper_final.tex`
- `<workspace>/final_paper/docx_build_log.md`
- `<workspace>/final_paper/docx_validation_report.md`
- `<workspace>/final_paper/markdown_consistency_report.md`
- `<workspace>/final_paper/docx_consistency_report.md`
- `<workspace>/final_paper/quality_check.md`
- `<workspace>/final_paper/final_gate_report.md`

---

## Stage 6 独立专家审稿

必须 agent：
- `agents/expert_reviewer_agent.md`

必须引用：
- `references/independent_review_rubric.md`
- `references/ai_patterns_zh.md`

必须上游产出：
- `<workspace>/final_paper/paper_final.docx` 或 `<workspace>/final_paper/paper_final.tex`
- `<workspace>/final_paper/final_gate_report.md`

预期产出：
- `<workspace>/06_expert_review/output/expert_review_report.md`

重要：
- Stage 6 专家审稿人不得读取 Stage 1-4 中间产出，除非用户明确要求追溯级审计。
