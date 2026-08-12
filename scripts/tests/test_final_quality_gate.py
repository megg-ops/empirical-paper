import json

from final_quality_gate import run_gate
from quality_contract import make_quality_result, write_json


def _workspace(tmp_path):
    ws = tmp_path / "run"
    (ws / "02_modeler/output").mkdir(parents=True)
    (ws / "03_coder/output").mkdir(parents=True)
    (ws / "04_writer/output").mkdir(parents=True)
    (ws / "final_paper").mkdir(parents=True)
    (ws / "02_modeler/output/method_fit_check.md").write_text("## 7. Stage 2 判定\nPASS", encoding="utf-8")
    (ws / "03_coder/output/results.json").write_text(json.dumps({"reportable_values": [{"key": "x"}]}), encoding="utf-8")
    (ws / "04_writer/output/word_count_report.json").write_text(json.dumps({
        "schema_version": 2, "status": "OK"
    }), encoding="utf-8")
    (ws / "final_paper/paper_final.tex").write_text("paper", encoding="utf-8")
    return ws


def test_final_gate_reads_json_not_markdown_words(tmp_path):
    ws = _workspace(tmp_path)
    result = make_quality_result("verify", {"all": {"status": "PASS", "issues": ["可提及 BLOCKER 字样"]}})
    write_json(result, str(ws / "final_paper/markdown_consistency_report.json"))
    gate = run_gate(str(ws), "latex")
    assert gate["verdict"] == "PASS"


def test_missing_required_json_is_incomplete(tmp_path):
    ws = _workspace(tmp_path)
    (ws / "final_paper/paper_final.docx").write_bytes(b"placeholder")
    gate = run_gate(str(ws), "docx")
    assert gate["verdict"] == "INCOMPLETE"


def test_source_fail_blocks(tmp_path):
    ws = _workspace(tmp_path)
    result = make_quality_result("verify", {"x": {"status": "BLOCKER", "issues": ["bad"]}})
    write_json(result, str(ws / "final_paper/markdown_consistency_report.json"))
    gate = run_gate(str(ws), "latex")
    assert gate["verdict"] == "FAIL"


def test_short_word_count_requires_user_decision(tmp_path):
    ws = _workspace(tmp_path)
    (ws / "04_writer/output/word_count_report.json").write_text(json.dumps({
        "schema_version": 2, "status": "SHORT"
    }), encoding="utf-8")
    result = make_quality_result("verify", {"all": {"status": "PASS", "issues": []}})
    write_json(result, str(ws / "final_paper/markdown_consistency_report.json"))
    assert run_gate(str(ws), "latex")["verdict"] == "FAIL"
