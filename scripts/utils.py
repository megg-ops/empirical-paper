"""共享工具函数。

将 gen_docx.py、validate_docx.py、verify_consistency.py、check_word_count.py
中重复出现的函数集中到此处，消除 DRY 违规。

导出：
    count_md_formulas / count_md_formulas_from_file  — 公式计数
    count_chinese_words                               — 中文字数统计
    is_caption                                        — 图表标题检测
    extract_md_citation_numbers                       — 引用编号提取
"""

import re
from pathlib import Path


DEFAULT_WORD_COUNT_SCOPE = {
    "include_abstract": True,
    "include_title": False,
    "include_keywords": False,
    "include_references": False,
    "include_acknowledgements": False,
    "include_appendices": False,
    "include_table_cells": False,
    "include_table_captions": True,
    "include_figure_captions": True,
    "include_formulas": False,
    "include_code_blocks": False,
}


# ---------------------------------------------------------------------------
# 1. 公式计数（来自 gen_docx.py:455-470 / validate_docx.py:82-93）
# ---------------------------------------------------------------------------

def count_md_formulas(md_text: str) -> tuple[int, int]:
    """统计 Markdown 中的行内和独立公式数。

    先统计 $$...$$ 独立公式（避免被行内匹配干扰），再去掉独立公式后
    统计 $...$ 行内公式。Returns (inline_count, block_count)。
    """
    # 独立公式 $$...$$
    block_formulas = re.findall(r'\$\$.*?\$\$', md_text, re.DOTALL)
    block_count = len(block_formulas)

    # 去掉独立公式后统计行内
    text_no_block = re.sub(r'\$\$.*?\$\$', '', md_text, flags=re.DOTALL)
    inline_formulas = re.findall(
        r'(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)', text_no_block,
    )
    inline_count = len(inline_formulas)

    return inline_count, block_count


def count_md_formulas_from_file(markdown_path: str) -> tuple[int, int]:
    """File-path wrapper for count_md_formulas."""
    text = Path(markdown_path).read_text(encoding="utf-8")
    return count_md_formulas(text)


# ---------------------------------------------------------------------------
# 2. 中文字数统计（来自 check_word_count.py:36-89）
# ---------------------------------------------------------------------------

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


def extract_countable_text(text: str, scope: dict | None = None) -> str:
    """按统一论文口径提取可计数字符串（Markdown/LaTeX 轻量兼容）。"""
    rules = {**DEFAULT_WORD_COUNT_SCOPE, **(scope or {})}
    cleaned = text.replace("\r\n", "\n")
    if not rules["include_code_blocks"]:
        cleaned = re.sub(r"```.*?```", "", cleaned, flags=re.DOTALL)
    if not rules["include_formulas"]:
        cleaned = re.sub(r"\$\$.*?\$\$", "", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r"(?<!\$)\$(?!\$).*?(?<!\$)\$(?!\$)", "", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r"\\\[.*?\\\]", "", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r"\\\(.*?\\\)", "", cleaned, flags=re.DOTALL)

    stop_sections = []
    if not rules["include_references"]:
        stop_sections.extend(["参考文献", "References"])
    if not rules["include_acknowledgements"]:
        stop_sections.extend(["致谢", "Acknowledgements", "Acknowledgments"])
    if not rules["include_appendices"]:
        stop_sections.extend(["附录", "Appendix"])
    if stop_sections:
        marker = re.compile(
            r"^(?:#{1,6}\s*|\\(?:section|section\*)\{)?(?:" + "|".join(map(re.escape, stop_sections)) + r")(?:\}|\s*)$",
            re.MULTILINE | re.IGNORECASE,
        )
        match = marker.search(cleaned)
        if match:
            cleaned = cleaned[:match.start()]

    if not rules["include_abstract"]:
        abstract = re.compile(
            r"^(?:#{1,6}\s*|\\(?:section|section\*)\{)?(?:摘要|Abstract)(?:\}|\s*)$.*?(?=^(?:#{1,6}\s+|\\(?:section|section\*)\{)|\Z)",
            re.MULTILINE | re.IGNORECASE | re.DOTALL,
        )
        cleaned = abstract.sub("", cleaned)

    cleaned = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", cleaned)
    cleaned = re.sub(r"\[FIGURE:\s*[^\]]+\]|\[TABLE:\s*[^\]]+\]", "", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    lines = []
    for line in cleaned.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            if rules["include_table_cells"]:
                lines.append(stripped)
            continue
        if re.match(r"^\s*\\(?:begin|end|usepackage|documentclass|input|includegraphics)", stripped):
            continue
        is_heading = bool(re.match(r"^#{1,6}\s+", stripped) or re.match(r"^\\(?:section|subsection|subsubsection)\*?\{", stripped))
        if is_heading and not rules["include_title"]:
            continue
        if not rules["include_keywords"] and re.match(r"^(关键词|Keywords?)\s*[：:]", stripped, re.IGNORECASE):
            continue
        if re.match(r"^(表|Table)\s*\d+", stripped, re.IGNORECASE) and not rules["include_table_captions"]:
            continue
        if re.match(r"^(图|Figure|Fig\.)\s*\d+", stripped, re.IGNORECASE) and not rules["include_figure_captions"]:
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", "", cleaned)
    cleaned = re.sub(r"[{}#*_`>]", "", cleaned)
    return cleaned


def count_paper_words(text: str, scope: dict | None = None) -> dict:
    """统一统计中文字符、英文单词和数字 token。"""
    cleaned = extract_countable_text(text, scope)
    chinese = re.findall(r"[\u4e00-\u9fff]", cleaned)
    english = re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)*", cleaned)
    digits = re.findall(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?%?", cleaned)
    return {
        "total": len(chinese) + len(english) + len(digits),
        "chinese": len(chinese),
        "english": len(english),
        "digits": len(digits),
    }


def validate_word_count_requirement(requirement: dict) -> dict:
    """校验并规范 Stage 0 已确认的字数要求。"""
    mode = requirement.get("mode")
    if mode not in {"exact", "minimum", "range"}:
        raise ValueError("word_count.mode 必须为 exact/minimum/range")
    if requirement.get("confirmed_by_user") is not True:
        raise ValueError("字数要求必须由用户确认")
    normalized = {
        "mode": mode,
        "target": requirement.get("target"),
        "minimum": requirement.get("minimum"),
        "maximum": requirement.get("maximum"),
        "source": requirement.get("source"),
        "confirmed_by_user": True,
        "scope": {**DEFAULT_WORD_COUNT_SCOPE, **requirement.get("scope", {})},
    }
    if mode == "exact" and (not isinstance(normalized["target"], int) or normalized["target"] <= 0):
        raise ValueError("exact 模式必须提供正整数 target")
    if mode == "minimum" and (not isinstance(normalized["minimum"], int) or normalized["minimum"] <= 0):
        raise ValueError("minimum 模式必须提供正整数 minimum")
    if mode == "range":
        if not isinstance(normalized["minimum"], int) or not isinstance(normalized["maximum"], int):
            raise ValueError("range 模式必须提供 minimum 和 maximum")
        if normalized["minimum"] <= 0 or normalized["maximum"] < normalized["minimum"]:
            raise ValueError("range 字数上下限无效")
    return normalized


def evaluate_word_count(actual: int, requirement: dict) -> dict:
    """根据已确认要求返回 OK/SHORT/OVER。"""
    req = validate_word_count_requirement(requirement)
    mode = req["mode"]
    if mode == "exact":
        status = "OK" if actual >= req["target"] else "SHORT"
        lower, upper = req["target"], None
    elif mode == "minimum":
        status = "OK" if actual >= req["minimum"] else "SHORT"
        lower, upper = req["minimum"], None
    else:
        lower, upper = req["minimum"], req["maximum"]
        status = "SHORT" if actual < lower else "OVER" if actual > upper else "OK"
    return {
        "status": status,
        "minimum_required": lower,
        "maximum_allowed": upper,
        "short_by": max(0, lower - actual),
        "over_by": max(0, actual - upper) if upper is not None else 0,
        "needs_user_decision": status == "SHORT",
    }


# ---------------------------------------------------------------------------
# 3. 图表标题检测（来自 gen_docx.py:836-851）
# ---------------------------------------------------------------------------

_CAPTION_NUM_PATTERN = re.compile(r'^[表图]\s*(\d+)\s+.+')
_CAPTION_REF_VERB_PATTERN = re.compile(
    r'^[表图]\s*\d+\s*'
    r'(报告|展示|说明|指出|呈现|反映|列出|给出|揭示了?|显示了?|直观展示了?)',
)


def is_caption(text: str) -> bool:
    """判断段落是否为图表标题。

    只匹配「表/图 + 编号 + 空格 + 标题文字」的真正标题，
    不匹配「表1报告了……」「图1展示了……」等正文引用。
    """
    t = text.strip()
    if not _CAPTION_NUM_PATTERN.match(t):
        return False
    # 排除正文引用模式
    if _CAPTION_REF_VERB_PATTERN.match(t):
        return False
    return True


# ---------------------------------------------------------------------------
# 4. 引用编号提取（来自 verify_consistency.py:621-628）
# ---------------------------------------------------------------------------

def extract_md_citation_numbers(md_text: str) -> list[int]:
    """提取 Markdown 中的引用编号 [1], [2], [3-5] 等。"""
    singles = re.findall(r'\[(\d+)\]', md_text)
    ranges = re.findall(r'\[(\d+)\s*[-–—]\s*(\d+)\]', md_text)
    numbers = [int(n) for n in singles]
    for start, end in ranges:
        numbers.extend(range(int(start), int(end) + 1))
    return sorted(set(numbers))
