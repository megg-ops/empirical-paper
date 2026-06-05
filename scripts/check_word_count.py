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
import re
import sys
from pathlib import Path


def count_chinese_words(text: str) -> int:
    """统计中文字数。

    规则：
    - 每个中文字符算 1 字
    - 连续英文/数字串按 1 个单词计（空格分隔）
    - 标点符号不单独计数（附着在相邻字符上）
    """
    # 去掉 markdown 标记
    cleaned = text

    # 去掉公式 $...$ 和 $$...$$
    cleaned = re.sub(r'\$\$.*?\$\$', '', cleaned, flags=re.DOTALL)
    cleaned = re.sub(r'\$[^$]+\$', '', cleaned)

    # 去掉 markdown 图片引用 ![...](...)
    cleaned = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', cleaned)

    # 去掉 markdown 链接 [...](...) 但保留显示文字
    cleaned = re.sub(r'\[([^\]]*)\]\([^)]+\)', r'\1', cleaned)

    # 去掉 markdown 表格行（以 | 开头的行）
    cleaned = re.sub(r'^\|.*\|$', '', cleaned, flags=re.MULTILINE)

    # 去掉 markdown 分隔行（如 |---|---|）
    cleaned = re.sub(r'^[\s|:-]+$', '', cleaned, flags=re.MULTILINE)

    # 去掉 markdown 标题标记 # ## ### 等
    cleaned = re.sub(r'^#{1,6}\s+', '', cleaned, flags=re.MULTILINE)

    # 去掉 markdown 加粗/斜体标记
    cleaned = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', cleaned)
    cleaned = re.sub(r'_{1,3}([^_]+)_{1,3}', r'\1', cleaned)

    # 去掉参考文献部分（从"参考文献"或"References"开始到结尾）
    ref_pattern = re.compile(
        r'^[#\s]*(参考文献|References|REFERENCES)\s*$',
        re.MULTILINE | re.IGNORECASE,
    )
    ref_match = ref_pattern.search(cleaned)
    if ref_match:
        cleaned = cleaned[:ref_match.start()]

    # 统计
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', cleaned)
    chinese_count = len(chinese_chars)

    # 英文/数字单词（空格分隔的连续非中文非标点串）
    # 先去掉中文和中文标点，再按空格分隔
    no_chinese = re.sub(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]', ' ', cleaned)
    english_words = [w for w in no_chinese.split() if re.search(r'[a-zA-Z0-9]', w)]
    english_count = len(english_words)

    return chinese_count + english_count


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
        print(f"ERROR: {e}", file=sys.stderr)
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
