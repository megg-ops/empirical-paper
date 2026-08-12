# V2 Demo

`demo_case/` 是输入材料：一份研究框架和一个含 `data`、`variable_dictionary`、`README` 三个 Sheet 的合成 XLSX。`paper_workspace/demo_digital_revenue_v2/` 是用 V2 工作流重建的完整产物。

关键证据：

- `01_audit/output/variable_map.json`：schema v2；脚本全量扫描，主分析表为 `data`；
- `01_audit/output/data_audit.md`：WARN 仅来自 README Sheet 的 1 条重复说明行，主分析表没有重复；
- `03_coder/output/results.json`：论文数字真源；
- `04_writer/output/word_count_report.json`：用户确认范围 5000–7000，实际 5082，状态 OK；
- `final_paper/final_gate_report.json`：最终 verdict 为 PASS；
- `final_paper/paper_final.docx`：完整 Word 成品。

从仓库根目录可重跑核心阶段：

```bash
python scripts/audit_data.py validate \
  --variable-map examples/paper_workspace/demo_digital_revenue_v2/01_audit/output/variable_map.json

python examples/paper_workspace/demo_digital_revenue_v2/03_coder/output/analysis.py

python scripts/check_word_count.py \
  --paper examples/paper_workspace/demo_digital_revenue_v2/04_writer/output/paper_draft.md \
  --manifest examples/paper_workspace/demo_digital_revenue_v2/00_intake/output/manifest.json \
  --output examples/paper_workspace/demo_digital_revenue_v2/04_writer/output/word_count_report.json

python scripts/final_quality_gate.py \
  --workspace examples/paper_workspace/demo_digital_revenue_v2 \
  --format docx \
  --output examples/paper_workspace/demo_digital_revenue_v2/final_paper/final_gate_report.md \
  --json-output examples/paper_workspace/demo_digital_revenue_v2/final_paper/final_gate_report.json
```

Demo 数据为合成数据，只用于验证工作流，不应被解释为现实企业证据。
