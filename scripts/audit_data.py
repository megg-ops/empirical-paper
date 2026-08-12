#!/usr/bin/env python3
"""结构化表格数据的确定性审计工具。

客观画像由本脚本全量计算；语义标注只能通过 ``finalize`` 子命令合并。
支持 CSV 与 XLSX，不修改原始数据。
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SCHEMA_VERSION = 2
ALLOWED_ROLES = {
    "observation_id", "entity_id", "time", "outcome", "predictor",
    "control", "treatment", "instrument", "running_variable",
    "fixed_effect", "cluster", "weight", "group", "input", "output",
    "environment", "auxiliary",
}
CRITICAL_ROLES = {
    "observation_id", "entity_id", "time", "outcome", "predictor",
    "treatment", "instrument", "running_variable", "input", "output",
}
ALLOWED_SEMANTIC_TYPES = {
    "continuous", "binary", "ordinal", "nominal", "count", "proportion",
    "date", "datetime", "identifier", "text", "unknown",
}
ALLOWED_SOURCES = {"framework", "data_dictionary", "user"}
ALLOWED_CONFIDENCE = {"low", "medium", "high"}
STATUS_RANK = {"PASS": 0, "INFO": 1, "WARN": 2, "NEEDS_CONFIRMATION": 3, "BLOCKER": 4}


def _json_value(value: Any) -> Any:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not math.isfinite(float(value)) else float(value)
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if isinstance(value, np.bool_):
        return bool(value)
    return str(value) if not isinstance(value, (str, int, bool)) else value


def _issue(code: str, severity: str, message: str, *, evidence: Any = None) -> dict:
    item = {"code": code, "severity": severity, "message": message, "resolution": None}
    if evidence is not None:
        item["evidence"] = evidence
    return item


def _read_tables(path: Path) -> list[tuple[str | None, pd.DataFrame]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return [(None, pd.read_csv(path))]
    if suffix == ".xlsx":
        book = pd.ExcelFile(path, engine="openpyxl")
        return [(sheet, book.parse(sheet_name=sheet)) for sheet in book.sheet_names]
    raise ValueError(f"不支持的数据格式: {path.suffix}（仅支持 .csv/.xlsx）")


def _storage_type(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_integer_dtype(series):
        return "integer"
    if pd.api.types.is_float_dtype(series):
        return "float"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    return "string"


def _profile_column(name: str, series: pd.Series) -> tuple[dict, list[dict]]:
    issues: list[dict] = []
    total = len(series)
    missing = int(series.isna().sum())
    non_null = series.dropna()
    unique = int(non_null.nunique(dropna=True))
    samples = [_json_value(v) for v in non_null.drop_duplicates().head(10).tolist()]
    pattern: dict[str, Any] = {
        "row_count": total,
        "non_null_count": total - missing,
        "missing_count": missing,
        "missing_rate": round(missing / total, 6) if total else None,
        "unique_count": unique,
        "sample_values": samples,
    }

    numeric = pd.to_numeric(non_null, errors="coerce")
    numeric_success = int(numeric.notna().sum())
    pattern["numeric_parse_rate"] = round(numeric_success / len(non_null), 6) if len(non_null) else None
    if numeric_success:
        finite = numeric[np.isfinite(numeric)]
        pattern["infinite_count"] = int(numeric_success - len(finite))
        if len(finite):
            desc = finite.quantile([0, .25, .5, .75, 1]).to_dict()
            pattern["numeric_summary"] = {
                "min": _json_value(desc[0.0]), "q1": _json_value(desc[0.25]),
                "median": _json_value(desc[0.5]), "q3": _json_value(desc[0.75]),
                "max": _json_value(desc[1.0]), "mean": _json_value(finite.mean()),
                "std": _json_value(finite.std()),
            }
        if pattern["infinite_count"]:
            issues.append(_issue("infinite_values", "WARN", f"{name} 含无穷值", evidence=pattern["infinite_count"]))

    if total and missing == total:
        issues.append(_issue("all_missing", "WARN", f"{name} 全部为空；是否为关键变量需结合语义确认"))
    elif unique <= 1 and total:
        issues.append(_issue("constant_column", "INFO", f"{name} 为常量列或无有效变化"))
    if 1 < unique <= 20:
        counts = non_null.value_counts(dropna=False).head(20)
        pattern["value_counts"] = [
            {"value": _json_value(k), "count": int(v)} for k, v in counts.items()
        ]

    return {
        "column": name,
        "storage_type": _storage_type(series),
        "observed_pattern": pattern,
        "semantic_mapping": {
            "semantic_type": None, "unit": None, "roles": [],
            "status": "unmapped", "source": None, "confidence": None,
            "evidence": [], "constraints": {},
        },
    }, issues


def _table_profile(path: Path, sheet: str | None, frame: pd.DataFrame) -> tuple[dict, list[dict]]:
    issues: list[dict] = []
    table_ref = {"source_path": path.as_posix(), "sheet": sheet}
    duplicate_columns = frame.columns[frame.columns.duplicated()].astype(str).tolist()
    if duplicate_columns:
        issues.append(_issue("duplicate_columns", "BLOCKER", "存在重复列名", evidence={**table_ref, "columns": duplicate_columns}))
    duplicate_rows = int(frame.duplicated().sum())
    if duplicate_rows:
        issues.append(_issue("duplicate_rows", "WARN", "存在完全重复行", evidence={**table_ref, "count": duplicate_rows}))
    if frame.empty or len(frame.columns) == 0:
        issues.append(_issue("empty_table", "BLOCKER", "数据表为空或没有列", evidence=table_ref))

    variables = []
    for col in frame.columns:
        profile, col_issues = _profile_column(str(col), frame[col])
        variables.append(profile)
        issues.extend(col_issues)

    unique_candidates = [
        str(col) for col in frame.columns
        if len(frame) and frame[col].notna().all() and frame[col].nunique(dropna=True) == len(frame)
    ]
    return {
        # 保留调用方给出的相对路径，避免在可提交产物中写入开发机绝对路径。
        "source_path": path.as_posix(),
        "sheet": sheet,
        "row_count": int(len(frame)),
        "column_count": int(len(frame.columns)),
        "columns": [str(c) for c in frame.columns],
        "duplicate_row_count": duplicate_rows,
        "unique_key_candidates": unique_candidates,
        "variables": variables,
    }, issues


def _table_id(path: str, sheet: str | None) -> str:
    return f"{Path(path).as_posix()}::{sheet or ''}"


def build_profile(data_paths: list[str], primary: str | None = None) -> dict:
    tables: list[dict] = []
    issues: list[dict] = []
    for raw in data_paths:
        path = Path(raw)
        if not path.exists():
            issues.append(_issue("missing_file", "BLOCKER", f"数据文件不存在: {raw}"))
            continue
        try:
            for sheet, frame in _read_tables(path):
                profile, table_issues = _table_profile(path, sheet, frame)
                tables.append(profile)
                issues.extend(table_issues)
        except Exception as exc:
            issues.append(_issue("read_failure", "BLOCKER", f"读取失败: {raw}: {exc}"))

    primary_id = None
    if primary:
        wanted_path, sep, wanted_sheet = primary.partition("::")
        primary_id = _table_id(wanted_path, wanted_sheet if sep else None)
        if primary_id not in {_table_id(t["source_path"], t["sheet"]) for t in tables}:
            issues.append(_issue("invalid_primary_table", "BLOCKER", f"指定主分析表不存在: {primary}"))
    elif len(tables) == 1:
        primary_id = _table_id(tables[0]["source_path"], tables[0]["sheet"])
    elif len(tables) > 1:
        issues.append(_issue(
            "primary_table_unresolved", "NEEDS_CONFIRMATION",
            "存在多个数据表，必须确认主分析表；脚本不会自动猜测",
            evidence=[_table_id(t["source_path"], t["sheet"]) for t in tables],
        ))

    result = {
        "schema_version": SCHEMA_VERSION,
        "kind": "variable_map",
        "status": "PASS",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "audit_scope": {"formats": ["csv", "xlsx"], "scan": "full", "raw_data_modified": False},
        "primary_table": primary_id,
        "tables": tables,
        "observation_unit": {"label": None, "status": "unmapped", "source": None, "evidence": []},
        "join_assessments": [],
        "structure_assessment": {"candidates": [], "confirmed_type": None},
        "method_capabilities": {},
        "issues": issues,
    }
    result["status"] = overall_status(issues)
    return result


def overall_status(issues: list[dict]) -> str:
    unresolved = [i["severity"] for i in issues if not i.get("resolution")]
    if not unresolved:
        return "PASS"
    highest = max(unresolved, key=lambda x: STATUS_RANK.get(x, 0))
    return highest if highest in {"BLOCKER", "NEEDS_CONFIRMATION", "WARN"} else "PASS"


def _find_primary(result: dict) -> dict | None:
    primary = result.get("primary_table")
    for table in result.get("tables", []):
        if _table_id(table["source_path"], table.get("sheet")) == primary:
            return table
    return None


def _find_table(result: dict, table_id: str) -> dict | None:
    for table in result.get("tables", []):
        if _table_id(table["source_path"], table.get("sheet")) == table_id:
            return table
    return None


def _load_profiled_table(table: dict) -> pd.DataFrame:
    path = Path(table["source_path"])
    tables = dict((sheet or "", frame) for sheet, frame in _read_tables(path))
    return tables[table.get("sheet") or ""]


def assess_joins(result: dict, requests: list[dict]) -> tuple[list[dict], list[dict]]:
    """全量计算候选连接键质量，不输出合并后的数据。"""
    assessments, issues = [], []
    for request in requests:
        left_id, right_id = request.get("left_table"), request.get("right_table")
        left_meta, right_meta = _find_table(result, left_id), _find_table(result, right_id)
        left_keys, right_keys = request.get("left_keys", []), request.get("right_keys", [])
        if not left_meta or not right_meta or not left_keys or len(left_keys) != len(right_keys):
            issues.append(_issue("invalid_join_request", "BLOCKER", "候选连接请求无效", evidence=request))
            continue
        left, right = _load_profiled_table(left_meta), _load_profiled_table(right_meta)
        if not set(left_keys) <= set(left.columns) or not set(right_keys) <= set(right.columns):
            issues.append(_issue("invalid_join_keys", "BLOCKER", "候选连接键不存在", evidence=request))
            continue
        left_nonnull = left[left_keys].notna().all(axis=1)
        right_nonnull = right[right_keys].notna().all(axis=1)
        left_key_frame = left.loc[left_nonnull, left_keys]
        right_key_frame = right.loc[right_nonnull, right_keys].copy()
        right_key_frame.columns = left_keys
        right_unique = right_key_frame.drop_duplicates()
        left_unique = left_key_frame.drop_duplicates()
        left_matches = left_key_frame.merge(right_unique, how="inner", on=left_keys)
        right_matches = right_key_frame.merge(left_unique, how="inner", on=left_keys)
        merged = left.merge(right, how="left", left_on=left_keys, right_on=right_keys)
        assessment = {
            "left_table": left_id, "right_table": right_id,
            "left_keys": left_keys, "right_keys": right_keys,
            "left_key_unique": not left_key_frame.duplicated().any(),
            "right_key_unique": not right_key_frame.duplicated().any(),
            "left_non_null_key_rows": int(len(left_key_frame)),
            "right_non_null_key_rows": int(len(right_key_frame)),
            "left_match_rate": round(len(left_matches) / len(left_key_frame), 6) if len(left_key_frame) else None,
            "right_match_rate": round(len(right_matches) / len(right_key_frame), 6) if len(right_key_frame) else None,
            "projected_left_join_rows": int(len(merged)),
            "row_expansion_factor": round(len(merged) / len(left), 6) if len(left) else None,
            "confirmed_by_user": bool(request.get("confirmed_by_user", False)),
            "merged": False,
        }
        assessments.append(assessment)
        if assessment["row_expansion_factor"] and assessment["row_expansion_factor"] > 1:
            issues.append(_issue("join_row_expansion", "NEEDS_CONFIRMATION", "候选连接会造成行数膨胀", evidence=assessment))
        if request.get("critical", False) and not assessment["confirmed_by_user"]:
            issues.append(_issue("join_confirmation_required", "NEEDS_CONFIRMATION", "关键连接方式必须由用户确认", evidence=assessment))
    return assessments, issues


def _semantic_issue(message: str, evidence: Any = None) -> dict:
    return _issue("semantic_confirmation_required", "NEEDS_CONFIRMATION", message, evidence=evidence)


def _apply_user_resolutions(issues: list[dict], resolutions: list[dict]) -> None:
    """只允许用户关闭待确认项；客观 BLOCKER 必须靠修正数据或配置消除。"""
    for resolution in resolutions:
        code = resolution.get("code")
        explanation = resolution.get("explanation")
        if resolution.get("resolved_by") != "user" or not code or not explanation:
            issues.append(_issue(
                "invalid_issue_resolution", "BLOCKER",
                "问题解决记录必须包含 code、explanation 且 resolved_by=user",
                evidence=resolution,
            ))
            continue
        matched = False
        for issue in issues:
            if issue.get("code") == code and issue.get("severity") == "NEEDS_CONFIRMATION":
                issue["resolution"] = {
                    "resolved_by": "user",
                    "resolved_at": resolution.get("resolved_at"),
                    "explanation": explanation,
                }
                matched = True
        if not matched:
            issues.append(_issue(
                "invalid_issue_resolution", "BLOCKER",
                f"找不到可由用户关闭的 NEEDS_CONFIRMATION: {code}",
                evidence=resolution,
            ))


def _check_declared_constraints(frame: pd.DataFrame, column: str, constraints: dict) -> list[dict]:
    """对已声明的语义约束执行全量硬校验，不猜测未声明的规则。"""
    issues: list[dict] = []
    series = frame[column]
    if constraints.get("required_non_missing") and series.isna().any():
        issues.append(_issue(
            "required_value_missing", "BLOCKER", f"{column} 违反非空约束",
            evidence={"missing_count": int(series.isna().sum())},
        ))
    if "allowed_values" in constraints:
        allowed = constraints["allowed_values"]
        if not isinstance(allowed, list) or not allowed:
            issues.append(_issue("invalid_constraint", "BLOCKER", f"{column} 的 allowed_values 必须为非空数组"))
        else:
            invalid = series.dropna()[~series.dropna().isin(allowed)]
            if len(invalid):
                issues.append(_issue(
                    "allowed_values_violation", "BLOCKER", f"{column} 含约束范围外取值",
                    evidence={"count": int(len(invalid)), "samples": [_json_value(v) for v in invalid.drop_duplicates().head(10)]},
                ))
    if "minimum" in constraints or "maximum" in constraints:
        numeric = pd.to_numeric(series.dropna(), errors="coerce")
        parse_failures = int(numeric.isna().sum())
        if parse_failures:
            issues.append(_issue(
                "numeric_constraint_parse_failure", "BLOCKER", f"{column} 无法完整执行数值边界校验",
                evidence={"unparseable_count": parse_failures},
            ))
        else:
            if "minimum" in constraints:
                violations = numeric[numeric < constraints["minimum"]]
                if len(violations):
                    issues.append(_issue(
                        "minimum_violation", "BLOCKER", f"{column} 存在低于下限的取值",
                        evidence={"count": int(len(violations)), "observed_min": _json_value(numeric.min()), "minimum": constraints["minimum"]},
                    ))
            if "maximum" in constraints:
                violations = numeric[numeric > constraints["maximum"]]
                if len(violations):
                    issues.append(_issue(
                        "maximum_violation", "BLOCKER", f"{column} 存在高于上限的取值",
                        evidence={"count": int(len(violations)), "observed_max": _json_value(numeric.max()), "maximum": constraints["maximum"]},
                    ))
    return issues


def finalize_profile(profile: dict, semantics: dict) -> dict:
    if profile.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("只接受 schema_version=2 的 variable_map.json")
    result = copy.deepcopy(profile)
    result["issues"] = [i for i in result.get("issues", []) if i.get("code") != "semantic_confirmation_required"]

    requested_primary = semantics.get("primary_table")
    if requested_primary:
        if _find_table(result, requested_primary):
            result["primary_table"] = requested_primary
        else:
            result["issues"].append(_issue("invalid_primary_table", "BLOCKER", "语义文件指定的主分析表不存在"))

    observation = semantics.get("observation_unit") or {}
    if observation:
        result["observation_unit"] = observation
    if result["observation_unit"].get("status") != "confirmed" or result["observation_unit"].get("source") not in ALLOWED_SOURCES:
        result["issues"].append(_semantic_issue("观测单位必须由框架、数据字典或用户确认"))

    table = _find_primary(result)
    if table is None:
        result["status"] = overall_status(result["issues"])
        return result
    by_name = {v["column"]: v for v in table["variables"]}
    frame = _load_profiled_table(table)
    for item in semantics.get("variables", []):
        column = item.get("column")
        if column not in by_name:
            result["issues"].append(_issue("unknown_semantic_column", "BLOCKER", f"语义标注引用未知列: {column}"))
            continue
        roles = item.get("roles", [])
        invalid = sorted(set(roles) - ALLOWED_ROLES)
        if invalid:
            result["issues"].append(_issue("invalid_role", "BLOCKER", f"{column} 含非法角色", evidence=invalid))
            continue
        semantic_type = item.get("semantic_type", "unknown")
        if semantic_type not in ALLOWED_SEMANTIC_TYPES:
            result["issues"].append(_issue("invalid_semantic_type", "BLOCKER", f"{column} 的 semantic_type 非法"))
            continue
        if item.get("source") is not None and item.get("source") not in ALLOWED_SOURCES:
            result["issues"].append(_issue("invalid_semantic_source", "BLOCKER", f"{column} 的语义来源非法"))
            continue
        if item.get("confidence") is not None and item.get("confidence") not in ALLOWED_CONFIDENCE:
            result["issues"].append(_issue("invalid_confidence", "BLOCKER", f"{column} 的 confidence 非法"))
            continue
        mapping = {
            "semantic_type": semantic_type,
            "unit": item.get("unit"),
            "roles": roles,
            "status": item.get("status", "candidate"),
            "source": item.get("source"),
            "confidence": item.get("confidence"),
            "evidence": item.get("evidence", []),
            "constraints": item.get("constraints", {}),
        }
        by_name[column]["semantic_mapping"] = mapping
        result["issues"].extend(_check_declared_constraints(frame, column, mapping["constraints"]))
        if set(roles) & CRITICAL_ROLES:
            if mapping["status"] != "confirmed" or mapping["source"] not in ALLOWED_SOURCES:
                result["issues"].append(_semantic_issue(f"关键变量 {column} 的角色必须确认", roles))

    join_assessments, join_issues = assess_joins(result, semantics.get("join_requests", []))
    result["join_assessments"] = join_assessments
    result["issues"].extend(join_issues)
    result["structure_assessment"] = semantics.get("structure_assessment", result.get("structure_assessment", {}))
    confirmed_roles = {
        role for v in table["variables"]
        if v["semantic_mapping"].get("status") == "confirmed"
        for role in v["semantic_mapping"].get("roles", [])
    }
    result["method_capabilities"] = {
        "panel_structure": {"supported": {"entity_id", "time"} <= confirmed_roles,
                            "required_roles": ["entity_id", "time"]},
        "policy_evaluation": {"supported": {"treatment", "time"} <= confirmed_roles,
                              "required_roles": ["treatment", "time"]},
        "instrumental_variables": {"supported": "instrument" in confirmed_roles,
                                   "required_roles": ["instrument"]},
        "regression_discontinuity": {"supported": "running_variable" in confirmed_roles,
                                     "required_roles": ["running_variable"]},
        "efficiency_analysis": {"supported": {"input", "output"} <= confirmed_roles,
                                "required_roles": ["input", "output"]},
    }
    _apply_user_resolutions(result["issues"], semantics.get("resolutions", []))
    result["status"] = overall_status(result["issues"])
    return result


def render_report(result: dict) -> str:
    lines = ["# 数据审计报告（Schema V2）", "", f"- 状态：**{result.get('status', 'BLOCKER')}**",
             "- 扫描方式：全量确定性扫描", "- 原始数据：只读，未修改", ""]
    lines.extend(["## 数据表", "", "| 文件 | Sheet | 行数 | 列数 | 完全重复行 |", "|---|---|---:|---:|---:|"])
    for table in result.get("tables", []):
        lines.append(f"| {table['source_path']} | {table.get('sheet') or '—'} | {table['row_count']} | {table['column_count']} | {table['duplicate_row_count']} |")
    lines.extend(["", "## 主分析表与观测单位", "", f"- 主分析表：`{result.get('primary_table') or '未确认'}`",
                  f"- 观测单位：{result.get('observation_unit', {}).get('label') or '未确认'}", ""])
    primary = _find_primary(result)
    if primary:
        lines.extend(["## 变量画像与语义映射", "", "| 列 | 存储类型 | 缺失 | 唯一值 | 语义类型 | 角色 | 状态 |", "|---|---|---:|---:|---|---|---|"])
        for var in primary["variables"]:
            obs, sem = var["observed_pattern"], var["semantic_mapping"]
            lines.append(f"| {var['column']} | {var['storage_type']} | {obs['missing_count']} | {obs['unique_count']} | {sem.get('semantic_type') or '—'} | {', '.join(sem.get('roles', [])) or '—'} | {sem.get('status', 'unmapped')} |")
        lines.append("")
    lines.extend(["## 数据质量与待确认事项", ""])
    if result.get("issues"):
        for item in result["issues"]:
            resolved = "（已解决）" if item.get("resolution") else ""
            evidence = f"；证据：`{json.dumps(item['evidence'], ensure_ascii=False)}`" if "evidence" in item else ""
            lines.append(f"- **{item['severity']}** `{item['code']}`：{item['message']}{resolved}{evidence}")
    else:
        lines.append("- 无")
    lines.extend(["", "## 方法条件（不作模型推荐）", ""])
    for name, capability in result.get("method_capabilities", {}).items():
        lines.append(f"- {name}：{'具备已确认字段条件' if capability.get('supported') else '字段条件不完整'}")
    lines.extend(["", "> 具体候选模型、推荐模型和解释边界由 Stage 2 决定。", ""])
    return "\n".join(lines)


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(result: dict, output: str, report: str) -> None:
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path = Path(report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(result), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="结构化表格数据确定性审计")
    sub = parser.add_subparsers(dest="command", required=True)
    profile = sub.add_parser("profile", help="全量扫描并生成事实骨架")
    profile.add_argument("--data", action="append", required=True, help="CSV/XLSX 文件，可重复")
    profile.add_argument("--primary", help="主表：文件路径或 文件路径::Sheet")
    profile.add_argument("--output", required=True, help="variable_map.json")
    profile.add_argument("--report", required=True, help="data_audit.md")
    finalize = sub.add_parser("finalize", help="受限合并语义标注并校验")
    finalize.add_argument("--variable-map", required=True)
    finalize.add_argument("--semantics", required=True)
    finalize.add_argument("--output", required=True)
    finalize.add_argument("--report", required=True)
    validate = sub.add_parser("validate", help="校验 V2 合约状态")
    validate.add_argument("--variable-map", required=True)
    args = parser.parse_args()

    try:
        if args.command == "profile":
            result = build_profile(args.data, args.primary)
            _write(result, args.output, args.report)
        elif args.command == "finalize":
            result = finalize_profile(_load(args.variable_map), _load(args.semantics))
            _write(result, args.output, args.report)
        else:
            result = _load(args.variable_map)
            if result.get("schema_version") != SCHEMA_VERSION:
                raise ValueError("variable_map.json 必须为 schema_version=2")
            print(json.dumps({"schema_version": 2, "status": result.get("status")}, ensure_ascii=False))
            sys.exit(0 if result.get("status") in {"PASS", "WARN"} else 2)
        print(json.dumps({"schema_version": 2, "status": result["status"]}, ensure_ascii=False))
        sys.exit(0 if result["status"] in {"PASS", "WARN"} else 2)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
