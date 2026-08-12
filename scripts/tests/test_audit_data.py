import json

import pandas as pd

from audit_data import build_profile, finalize_profile, overall_status, assess_joins


def test_csv_profile_is_full_and_deterministic(tmp_path):
    path = tmp_path / "data.csv"
    pd.DataFrame({"id": [1, 2, 3], "x": [1.0, None, 3.0], "group": ["a", "a", "b"]}).to_csv(path, index=False)
    result = build_profile([str(path)])
    assert result["schema_version"] == 2
    assert result["primary_table"].endswith("data.csv::")
    table = result["tables"][0]
    assert table["row_count"] == 3
    assert table["variables"][1]["observed_pattern"]["missing_count"] == 1
    assert "id" in table["unique_key_candidates"]


def test_multiple_xlsx_sheets_require_primary(tmp_path):
    path = tmp_path / "book.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame({"id": [1]}).to_excel(writer, sheet_name="data", index=False)
        pd.DataFrame({"name": ["id"]}).to_excel(writer, sheet_name="dictionary", index=False)
    result = build_profile([str(path)])
    assert result["status"] == "NEEDS_CONFIRMATION"
    assert any(i["code"] == "primary_table_unresolved" for i in result["issues"])


def test_finalize_requires_confirmed_observation_unit(tmp_path):
    path = tmp_path / "data.csv"
    pd.DataFrame({"id": [1, 2], "y": [3.0, 4.0]}).to_csv(path, index=False)
    result = finalize_profile(build_profile([str(path)]), {"variables": []})
    assert result["status"] == "NEEDS_CONFIRMATION"


def test_finalize_adds_roles_and_capabilities(tmp_path):
    path = tmp_path / "panel.csv"
    pd.DataFrame({"firm": [1, 1], "year": [2020, 2021], "y": [2.0, 3.0]}).to_csv(path, index=False)
    semantics = {
        "observation_unit": {"label": "企业-年份", "status": "confirmed", "source": "user", "evidence": []},
        "variables": [
            {"column": "firm", "semantic_type": "identifier", "roles": ["entity_id"], "status": "confirmed", "source": "framework", "confidence": "high"},
            {"column": "year", "semantic_type": "date", "roles": ["time"], "status": "confirmed", "source": "framework", "confidence": "high"},
            {"column": "y", "semantic_type": "continuous", "roles": ["outcome"], "status": "confirmed", "source": "framework", "confidence": "high"},
        ],
        "structure_assessment": {"candidates": [{"type": "panel", "confidence": "high"}], "confirmed_type": "panel"},
    }
    result = finalize_profile(build_profile([str(path)]), semantics)
    assert result["status"] in {"PASS", "WARN"}
    assert result["method_capabilities"]["panel_structure"]["supported"] is True
    assert "recommended_model" not in result


def test_blocker_precedes_other_statuses():
    assert overall_status([{"severity": "WARN", "resolution": None}, {"severity": "BLOCKER", "resolution": None}]) == "BLOCKER"


def test_join_assessment_detects_row_expansion(tmp_path):
    left = tmp_path / "left.csv"
    right = tmp_path / "right.csv"
    pd.DataFrame({"id": [1, 2]}).to_csv(left, index=False)
    pd.DataFrame({"id": [1, 1, 2], "z": [3, 4, 5]}).to_csv(right, index=False)
    profile = build_profile([str(left), str(right)], primary=str(left))
    left_id = f"{left.resolve()}::"
    right_id = f"{right.resolve()}::"
    assessments, issues = assess_joins(profile, [{
        "left_table": left_id, "right_table": right_id,
        "left_keys": ["id"], "right_keys": ["id"], "critical": True,
        "confirmed_by_user": False,
    }])
    assert assessments[0]["row_expansion_factor"] == 1.5
    assert assessments[0]["right_key_unique"] is False
    assert {i["code"] for i in issues} == {"join_row_expansion", "join_confirmation_required"}


def test_declared_constraints_are_hard_checked(tmp_path):
    path = tmp_path / "data.csv"
    pd.DataFrame({"id": [1, 2], "treated": [0, 2]}).to_csv(path, index=False)
    semantics = {
        "observation_unit": {"label": "个体", "status": "confirmed", "source": "user", "evidence": []},
        "variables": [{
            "column": "treated", "semantic_type": "binary", "roles": ["treatment"],
            "status": "confirmed", "source": "user", "confidence": "high",
            "constraints": {"allowed_values": [0, 1], "required_non_missing": True},
        }],
    }
    result = finalize_profile(build_profile([str(path)]), semantics)
    assert result["status"] == "BLOCKER"
    assert any(i["code"] == "allowed_values_violation" for i in result["issues"])


def test_only_user_can_resolve_confirmation(tmp_path):
    path = tmp_path / "data.csv"
    pd.DataFrame({"id": [1, 2]}).to_csv(path, index=False)
    profile = build_profile([str(path)])
    semantics = {
        "observation_unit": {"label": "个体", "status": "candidate", "source": "framework", "evidence": []},
        "resolutions": [{"code": "semantic_confirmation_required", "resolved_by": "model", "explanation": "猜测"}],
    }
    result = finalize_profile(profile, semantics)
    assert result["status"] == "BLOCKER"
    assert any(i["code"] == "invalid_issue_resolution" for i in result["issues"])
