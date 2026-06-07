"""tests/test_utils.py -- utils.py 单元测试"""

import pytest
from utils import (
    count_md_formulas,
    count_md_formulas_from_file,
    count_chinese_words,
    is_caption,
    extract_md_citation_numbers,
)


# ---- count_md_formulas ----

class TestCountMdFormulas:
    def test_no_formulas(self):
        assert count_md_formulas("hello world") == (0, 0)

    def test_inline_only(self):
        text = "公式 $E=mc^2$ 和 $a+b$"
        assert count_md_formulas(text) == (2, 0)

    def test_block_only(self):
        text = "行内\n$$\nx^2 + y^2 = z^2\n$$\n结尾"
        assert count_md_formulas(text) == (0, 1)

    def test_mixed(self):
        text = "行内 $a$ 然后 $$\nblock\n$$ 和 $b$"
        inline, block = count_md_formulas(text)
        assert block == 1
        assert inline == 2

    def test_block_not_counted_as_inline(self):
        text = "$$\nblock formula\n$$"
        assert count_md_formulas(text) == (0, 1)

    def test_from_file(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text("公式 $x$ 和 $$y$$", encoding="utf-8")
        inline, block = count_md_formulas_from_file(str(md))
        assert inline == 1
        assert block == 1


# ---- count_chinese_words ----

class TestCountChineseWords:
    def test_pure_chinese(self):
        assert count_chinese_words("这是中文测试") == 6

    def test_mixed(self):
        result = count_chinese_words("这是test测试")
        assert result >= 5  # 4 中文字 + 1 英文词

    def test_empty(self):
        assert count_chinese_words("") == 0

    def test_removes_formulas(self):
        text = "正文$公式$结束"
        result = count_chinese_words(text)
        assert result == 4  # "正文" + "结束"

    def test_removes_references(self):
        text = "正文内容\n# 参考文献\n[1] Author. Title."
        result = count_chinese_words(text)
        assert result == 4  # 只有"正文内容"

    def test_removes_images(self):
        text = "正文![图片](path.png)结束"
        result = count_chinese_words(text)
        assert result == 4  # "正文" + "结束"


# ---- is_caption ----

class TestIsCaption:
    def test_table_caption(self):
        assert is_caption("表1 回归分析结果") is True

    def test_figure_caption(self):
        assert is_caption("图2 散点图") is True

    def test_caption_with_spaces(self):
        assert is_caption("表 3  描述性统计") is True

    def test_ref_verb_excluded(self):
        assert is_caption("表1报告了回归分析结果") is False

    def test_ref_verb_figure(self):
        assert is_caption("图2展示了数据分布") is False

    def test_plain_text(self):
        assert is_caption("这是一段普通文字") is False

    def test_no_number(self):
        assert is_caption("表 回归分析") is False


# ---- extract_md_citation_numbers ----

class TestExtractMdCitationNumbers:
    def test_single_citations(self):
        assert extract_md_citation_numbers("如[1]所示，[3]也验证了") == [1, 3]

    def test_range_citation(self):
        assert extract_md_citation_numbers("多项研究[2-5]表明") == [2, 3, 4, 5]

    def test_mixed(self):
        assert extract_md_citation_numbers("[1]和[3-5]以及[7]") == [1, 3, 4, 5, 7]

    def test_no_citations(self):
        assert extract_md_citation_numbers("无引用文本") == []

    def test_dedup_and_sort(self):
        assert extract_md_citation_numbers("[3][1][3][2]") == [1, 2, 3]
