import json

from stage_guard import check_stage


def _intake(tmp_path, word_count):
    ws = tmp_path / "run"
    output = ws / "00_intake/output"
    output.mkdir(parents=True)
    data = ws / "data.csv"
    data.write_text("id,x\n1,2\n", encoding="utf-8")
    (output / "framework.md").write_text("framework", encoding="utf-8")
    (output / "manifest.json").write_text(json.dumps({
        "data_files": [str(data)],
        "paper_requirements": {"word_count": word_count},
    }), encoding="utf-8")
    return ws


def test_stage1_requires_confirmed_word_count(tmp_path):
    ws = _intake(tmp_path, {"mode": "minimum", "minimum": 1000, "confirmed_by_user": False})
    assert check_stage(1, ws)["ok"] is False


def test_stage2_rejects_v1_variable_map(tmp_path):
    ws = _intake(tmp_path, {"mode": "minimum", "minimum": 1000, "confirmed_by_user": True})
    output = ws / "01_audit/output"
    output.mkdir(parents=True)
    (output / "data_audit.md").write_text("audit", encoding="utf-8")
    (output / "variable_map.json").write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
    assert check_stage(2, ws)["ok"] is False


def test_stage2_accepts_v2_warn(tmp_path):
    ws = _intake(tmp_path, {"mode": "minimum", "minimum": 1000, "confirmed_by_user": True})
    output = ws / "01_audit/output"
    output.mkdir(parents=True)
    (output / "data_audit.md").write_text("audit", encoding="utf-8")
    (output / "variable_map.json").write_text(json.dumps({"schema_version": 2, "status": "WARN"}), encoding="utf-8")
    assert check_stage(2, ws)["ok"] is True
