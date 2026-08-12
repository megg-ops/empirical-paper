#!/usr/bin/env python3
"""按 Stage 0 已确认的 manifest 规则统计论文正文并输出 JSON。

用法：
    python scripts/check_word_count.py \
      --paper <workspace>/04_writer/output/paper_draft.md \
      --manifest <workspace>/00_intake/output/manifest.json \
      --output <workspace>/04_writer/output/word_count_report.json

脚本不提供隐式默认字数；exact/minimum/range 及统计范围均来自 manifest。
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from utils import count_paper_words, evaluate_word_count, validate_word_count_requirement

logger = logging.getLogger(__name__)


def count_words_file(paper_path: str, scope: dict | None = None) -> dict:
    """读取文件并统计字数。"""
    p = Path(paper_path)
    if not p.exists():
        raise FileNotFoundError(f"论文文件不存在: {paper_path}")

    text = p.read_text(encoding="utf-8")
    return count_paper_words(text, scope)


def load_requirement(manifest_path: str) -> dict:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    try:
        requirement = manifest["paper_requirements"]["word_count"]
    except (KeyError, TypeError) as exc:
        raise ValueError("manifest 缺少 paper_requirements.word_count") from exc
    return validate_word_count_requirement(requirement)


def main():
    parser = argparse.ArgumentParser(description="统计论文正文字数")
    parser.add_argument("--paper", required=True, help="论文文件路径 (.md 或 .tex)")
    parser.add_argument("--manifest", required=True, help="包含已确认字数要求的 manifest.json")
    parser.add_argument("--output", required=True, help="JSON 报告输出路径")
    args = parser.parse_args()

    try:
        requirement = load_requirement(args.manifest)
        counts = count_words_file(args.paper, requirement["scope"])
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        logger.error(str(e))
        sys.exit(2)

    evaluation = evaluate_word_count(counts["total"], requirement)
    report = {"schema_version": 2, "actual_words": counts["total"], "counts": counts,
              "requirement": requirement, **evaluation}

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
