#!/usr/bin/env python3
"""
check_word_count.py -- 统计论文正文字数，输出 JSON 报告

用法：
    python scripts/check_word_count.py \
      --paper <workspace>/04_writer/output/paper_draft.md \
      --target 8000 \
      --output <workspace>/04_writer/output/word_count_report.json

输出 JSON：
{
  "actual_words": 6420,
  "target_words": 8000,
  "short_by": 1580,
  "status": "SHORT",
  "needs_user_decision": true
}

status 取值：
  - OK        : actual >= target
  - SHORT     : actual < target

exit code:
  0 : OK 或 SHORT（都正常，只是状态不同）
  2 : 参数错误
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from utils import count_chinese_words

logger = logging.getLogger(__name__)


def count_words_file(paper_path: str) -> int:
    """读取文件并统计字数。"""
    p = Path(paper_path)
    if not p.exists():
        raise FileNotFoundError(f"论文文件不存在: {paper_path}")

    text = p.read_text(encoding="utf-8")
    return count_chinese_words(text)


def main():
    parser = argparse.ArgumentParser(description="统计论文正文字数")
    parser.add_argument("--paper", required=True, help="论文文件路径 (.md 或 .tex)")
    parser.add_argument("--target", type=int, default=8000, help="目标字数 (默认 8000)")
    parser.add_argument("--output", required=True, help="JSON 报告输出路径")
    args = parser.parse_args()

    try:
        actual = count_words_file(args.paper)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(2)

    short_by = max(0, args.target - actual)
    status = "OK" if actual >= args.target else "SHORT"

    report = {
        "actual_words": actual,
        "target_words": args.target,
        "short_by": short_by,
        "status": status,
        "needs_user_decision": status == "SHORT",
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
