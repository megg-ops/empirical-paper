#!/usr/bin/env python3
"""聚合结构化质量结果，生成最终门禁结论。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from quality_contract import make_quality_result, read_quality_result, write_json


def _method_fit_check(path: Path) -> dict:
    if not path.exists():
        return {"status": "INCOMPLETE", "issues": [f"必要文件缺失: {path}"]}
    text = path.read_text(encoding="utf-8", errors="ignore")
    import re
    match = re.search(r"Stage\s*2\s*判定.*?\b(PASS|WARN|BLOCKER)\b", text, re.IGNORECASE | re.DOTALL)
    if not match:
        return {"status": "INCOMPLETE", "issues": ["method_fit_check.md 缺少明确 Stage 2 判定"]}
    verdict = match.group(1).upper()
    return {"status": verdict, "issues": []}


def _results_check(path: Path) -> dict:
    if not path.exists():
        return {"status": "INCOMPLETE", "issues": [f"必要文件缺失: {path}"]}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "BLOCKER", "issues": [f"results.json 无法解析: {exc}"]}
    values = data.get("reportable_values")
    if not isinstance(values, list) or not values:
        return {"status": "BLOCKER", "issues": ["results.json.reportable_values 为空"]}
    return {"status": "PASS", "issues": []}


def _source_check(path: Path, label: str) -> dict:
    if not path.exists():
        return {"status": "INCOMPLETE", "issues": [f"必要门禁 JSON 缺失: {path}"], "source": str(path)}
    try:
        result = read_quality_result(str(path))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {"status": "BLOCKER", "issues": [f"{label} JSON 无效: {exc}"], "source": str(path)}
    status = {"PASS": "PASS", "PASS_WITH_MINOR": "WARN", "WARN": "WARN",
              "FAIL": "BLOCKER", "INCOMPLETE": "INCOMPLETE"}[result["verdict"]]
    issues = []
    for name, check in result.get("checks", {}).items():
        if check.get("status") in {"WARN", "BLOCKER", "INCOMPLETE"}:
            issues.extend(f"{name}: {item}" for item in check.get("issues", []))
    return {"status": status, "issues": issues, "source": str(path), "source_verdict": result["verdict"]}


def _word_count_check(ws: Path) -> dict:
    report_path = ws / "04_writer" / "output" / "word_count_report.json"
    if not report_path.exists():
        return {"status": "INCOMPLETE", "issues": [f"必要文件缺失: {report_path}"]}
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "BLOCKER", "issues": [f"word_count_report.json 无法解析: {exc}"]}
    if report.get("schema_version") != 2 or report.get("status") not in {"OK", "SHORT", "OVER"}:
        return {"status": "BLOCKER", "issues": ["word_count_report.json 不是有效的 schema v2 报告"]}
    if report["status"] == "SHORT":
        decision_path = report_path.with_name("user_wordcount_decision.json")
        try:
            decision = json.loads(decision_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {"status": "BLOCKER", "issues": [f"字数不足且缺少有效用户决策: {exc}"]}
        if decision.get("decision") != "accept_short" or decision.get("confirmed_by_user") is not True:
            return {"status": "BLOCKER", "issues": ["字数不足决策必须是用户确认的 accept_short"]}
        return {"status": "WARN", "issues": ["字数不足，用户已明确接受"], "source": str(report_path)}
    return {
        "status": "WARN" if report["status"] == "OVER" else "PASS",
        "issues": ["字数高于已确认范围"] if report["status"] == "OVER" else [],
        "source": str(report_path),
    }


def _final_file_check(ws: Path, output_format: str) -> dict:
    suffix = "docx" if output_format == "docx" else "tex"
    path = ws / "final_paper" / f"paper_final.{suffix}"
    return {
        "status": "PASS" if path.exists() else "INCOMPLETE",
        "issues": [] if path.exists() else [f"最终论文不存在: {path}"],
        "source": str(path),
    }


def run_gate(workspace: str, output_format: str) -> dict:
    ws = Path(workspace)
    final = ws / "final_paper"
    checks = {
        "method_fit": _method_fit_check(ws / "02_modeler" / "output" / "method_fit_check.md"),
        "structured_results": _results_check(ws / "03_coder" / "output" / "results.json"),
        "word_count": _word_count_check(ws),
        "final_file": _final_file_check(ws, output_format),
        "markdown_consistency": _source_check(final / "markdown_consistency_report.json", "Markdown consistency"),
    }
    if output_format == "docx":
        checks["docx_validation"] = _source_check(final / "docx_validation_report.json", "DOCX validation")
        checks["docx_consistency"] = _source_check(final / "docx_consistency_report.json", "DOCX consistency")
    return make_quality_result("final_quality_gate", checks, metadata={"workspace": str(ws), "output_format": output_format})


def format_report(result: dict) -> str:
    lines = ["# Final Quality Gate Report", "", "## Final Verdict", "", result["verdict"], "",
             "## Source Checks", "", "| Check | Status | Source |", "|---|---|---|"]
    for name, check in result["checks"].items():
        lines.append(f"| {name} | {check['status']} | {check.get('source', 'direct structured check')} |")
    lines.extend(["", "## Findings", ""])
    findings = False
    for name, check in result["checks"].items():
        for issue in check.get("issues", []):
            findings = True
            lines.append(f"- **{check['status']}** `{name}`: {issue}")
    if not findings:
        lines.append("- 无")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="最终质量门禁脚本")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--output", required=True, help="Markdown 报告")
    parser.add_argument("--json-output", help="结构化最终门禁 JSON")
    parser.add_argument("--format", choices=["latex", "docx"], default="latex")
    parser.add_argument("--allow-warn", action="store_true", default=False)
    args = parser.parse_args()

    output_format = args.format
    manifest_path = Path(args.workspace) / "00_intake" / "output" / "manifest.json"
    if manifest_path.exists():
        try:
            output_format = json.loads(manifest_path.read_text(encoding="utf-8")).get("output_format", output_format)
        except (OSError, json.JSONDecodeError):
            pass
    result = run_gate(args.workspace, output_format)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(format_report(result), encoding="utf-8")
    json_output = args.json_output or str(output.with_suffix(".json"))
    write_json(result, json_output)
    print(format_report(result))
    print(f"\n报告已写入: {args.output}\n结构化结果已写入: {json_output}")
    if result["verdict"] in {"FAIL", "INCOMPLETE"}:
        sys.exit(2)
    if result["verdict"] == "WARN" and not args.allow_warn:
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
