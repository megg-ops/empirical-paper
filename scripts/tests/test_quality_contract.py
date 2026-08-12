import json

import pytest

from quality_contract import make_quality_result, read_quality_result, verdict_from_checks


def test_verdict_uses_structured_status_not_issue_words():
    result = make_quality_result("demo", {
        "review": {"status": "PASS", "issues": ["文本可出现 BLOCKER 字样但不是状态"]}
    })
    assert result["verdict"] == "PASS"


@pytest.mark.parametrize("status,verdict", [
    ("PASS", "PASS"), ("WARN", "WARN"), ("INCOMPLETE", "INCOMPLETE"), ("BLOCKER", "FAIL")
])
def test_verdict_mapping(status, verdict):
    assert verdict_from_checks({"x": {"status": status}}) == verdict


def test_read_rejects_free_form_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"verdict": "PASS"}), encoding="utf-8")
    with pytest.raises(ValueError):
        read_quality_result(str(path))
