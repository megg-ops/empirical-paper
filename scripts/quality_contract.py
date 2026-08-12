"""质量门禁的结构化结果合约。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


CHECK_STATUSES = {"PASS", "WARN", "BLOCKER", "INCOMPLETE"}


def normalize_status(value: str) -> str:
    mapping = {
        "pass": "PASS", "ok": "PASS", "warn": "WARN", "warning": "WARN",
        "block": "BLOCKER", "blocker": "BLOCKER", "fail": "BLOCKER",
        "error": "BLOCKER", "incomplete": "INCOMPLETE",
    }
    status = mapping.get(str(value).lower(), str(value).upper())
    if status not in CHECK_STATUSES:
        raise ValueError(f"非法质量状态: {value}")
    return status


def verdict_from_checks(checks: dict) -> str:
    statuses = [normalize_status(v.get("status", "PASS")) for v in checks.values()]
    if "BLOCKER" in statuses:
        return "FAIL"
    if "INCOMPLETE" in statuses:
        return "INCOMPLETE"
    if "WARN" in statuses:
        return "WARN"
    return "PASS"


def make_quality_result(tool: str, checks: dict, *, metadata: dict | None = None) -> dict:
    normalized = {}
    for key, value in checks.items():
        item = dict(value)
        item["status"] = normalize_status(item.get("status", "PASS"))
        item.setdefault("issues", [])
        normalized[key] = item
    return {
        "schema_version": 1,
        "kind": "quality_gate_result",
        "tool": tool,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "verdict": verdict_from_checks(normalized),
        "checks": normalized,
        "metadata": metadata or {},
    }


def write_json(result: dict, output: str) -> None:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def read_quality_result(path: str) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or data.get("kind") != "quality_gate_result":
        raise ValueError(f"不是有效的质量门禁 JSON: {path}")
    if data.get("verdict") not in {"PASS", "PASS_WITH_MINOR", "WARN", "FAIL", "INCOMPLETE"}:
        raise ValueError(f"质量门禁 verdict 非法: {path}")
    return data
