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


# ---------------------------------------------------------------------------
# 3. 图表标题检测（来自 gen_docx.py:836-851）
# ---------------------------------------------------------------------------

_CAPTION_NUM_PATTERN = re.compile(r'^[表图]\s*\d+\s+.+')
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
