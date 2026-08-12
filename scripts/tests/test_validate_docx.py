from docx import Document

from utils import _CAPTION_NUM_PATTERN
from validate_docx import check_figure_table_integrity, count_docx_formulas


def test_caption_pattern_exposes_number_group():
    match = _CAPTION_NUM_PATTERN.match("表 12 描述性统计")
    assert match and match.group(1) == "12"


def test_figure_table_integrity_does_not_crash_on_caption(tmp_path):
    doc = Document()
    doc.add_paragraph("表1 描述性统计")
    doc.add_paragraph("图1 分布图")
    path = tmp_path / "paper.docx"
    doc.save(path)
    result = check_figure_table_integrity(str(path), None, None, None)
    assert result["table_nums"] == [1]
    assert result["figure_nums"] == [1]


def test_minimal_docx_has_no_formulas(tmp_path):
    doc = Document()
    doc.add_paragraph("正文")
    path = tmp_path / "paper.docx"
    doc.save(path)
    assert count_docx_formulas(str(path)) == (0, 0)
