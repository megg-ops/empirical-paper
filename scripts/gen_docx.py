#!/usr/bin/env python3
"""
gen_docx.py -- Markdown draft (with LaTeX math) -> formatted Word document

Pipeline:
    paper_draft.md -> pandoc -> raw.docx -> python-docx post-processing -> paper_final.docx

Usage:
    python gen_docx.py \
        --manifest paper_workspace/00_intake/output/manifest.json \
        --markdown paper_workspace/04_writer/output/paper_draft.md \
        --output paper_workspace/final_paper/paper_final.docx \
        --reference-doc template.docx \
        --tables paper_workspace/03_coder/output/tables \
        --figures paper_workspace/03_coder/output/figures \
        --log paper_workspace/final_paper/docx_build_log.md
"""

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt

logger = logging.getLogger("gen_docx")


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# load_manifest / load_template_rules
# ---------------------------------------------------------------------------

def load_manifest(path: str) -> dict:
    """Load manifest.json; returns empty dict on failure."""
    p = Path(path)
    if not p.exists():
        logger.warning("manifest not found: %s", path)
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("manifest parse error: %s", exc)
        return {}


def load_template_rules(path: str | None, manifest: dict = None) -> dict:
    """Load template_rules.json; returns empty dict on failure.

    Resolution order:
    1. Explicit --template-rules path
    2. manifest["template_rules_file"]
    """
    if not path and manifest:
        path = manifest.get("template_rules_file")
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        logger.warning("template_rules not found: %s", path)
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        logger.info("template_rules loaded: %s (priority: %s)", path, data.get("priority", "unknown"))
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("template_rules parse error: %s", exc)
        return {}


def load_assets_manifest(path: str | None, manifest: dict = None) -> dict:
    """Load assets_manifest.json; returns empty dict on failure.

    Resolution order:
    1. Explicit --assets-manifest path
    2. manifest["assets_manifest_file"]
    """
    if not path and manifest:
        path = manifest.get("assets_manifest_file")
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        logger.warning("assets_manifest not found: %s", path)
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        fig_count = len(data.get("figures", []))
        tbl_count = len(data.get("tables", []))
        logger.info("assets_manifest loaded: %s (%d figures, %d tables)", path, fig_count, tbl_count)
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("assets_manifest parse error: %s", exc)
        return {}


# ---------------------------------------------------------------------------
# Placeholder replacement: [FIGURE: xxx] / [TABLE: xxx]
# ---------------------------------------------------------------------------

_FIGURE_PLACEHOLDER = re.compile(r"\[FIGURE:\s*(\w+)\]")
_TABLE_PLACEHOLDER = re.compile(r"\[TABLE:\s*(\w+)\]")


def render_table_asset_as_markdown(tbl_path: str) -> str:
    """将表格资产文件渲染为 Markdown 表格文本。

    支持 csv / xlsx / md 格式。不支持的格式抛出 ValueError。

    Returns:
        Markdown 表格字符串（含表头分隔行）。
    """
    p = Path(tbl_path)
    if not p.exists():
        raise FileNotFoundError(f"表格资产文件不存在: {tbl_path}")

    ext = p.suffix.lower()

    if ext == ".csv":
        import csv
        with open(tbl_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = [list(row) for row in reader]
        if not rows:
            raise ValueError(f"CSV 表格为空: {tbl_path}")
        # 构建 markdown 表格
        header = rows[0]
        data_rows = rows[1:]
        ncols = len(header)
        # 对齐所有行到相同列数
        for i, row in enumerate(data_rows):
            if len(row) < ncols:
                data_rows[i] = row + [""] * (ncols - len(row))
        lines = ["| " + " | ".join(header) + " |"]
        lines.append("|" + "|".join(["---"] * ncols) + "|")
        for row in data_rows:
            lines.append("| " + " | ".join(row[:ncols]) + " |")
        return "\n".join(lines)

    elif ext in (".xlsx", ".xls"):
        try:
            import openpyxl
        except ImportError:
            raise ImportError("需要 openpyxl 来读取 xlsx 表格，请安装: pip install openpyxl")
        wb = openpyxl.load_workbook(tbl_path, data_only=True, read_only=True)
        ws = wb.active
        rows = []
        for row in ws.iter_rows(values_only=True):
            rows.append([str(cell) if cell is not None else "" for cell in row])
        wb.close()
        if not rows:
            raise ValueError(f"xlsx 表格为空: {tbl_path}")
        header = rows[0]
        data_rows = rows[1:]
        ncols = len(header)
        lines = ["| " + " | ".join(header) + " |"]
        lines.append("|" + "|".join(["---"] * ncols) + "|")
        for row in data_rows:
            padded = row + [""] * (ncols - len(row)) if len(row) < ncols else row
            lines.append("| " + " | ".join(padded[:ncols]) + " |")
        return "\n".join(lines)

    elif ext == ".md":
        content = p.read_text(encoding="utf-8").strip()
        if not content:
            raise ValueError(f"md 表格文件为空: {tbl_path}")
        # 剥离顶部粗体标题行（如 **变量描述性统计**），标题由 writer 的 caption 提供
        lines = content.split("\n")
        while lines and lines[0].strip().startswith("**") and lines[0].strip().endswith("**"):
            lines.pop(0)
        while lines and not lines[0].strip():
            lines.pop(0)
        return "\n".join(lines)

    else:
        raise ValueError(
            f"不支持的表格资产格式: {ext}（文件: {tbl_path}）。"
            f"仅支持 .csv / .xlsx / .md，不支持的格式不得静默跳过。"
        )


def _check_caption_adjacency(md_text: str) -> list[str]:
    """检查 [TABLE:] 和 [FIGURE:] 占位符周围是否有正确的表题/图题。

    [TABLE: table_XX] 的前一个非空段落必须匹配：^表\\s*\\d+\\s+.+$
    [FIGURE: fig_XX] 的后一个非空段落必须匹配：^图\\s*\\d+\\s+.+$

    Returns:
        错误信息列表，空列表表示全部通过。
    """
    errors = []
    lines = md_text.split("\n")

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Check [TABLE: ...] — previous non-blank line must be a table caption
        tbl_match = re.match(r"^\[TABLE:\s*(\S+?)\s*\]$", stripped)
        if tbl_match:
            tbl_id = tbl_match.group(1)
            prev = ""
            for j in range(i - 1, -1, -1):
                if lines[j].strip():
                    prev = lines[j].strip()
                    break
            if not re.match(r"^表\s*\d+\s+.+$", prev):
                errors.append(
                    f"[TABLE: {tbl_id}] 前一个非空段落必须为表题（格式：'表X 标题内容'），"
                    f"实际为：'{prev or '(无)'}'"
                )

        # Check [FIGURE: ...] — next non-blank line must be a figure caption
        fig_match = re.match(r"^\[FIGURE:\s*(\S+?)\s*\]$", stripped)
        if fig_match:
            fig_id = fig_match.group(1)
            nxt = ""
            for j in range(i + 1, len(lines)):
                if lines[j].strip():
                    nxt = lines[j].strip()
                    break
            if not re.match(r"^图\s*\d+\s+.+$", nxt):
                errors.append(
                    f"[FIGURE: {fig_id}] 后一个非空段落必须为图题（格式：'图X 标题内容'），"
                    f"实际为：'{nxt or '(无)'}'"
                )

    return errors


def replace_asset_placeholders(
    md_text: str,
    assets: dict,
) -> tuple[str, dict]:
    """Replace [FIGURE: id] and [TABLE: id] placeholders in markdown.

    Only replaces content; does NOT add titles or auto-number.
    Title adjacency is validated separately by _check_caption_adjacency().

    Returns (modified_md, stats) where stats has 'figures_replaced', 'tables_replaced',
    'figures_missing', 'tables_missing'.
    """
    stats = {"figures_replaced": 0, "tables_replaced": 0, "figures_missing": [], "tables_missing": []}

    # Build lookup maps
    fig_map = {f["id"]: f for f in assets.get("figures", [])}
    tbl_map = {t["id"]: t for t in assets.get("tables", [])}

    def _replace_fig(m):
        fig_id = m.group(1)
        fig = fig_map.get(fig_id)
        if not fig:
            stats["figures_missing"].append(fig_id)
            return m.group(0)  # leave placeholder as-is
        abs_path = str(Path(fig["path"]).resolve())
        stats["figures_replaced"] += 1
        # alt text 为空，标题由 writer 的 caption（图 X 标题）提供
        return f"![]({abs_path})"

    def _replace_tbl(m):
        tbl_id = m.group(1)
        tbl = tbl_map.get(tbl_id)
        if not tbl:
            stats["tables_missing"].append(tbl_id)
            return m.group(0)  # leave placeholder as-is
        abs_path = str(Path(tbl["path"]).resolve())
        try:
            md_table = render_table_asset_as_markdown(abs_path)
        except (FileNotFoundError, ValueError, ImportError) as exc:
            stats["tables_missing"].append(tbl_id)
            logger.error("TABLE asset render failed for %s: %s", tbl_id, exc)
            return m.group(0)  # leave placeholder as-is; will be caught by validation
        stats["tables_replaced"] += 1
        return md_table

    result = _FIGURE_PLACEHOLDER.sub(_replace_fig, md_text)
    result = _TABLE_PLACEHOLDER.sub(_replace_tbl, result)
    return result, stats


def _validate_assets_embedded(
    md_text: str,
    assets: dict,
    placeholder_stats: dict,
) -> list[str]:
    """Check that all required assets are accounted for.

    Returns list of warning strings (empty = all good).
    """
    warnings = []
    if not assets:
        return warnings

    fig_map = {f["id"]: f for f in assets.get("figures", [])}
    tbl_map = {t["id"]: t for t in assets.get("tables", [])}

    # Check missing figures
    for fig_id in placeholder_stats.get("figures_missing", []):
        fig = fig_map.get(fig_id)
        if fig and fig.get("required", True):
            warnings.append(f"Required figure not found in manifest: {fig_id}")

    # Check missing tables
    for tbl_id in placeholder_stats.get("tables_missing", []):
        tbl = tbl_map.get(tbl_id)
        if tbl and tbl.get("required", True):
            warnings.append(f"Required table not found in manifest: {tbl_id}")

    # Check for leftover placeholders
    leftover_fig = _FIGURE_PLACEHOLDER.findall(md_text)
    if leftover_fig:
        warnings.append(f"Leftover [FIGURE:] placeholders: {leftover_fig}")
    leftover_tbl = _TABLE_PLACEHOLDER.findall(md_text)
    if leftover_tbl:
        warnings.append(f"Leftover [TABLE:] placeholders: {leftover_tbl}")

    # Check for leftover TABLE_ASSET comments (should be consumed by post-processing)
    leftover_assets = re.findall(r'<!--TABLE_ASSET:([^:]+):', md_text)
    if leftover_assets:
        warnings.append(f"Leftover TABLE_ASSET comments: {leftover_assets}")

    # Count placeholders actually present in markdown vs replaced
    replaced_figs = placeholder_stats.get("figures_replaced", 0)
    replaced_tbls = placeholder_stats.get("tables_replaced", 0)
    actual_fig_placeholders = len(_FIGURE_PLACEHOLDER.findall(md_text)) + replaced_figs
    actual_tbl_placeholders = len(_TABLE_PLACEHOLDER.findall(md_text)) + replaced_tbls

    if replaced_figs < actual_fig_placeholders:
        warnings.append(f"Only {replaced_figs}/{actual_fig_placeholders} figure placeholders replaced")
    if replaced_tbls < actual_tbl_placeholders:
        warnings.append(f"Only {replaced_tbls}/{actual_tbl_placeholders} table placeholders replaced")

    return warnings


# ---------------------------------------------------------------------------
# find_pandoc
# ---------------------------------------------------------------------------

def find_pandoc(cli_path: str | None = None) -> str:
    """Locate pandoc binary with this priority:
    1. cli_path (--pandoc argument)
    2. PANDOC_PATH env var
    3. shutil.which('pandoc')
    4. pypandoc.get_pandoc_path()
    5. Raise RuntimeError
    """
    # 1. CLI argument
    if cli_path:
        if os.path.isfile(cli_path) and os.access(cli_path, os.X_OK):
            return cli_path
        raise RuntimeError(f"--pandoc path not executable: {cli_path}")

    # 2. Environment variable
    env_path = os.environ.get("PANDOC_PATH")
    if env_path and os.path.isfile(env_path) and os.access(env_path, os.X_OK):
        return env_path

    # 3. shutil.which
    which_path = shutil.which("pandoc")
    if which_path:
        return which_path

    # 4. pypandoc
    try:
        import pypandoc
        return pypandoc.get_pandoc_path()
    except (ImportError, OSError):
        pass

    # 5. Not found
    raise RuntimeError(
        "pandoc not found. Install one of the following ways:\n"
        "  - Ubuntu/Debian: sudo apt install pandoc\n"
        "  - macOS: brew install pandoc\n"
        "  - conda: conda install -c conda-forge pandoc\n"
        "  - Or set PANDOC_PATH=/path/to/pandoc\n"
        "  - Or pass --pandoc /path/to/pandoc"
    )


# ---------------------------------------------------------------------------
# run_pandoc
# ---------------------------------------------------------------------------

def run_pandoc(
    markdown: str,
    raw_docx: str,
    reference_doc: str | None,
    pandoc_path: str,
    cwd: str | None = None,
    resource_path: list[str] | None = None,
) -> str:
    """Run pandoc to convert markdown -> docx. Returns pandoc version string.

    Args:
        cwd: Working directory for pandoc (typically markdown's parent dir).
        resource_path: List of directories for pandoc to search for images/resources.
    """
    # Get pandoc version
    version_out = subprocess.run(
        [pandoc_path, "--version"],
        capture_output=True, text=True, timeout=30,
    )
    version_str = version_out.stdout.strip().split("\n")[0] if version_out.stdout else "unknown"

    cmd = [
        pandoc_path,
        markdown,
        "--from", "markdown+tex_math_dollars+tex_math_single_backslash",
        "--to", "docx",
    ]
    if reference_doc and os.path.isfile(reference_doc):
        cmd += ["--reference-doc", reference_doc]
    if resource_path:
        cmd += ["--resource-path", os.pathsep.join(resource_path)]
    cmd += ["-o", raw_docx]

    logger.info("pandoc cmd: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(
            f"pandoc failed (exit {result.returncode}):\n"
            f"  stdout: {result.stdout}\n"
            f"  stderr: {result.stderr}"
        )
    if result.stderr:
        logger.warning("pandoc stderr: %s", result.stderr.strip())

    return version_str


# ---------------------------------------------------------------------------
# count_markdown_formulas
# ---------------------------------------------------------------------------

def count_markdown_formulas(markdown_path: str) -> tuple[int, int]:
    """Count inline ($) and block ($$) formulas in markdown. Returns (inline, block)."""
    text = Path(markdown_path).read_text(encoding="utf-8")

    # Count block formulas first (so they don't get double-counted as inline)
    block_pattern = r'\$\$(.+?)\$\$'
    block_matches = re.findall(block_pattern, text, re.DOTALL)
    block_count = len(block_matches)

    # Remove block formulas, then count inline
    text_no_block = re.sub(block_pattern, '', text, flags=re.DOTALL)
    inline_pattern = r'(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)'
    inline_matches = re.findall(inline_pattern, text_no_block)
    inline_count = len(inline_matches)

    return inline_count, block_count


# ---------------------------------------------------------------------------
# open_docx_safely
# ---------------------------------------------------------------------------

def open_docx_safely(path: str) -> Document:
    """Open a docx file, raising clear error if missing."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"docx not found: {path}")
    return Document(str(p))


# ---------------------------------------------------------------------------
# Post-processing: normalize_heading_styles
# ---------------------------------------------------------------------------

def _ensure_style(doc: Document, name: str) -> None:
    """Ensure a built-in heading style exists in the document."""
    try:
        doc.styles[name]
    except KeyError:
        from docx.enum.style import WD_STYLE_TYPE
        doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)


def normalize_heading_styles(doc: Document) -> int:
    """Fix heading hierarchy:
    - First Heading 1 -> Normal + centered (paper title)
    - Heading 2 -> Heading 1
    - Heading 3 -> Heading 2
    - Heading 4 -> Heading 3
    Returns count of headings adjusted.
    """
    # Ensure target styles exist before assigning
    for s in ("Heading 1", "Heading 2", "Heading 3"):
        _ensure_style(doc, s)

    count = 0
    first_h1_seen = False

    for para in doc.paragraphs:
        style_name = para.style.name if para.style else ""
        if style_name == "Heading 1":
            if not first_h1_seen:
                # Paper title -> Normal, centered
                para.style = doc.styles["Normal"]
                para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                first_h1_seen = True
                count += 1
            # else: keep as Heading 1 (was already Heading 2 in markdown)
        elif style_name == "Heading 2":
            para.style = doc.styles["Heading 1"]
            count += 1
        elif style_name == "Heading 3":
            para.style = doc.styles["Heading 2"]
            count += 1
        elif style_name == "Heading 4":
            para.style = doc.styles["Heading 3"]
            count += 1

    return count


# ---------------------------------------------------------------------------
# Post-processing: set_run_fonts
# ---------------------------------------------------------------------------

def _get_body_fonts(template_rules: dict) -> tuple[str, str]:
    """Extract (east_asia, ascii) fonts from template rules for body text.

    Falls back to 宋体 / Times New Roman if not specified.
    """
    rules = template_rules.get("rules", {})
    body = rules.get("body", {})
    east_asia = body.get("font_name_east_asia") or body.get("font_name", "宋体")
    # For ascii, prefer a Latin font name; if body font is Chinese, use default
    ascii_font = body.get("font_name", "Times New Roman")
    # If the font is a Chinese font name, check if there's a separate ascii hint
    if ascii_font in ("宋体", "黑体", "楷体", "仿宋"):
        ascii_font = "Times New Roman"
    return east_asia, ascii_font


def _get_title_fonts(template_rules: dict) -> tuple[str, str] | None:
    """Extract fonts for the paper title from template rules.

    Returns (east_asia, ascii) or None if no title rule found.
    """
    rules = template_rules.get("rules", {})
    title = rules.get("title", {})
    if not title:
        return None
    east_asia = title.get("font_name_east_asia") or title.get("font_name")
    ascii_font = title.get("font_name")
    if not east_asia and not ascii_font:
        return None
    if not east_asia:
        east_asia = "黑体"
    if not ascii_font or ascii_font in ("宋体", "黑体", "楷体", "仿宋"):
        ascii_font = "Times New Roman"
    return east_asia, ascii_font


def _get_heading_fonts(template_rules: dict, heading_level: int) -> tuple[str, str] | None:
    """Extract fonts for a specific heading level from template rules.

    Returns (east_asia, ascii) or None if no heading rule found.
    """
    rules = template_rules.get("rules", {})
    key = f"heading{heading_level}"
    heading = rules.get(key, {})
    if not heading or heading.get("source") == "fallback_default":
        return None
    east_asia = heading.get("font_name_east_asia") or heading.get("font_name")
    ascii_font = heading.get("font_name")
    if not east_asia and not ascii_font:
        return None
    if not east_asia:
        east_asia = "宋体"
    if not ascii_font or ascii_font in ("宋体", "黑体", "楷体", "仿宋"):
        ascii_font = "Times New Roman"
    return east_asia, ascii_font


def set_run_fonts(
    run,
    east_asia: str = "\u5b8b\u4f53",
    ascii_font: str = "Times New Roman",
    font_size_pt: float | None = None,
) -> None:
    """Set font on a single run: east_asia + ascii, optionally font size."""
    rpr = run._element.get_or_add_rPr()

    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)

    rfonts.set(qn("w:eastAsia"), east_asia)
    rfonts.set(qn("w:ascii"), ascii_font)
    rfonts.set(qn("w:hAnsi"), ascii_font)

    if font_size_pt is not None:
        from docx.shared import Pt
        run.font.size = Pt(font_size_pt)


# ---------------------------------------------------------------------------
# Post-processing: normalize_paragraphs
# ---------------------------------------------------------------------------

def normalize_paragraphs(doc: Document, template_rules: dict = None) -> int:
    """Set first-line indent of 2 chars (approx 480 twips = 2 * 12pt * 20twips/pt * 2)
    for body paragraphs that are not headings, captions, or special blocks.

    If template_rules provides body.first_line_indent_chars, use that instead.
    """
    # Heading style names to skip
    heading_styles = {"Heading 1", "Heading 2", "Heading 3", "Heading 4", "Heading 5"}

    # Determine indent from template rules or fallback to 2 chars
    indent_chars = 2
    if template_rules:
        body_rules = template_rules.get("rules", {}).get("body", {})
        if "first_line_indent_chars" in body_rules:
            indent_chars = body_rules["first_line_indent_chars"]
    INDENT_TWIPS = int(indent_chars * 240)  # 1 char ≈ 12pt = 240 twips

    count = 0
    for para in doc.paragraphs:
        style_name = para.style.name if para.style else ""
        if style_name in heading_styles:
            continue
        # Skip centered paragraphs (likely titles)
        if para.alignment == WD_ALIGN_PARAGRAPH.CENTER:
            continue
        # Skip empty paragraphs
        text = para.text.strip()
        if not text:
            continue
        # Skip table/figure captions
        if is_caption(text):
            continue
        # Skip if starts with special labels
        if text.startswith("\u6458\u8981") or text.startswith("\u5173\u952e\u8bcd"):
            continue

        # Apply first-line indent
        ppr = para._element.get_or_add_pPr()
        ind = ppr.find(qn("w:ind"))
        if ind is None:
            ind = OxmlElement("w:ind")
            ppr.append(ind)
        ind.set(qn("w:firstLineChars"), "200")
        ind.set(qn("w:firstLine"), str(INDENT_TWIPS))

        count += 1

    return count


# ---------------------------------------------------------------------------
# Post-processing: normalize_abstract_keywords
# ---------------------------------------------------------------------------

def normalize_abstract_keywords(doc: Document) -> int:
    """Format '摘要' and '关键词' labels with bold styling.

    Only bold these labels when they appear at the start of the paragraph
    (followed by a colon, dash, or similar separator), to avoid false
    positives when the words appear in body text (e.g. '关键词频次').
    """
    # Labels to bold: must appear at paragraph start followed by separator
    _label_re = re.compile(r"^(摘要|关键词)\s*[：:、\-]")

    count = 0
    for para in doc.paragraphs:
        text = para.text
        if not text:
            continue
        # Only process paragraphs that start with a label
        if not _label_re.match(text.lstrip()):
            continue
        # Bold only the label portion (first run(s) up to the separator)
        label_bold_done = False
        for run in para.runs:
            run_text = run.text
            if not label_bold_done and (
                "\u6458\u8981" in run_text or "\u5173\u952e\u8bcd" in run_text
            ):
                run.bold = True
                set_run_fonts(run)
                # If separator is also in this run, stop bolding after this
                if "\uff1a" in run_text or ":" in run_text:
                    label_bold_done = True
                count += 1
            else:
                if not label_bold_done:
                    # Separator might be in a separate run
                    if "\uff1a" in run_text or ":" in run_text:
                        label_bold_done = True
                set_run_fonts(run)
    return count


# ---------------------------------------------------------------------------
# Post-processing: superscript_numeric_citations
# ---------------------------------------------------------------------------

def superscript_numeric_citations(doc: Document) -> int:
    """Convert [1], [2], [1,2] style citations to superscript."""
    count = 0
    cite_pattern = re.compile(r"\[(\d+(?:[,，\s]\d+)*)\]")

    for para in doc.paragraphs:
        # Check if paragraph contains math elements -- skip those
        if para._element.find(qn("m:oMathPara")) is not None:
            continue
        if para._element.find(qn("m:oMath")) is not None:
            continue

        runs_to_process = []
        for run in para.runs:
            if cite_pattern.search(run.text):
                runs_to_process.append(run)

        for run in runs_to_process:
            text = run.text
            parts = cite_pattern.split(text)
            if not parts:
                continue

            # We need to rebuild this run into multiple runs
            parent = run._element.getparent()
            run_index = list(parent).index(run._element)

            new_elements = []
            last_end = 0
            for m in cite_pattern.finditer(text):
                # Text before citation
                before = text[last_end:m.start()]
                if before:
                    r_before = _make_text_run(before, run)
                    new_elements.append(r_before)

                # Citation text as superscript
                cite_text = m.group(0)
                r_cite = _make_superscript_run(cite_text, run)
                new_elements.append(r_cite)
                count += 1

                last_end = m.end()

            # Remaining text after last citation
            remaining = text[last_end:]
            if remaining:
                r_after = _make_text_run(remaining, run)
                new_elements.append(r_after)

            # Replace original run with new runs
            parent.remove(run._element)
            for i, elem in enumerate(new_elements):
                parent.insert(run_index + i, elem)

    return count


def _make_text_run(text: str, source_run) -> OxmlElement:
    """Create a normal run element copying formatting from source_run."""
    r = OxmlElement("w:r")
    # Copy run properties from source (without superscript)
    rpr_src = source_run._element.find(qn("w:rPr"))
    if rpr_src is not None:
        import copy
        rpr = copy.deepcopy(rpr_src)
        # Remove any existing vertAlign
        va = rpr.find(qn("w:vertAlign"))
        if va is not None:
            rpr.remove(va)
        r.append(rpr)
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    r.append(t)
    return r


def _make_superscript_run(text: str, source_run) -> OxmlElement:
    """Create a superscript run element."""
    r = OxmlElement("w:r")
    import copy
    rpr_src = source_run._element.find(qn("w:rPr"))
    if rpr_src is not None:
        rpr = copy.deepcopy(rpr_src)
    else:
        rpr = OxmlElement("w:rPr")
    # Add superscript
    va = rpr.find(qn("w:vertAlign"))
    if va is not None:
        rpr.remove(va)
    va = OxmlElement("w:vertAlign")
    va.set(qn("w:val"), "superscript")
    rpr.append(va)
    # Ensure rFonts is present
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    rfonts.set(qn("w:eastAsia"), "\u5b8b\u4f53")
    rfonts.set(qn("w:ascii"), "Times New Roman")
    rfonts.set(qn("w:hAnsi"), "Times New Roman")
    r.append(rpr)
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    r.append(t)
    return r


# ---------------------------------------------------------------------------
# Helper: is_caption
# ---------------------------------------------------------------------------

def is_caption(text: str) -> bool:
    """判断段落是否为图表标题。

    只匹配「表/图 + 编号 + 空格 + 标题文字」的真正标题，
    不匹配「表1报告了……」「图1展示了……」等正文引用。
    """
    t = text.strip()
    if not re.match(r'^[表图]\s*\d+\s+.+', t):
        return False
    # 排除正文引用模式
    if re.match(
        r'^[表图]\s*\d+\s*'
        r'(报告|展示|说明|指出|呈现|反映|列出|给出|揭示了?|显示了?|直观展示了?)',
        t,
    ):
        return False
    return True


# ---------------------------------------------------------------------------
# Post-processing: center_captions
# ---------------------------------------------------------------------------

def center_captions(doc: Document) -> int:
    """Center paragraphs starting with '表X' or '图X' (table/figure captions).
    Also sets keep_with_next so captions stick to the following table/figure."""
    count = 0
    for para in doc.paragraphs:
        text = para.text.strip()
        if is_caption(text):
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            pf = para.paragraph_format
            pf.keep_with_next = True
            # Set fonts on caption runs
            for run in para.runs:
                set_run_fonts(run)
            count += 1
    return count


# ---------------------------------------------------------------------------
# Post-processing: three-line tables
# ---------------------------------------------------------------------------

def _get_or_create_tc_borders(cell):
    """Get or create w:tcBorders on a table cell, avoiding duplicates."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    borders = tcPr.find(qn("w:tcBorders"))
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tcPr.append(borders)
    return borders


def _set_tc_border(cell, edge: str, val: str = "single", sz: str = "8"):
    """Set a single border edge on a table cell. Reuses existing element."""
    borders = _get_or_create_tc_borders(cell)
    border = borders.find(qn(f"w:{edge}"))
    if border is None:
        border = OxmlElement(f"w:{edge}")
        borders.append(border)
    border.set(qn("w:val"), val)
    border.set(qn("w:sz"), sz)
    border.set(qn("w:space"), "0")
    border.set(qn("w:color"), "000000")


def apply_three_line_table(table) -> None:
    """Apply three-line style to a single table:
    - Header row: top thick (12), bottom thin (6)
    - Last row: bottom thick (12)
    - All other borders: none
    """
    nrows = len(table.rows)
    if nrows == 0:
        return

    # First: clear all borders on all cells
    for row in table.rows:
        for cell in row.cells:
            for edge in ("top", "bottom", "left", "right", "insideH", "insideV"):
                _set_tc_border(cell, edge, val="none", sz="0")

    # Header row: top + bottom
    for cell in table.rows[0].cells:
        _set_tc_border(cell, "top", "single", "12")
        _set_tc_border(cell, "bottom", "single", "6")

    # Last row: bottom only
    for cell in table.rows[-1].cells:
        _set_tc_border(cell, "bottom", "single", "12")


def apply_three_line_tables(doc: Document) -> int:
    """Apply three-line style to all tables in document."""
    count = 0
    for table in doc.tables:
        apply_three_line_table(table)
        # Also set fonts in all table cells
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    for run in para.runs:
                        set_run_fonts(run)
        count += 1
    return count


# ---------------------------------------------------------------------------
# Post-processing: fix_table_formatting
# ---------------------------------------------------------------------------

def fix_table_formatting(doc: Document) -> int:
    """Apply table-level formatting: alignment, font size, cell alignment.

    - Center the table itself on the page.
    - Font size: 9pt for normal tables (< 8 cols), 8pt for wide tables (>= 8 cols).
    - Header row (first row): all cells centered.
    - Data rows: first column left-aligned, remaining columns centered.
    Returns count of tables processed.
    """
    count = 0
    for table in doc.tables:
        # --- table-level centering ---
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        ncols = len(table.columns)
        font_size = Pt(8) if ncols >= 8 else Pt(9)
        nrows = len(table.rows)

        for row_idx, row in enumerate(table.rows):
            for col_idx, cell in enumerate(row.cells):
                for para in cell.paragraphs:
                    # --- font size ---
                    for run in para.runs:
                        run.font.size = font_size
                    # --- cell alignment ---
                    if row_idx == 0:
                        # Header row: all cells centered
                        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    else:
                        if col_idx == 0:
                            # First column: left-aligned (default)
                            para.alignment = WD_ALIGN_PARAGRAPH.LEFT
                        else:
                            # Other columns: centered
                            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        count += 1
    return count


# ---------------------------------------------------------------------------
# Post-processing: protect_math_objects
# ---------------------------------------------------------------------------

def protect_math_objects(doc: Document) -> int:
    """Ensure m:oMath / m:oMathPara elements are not disturbed.
    This is a no-op guard: we log count but do not modify math elements."""
    count = 0
    body = doc.element.body
    # Count m:oMathPara (block math)
    count += len(body.findall(f".//{qn('m:oMathPara')}"))
    # Count m:oMath that are NOT inside m:oMathPara (inline math)
    for omath in body.findall(f".//{qn('m:oMath')}"):
        parent = omath.getparent()
        if parent is not None and parent.tag != qn("m:oMathPara"):
            count += 1
    return count


# ---------------------------------------------------------------------------
# Post-processing: insert_images
# ---------------------------------------------------------------------------

def insert_images(doc: Document, figures_dir: str) -> int:
    """Insert PNG images at markdown image reference points in the document.
    Looks for paragraphs containing '![alt](filename.png)' patterns.
    """
    if not figures_dir or not os.path.isdir(figures_dir):
        return 0

    figures_path = Path(figures_dir)
    img_pattern = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
    count = 0

    # Collect paragraphs to process (avoid modifying while iterating)
    paras_to_process = []
    for para in doc.paragraphs:
        if img_pattern.search(para.text):
            paras_to_process.append(para)

    for para in paras_to_process:
        full_text = para.text
        matches = list(img_pattern.finditer(full_text))
        if not matches:
            continue

        # For each image reference, try to find the file
        for m in reversed(matches):
            img_filename = m.group(2)
            img_path = figures_path / img_filename

            # Also try with common extensions
            if not img_path.exists():
                for ext in [".png", ".jpg", ".jpeg", ".PNG", ".JPG"]:
                    candidate = figures_path / (img_filename + ext)
                    if candidate.exists():
                        img_path = candidate
                        break

            if not img_path.exists():
                logger.warning("image not found: %s (looked in %s)", img_filename, figures_dir)
                continue

            # Clear the paragraph and insert the image
            # We insert into a new paragraph before this one, then remove text
            # from the original (or clear it if it was only an image ref)
            if full_text.strip() == m.group(0):
                # Entire paragraph is just the image reference
                para.clear()
                run = para.add_run()
                run.add_picture(str(img_path), width=None)
                para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                count += 1
            else:
                # Paragraph has other text; just log a warning
                logger.warning(
                    "image reference '%s' mixed with other text in paragraph, skipping auto-insert",
                    img_filename,
                )

    return count


# ---------------------------------------------------------------------------
# save_and_roundtrip_check
# ---------------------------------------------------------------------------

def save_and_roundtrip_check(doc: Document, output_path: str) -> dict:
    """Save document and verify by re-opening. Returns stats dict."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    doc.save(str(out))

    # Roundtrip check: re-open and count elements
    doc2 = Document(str(out))
    stats = {
        "paragraphs": len(doc2.paragraphs),
        "tables": len(doc2.tables),
        "sections": len(doc2.sections),
    }

    # Count math objects
    body = doc2.element.body
    stats["math_omathpara"] = len(body.findall(f".//{qn('m:oMathPara')}"))
    omath_all = body.findall(f".//{qn('m:oMath')}")
    stats["math_omath"] = len(omath_all)

    return stats


# ---------------------------------------------------------------------------
# write_build_log
# ---------------------------------------------------------------------------

def write_build_log(log_path: str, **kwargs) -> None:
    """Write a markdown build log with all pipeline information."""
    lines = [
        "# DOCX Build Log",
        "",
        f"**Generated**: {_now()}",
        "",
        "## Environment",
        "",
        f"- **pandoc source**: {kwargs.get('pandoc_source', 'N/A')}",
        f"- **pandoc version**: {kwargs.get('pandoc_version', 'N/A')}",
        "",
        "## Input",
        "",
        f"- **markdown**: `{kwargs.get('markdown', 'N/A')}`",
        f"- **reference-doc**: `{kwargs.get('reference_doc', 'N/A')}`",
        f"- **tables dir**: `{kwargs.get('tables_dir', 'N/A')}`",
        f"- **figures dir**: `{kwargs.get('figures_dir', 'N/A')}`",
        "",
        "## Formula Counts (Markdown)",
        "",
        f"- **inline ($)**: {kwargs.get('inline_formulas', 0)}",
        f"- **block ($$)**: {kwargs.get('block_formulas', 0)}",
        "",
        "## Formula Counts (Word)",
        "",
        f"- **m:oMathPara (block)**: {kwargs.get('math_omathpara', 0)}",
        f"- **m:oMath (inline + block)**: {kwargs.get('math_omath', 0)}",
        "",
        "## Document Stats",
        "",
        f"- **paragraphs**: {kwargs.get('paragraphs', 0)}",
        f"- **tables**: {kwargs.get('tables', 0)}",
        f"- **sections**: {kwargs.get('sections', 0)}",
        "",
        "## Image Counts",
        "",
        f"- **Markdown images**: {kwargs.get('markdown_images', 0)}",
        f"- **Images embedded in docx**: {kwargs.get('docx_embedded_images', 0)}",
        f"- **Images inserted by postprocess**: {kwargs.get('postprocess_images_inserted', 0)}",
        "",
        "## Asset Counts",
        "",
        f"- **assets_manifest**: `{kwargs.get('assets_manifest_path', '(not provided)')}`",
        f"- **figures required**: {kwargs.get('asset_fig_required', 0)}",
        f"- **figures replaced**: {kwargs.get('asset_fig_replaced', 0)}",
        f"- **tables required**: {kwargs.get('asset_tbl_required', 0)}",
        f"- **tables replaced**: {kwargs.get('asset_tbl_replaced', 0)}",
        f"- **missing assets**: {kwargs.get('asset_missing', 0)}",
        "",
        "## Manifest",
        "",
        f"- **manifest_path**: `{kwargs.get('manifest_path', '(not provided)')}`",
        f"- **template_rules**: `{kwargs.get('template_rules_path', '(not provided)')}`",
        f"- **output_format**: {kwargs.get('manifest_output_format', '(unknown)')}",
        f"- **pandoc dependency**: {kwargs.get('manifest_pandoc_status', '(unknown)')}",
        "",
        "## Post-processing Steps",
        "",
    ]

    steps = kwargs.get("post_steps", {})
    for step_name, detail in steps.items():
        lines.append(f"- **{step_name}**: {detail}")

    warnings = kwargs.get("warnings", [])
    if warnings:
        lines.append("")
        lines.append("## Warnings")
        lines.append("")
        for w in warnings:
            lines.append(f"- {w}")

    lines.append("")

    log_file = Path(log_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def build_docx(args: argparse.Namespace) -> int:
    """Run the full pipeline. Returns 0 on success, 1 on error."""
    warnings = []

    # 0. Load manifest (optional)
    manifest = load_manifest(args.manifest) if args.manifest else {}
    if not manifest and args.manifest:
        warnings.append(f"manifest not found or invalid: {args.manifest}")
    elif not args.manifest:
        warnings.append("manifest: not provided")

    # 0b. Load template rules (optional)
    template_rules = load_template_rules(args.template_rules, manifest)
    if template_rules:
        body_ea, body_ascii = _get_body_fonts(template_rules)
        logger.info("template rules loaded: body fonts = %s / %s", body_ea, body_ascii)
    else:
        body_ea, body_ascii = "宋体", "Times New Roman"

    # 0b2. Template rules mandatory when Word template exists
    word_template_file = manifest.get("word_template_file")
    has_word_template = bool(args.reference_doc or word_template_file)
    if has_word_template and not template_rules:
        msg = (
            "FATAL: Word 模板已指定但 template_rules.json 缺失。"
            "请先运行 extract_word_template_rules.py 生成 template_rules.json。"
        )
        print(msg, file=sys.stderr)
        logger.error(msg)
        return 1

    # 0c. Load assets manifest (optional)
    assets = load_assets_manifest(args.assets_manifest, manifest)

    # 1. Find pandoc
    try:
        pandoc_path = find_pandoc(args.pandoc)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    pandoc_source = "cli"
    if args.pandoc:
        pandoc_source = "--pandoc"
    elif os.environ.get("PANDOC_PATH"):
        pandoc_source = "PANDOC_PATH env"
    elif shutil.which("pandoc"):
        pandoc_source = "shutil.which"
    else:
        try:
            import pypandoc  # noqa: F401
            pandoc_source = "pypandoc"
        except ImportError:
            pandoc_source = "unknown"

    # 2. Validate inputs
    md_path = Path(args.markdown)
    if not md_path.exists():
        print(f"ERROR: markdown not found: {args.markdown}", file=sys.stderr)
        return 1

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    reference_doc = args.reference_doc if args.reference_doc else None
    if reference_doc and not Path(reference_doc).exists():
        logger.warning("reference-doc not found: %s, proceeding without it", reference_doc)
        warnings.append(f"reference-doc not found: {reference_doc}")
        reference_doc = None

    # 3. Count markdown formulas
    inline_count, block_count = count_markdown_formulas(str(md_path))

    # 4. Run pandoc — all processing inside tempdir lifetime
    img_count = 0
    post_steps = {}
    stats = {}

    with tempfile.TemporaryDirectory(prefix="gen_docx_") as tmpdir:
        raw_docx = os.path.join(tmpdir, "raw.docx")

        # 3b. Replace asset placeholders before pandoc
        md_text = md_path.read_text(encoding="utf-8")
        placeholder_stats = {}
        log_entries = []
        if assets:
            # Validate caption adjacency before replacing placeholders
            caption_errors = _check_caption_adjacency(md_text)
            if caption_errors:
                for err in caption_errors:
                    logger.error("CAPTION ADJACENCY: %s", err)
                    log_entries.append(f"CAPTION ADJACENCY ERROR: {err}")
                logger.error("Caption adjacency check failed (%d errors). Aborting.", len(caption_errors))
                _write_build_log(log_entries, args.log)
                return 1

            md_text, placeholder_stats = replace_asset_placeholders(md_text, assets)
            logger.info(
                "asset placeholders: fig=%d replaced/%d missing, tbl=%d replaced/%d missing",
                placeholder_stats.get("figures_replaced", 0),
                len(placeholder_stats.get("figures_missing", [])),
                placeholder_stats.get("tables_replaced", 0),
                len(placeholder_stats.get("tables_missing", [])),
            )

        # Write modified markdown to temp file for pandoc
        tmp_md = os.path.join(tmpdir, "paper_draft_assets.md")
        Path(tmp_md).write_text(md_text, encoding="utf-8")

        # Set up cwd and resource_path for reliable image discovery
        pandoc_cwd = str(md_path.parent)
        resource_dirs = [str(md_path.parent)]
        if args.figures and os.path.isdir(args.figures):
            resource_dirs.append(str(Path(args.figures).resolve()))
            # Also add figures subdirectories
            for sub in Path(args.figures).iterdir():
                if sub.is_dir():
                    resource_dirs.append(str(sub.resolve()))
        if args.tables and os.path.isdir(args.tables):
            resource_dirs.append(str(Path(args.tables).resolve()))

        try:
            pandoc_version = run_pandoc(
                tmp_md, raw_docx, reference_doc, pandoc_path,
                cwd=pandoc_cwd, resource_path=resource_dirs,
            )
        except RuntimeError as exc:
            print(f"ERROR: pandoc failed: {exc}", file=sys.stderr)
            return 1

        # 5. Open raw docx
        doc = open_docx_safely(raw_docx)

        # 6. Post-processing pipeline (all inside tempdir)
        post_steps = {}

        # 6a. Protect math objects (count only, no modification)
        math_count = protect_math_objects(doc)
        post_steps["protect_math_objects"] = f"{math_count} math elements preserved"

        # 6b. Normalize heading styles
        heading_count = normalize_heading_styles(doc)
        post_steps["normalize_heading_styles"] = f"{heading_count} headings adjusted"

        # 6c. Set fonts on all runs in the document body
        # Use template rules for heading-specific fonts; body uses body_ea/body_ascii
        _title_font_done = False
        for para in doc.paragraphs:
            style_name = para.style.name if para.style else ""
            # Determine fonts for this paragraph
            ea, ascii = body_ea, body_ascii
            # Paper title: first Normal paragraph with center alignment
            if (
                not _title_font_done
                and style_name == "Normal"
                and para.alignment == WD_ALIGN_PARAGRAPH.CENTER
                and para.text.strip()
            ):
                title_fonts = _get_title_fonts(template_rules)
                if title_fonts:
                    ea, ascii = title_fonts
                # Get title font size from template rules
                _title_size = None
                _tr = template_rules.get("rules", {}).get("title", {})
                if _tr.get("font_size_pt"):
                    _title_size = _tr["font_size_pt"]
                for run in para.runs:
                    set_run_fonts(run, east_asia=ea, ascii_font=ascii, font_size_pt=_title_size)
                _title_font_done = True
                continue
            elif style_name.startswith("Heading 1"):
                hfonts = _get_heading_fonts(template_rules, 1)
                if hfonts:
                    ea, ascii = hfonts
            elif style_name.startswith("Heading 2"):
                hfonts = _get_heading_fonts(template_rules, 2)
                if hfonts:
                    ea, ascii = hfonts
            elif style_name.startswith("Heading 3"):
                hfonts = _get_heading_fonts(template_rules, 3)
                if hfonts:
                    ea, ascii = hfonts
            for run in para.runs:
                set_run_fonts(run, east_asia=ea, ascii_font=ascii)
        post_steps["set_run_fonts"] = f"all runs: eastAsia={body_ea}, ascii={body_ascii}"

        # 6d. Normalize paragraphs (first-line indent)
        para_count = normalize_paragraphs(doc, template_rules)
        post_steps["normalize_paragraphs"] = f"{para_count} paragraphs indented"

        # 6e. Abstract/keywords formatting
        abstract_count = normalize_abstract_keywords(doc)
        post_steps["normalize_abstract_keywords"] = f"{abstract_count} labels formatted"

        # 6f. Superscript citations
        cite_count = superscript_numeric_citations(doc)
        post_steps["superscript_numeric_citations"] = f"{cite_count} citations superscripted"

        # 6g. Center captions
        caption_count = center_captions(doc)
        post_steps["center_captions"] = f"{caption_count} captions centered"

        # 6h. Three-line tables
        table_count = apply_three_line_tables(doc)
        post_steps["apply_three_line_tables"] = f"{table_count} tables styled"

        # 6h2. Table formatting (alignment, font size, cell alignment)
        fmt_count = fix_table_formatting(doc)
        post_steps["fix_table_formatting"] = f"{fmt_count} tables formatted"

        # 6i. Insert images
        img_count = 0
        if args.figures and os.path.isdir(args.figures):
            img_count = insert_images(doc, args.figures)
            post_steps["postprocess_images_inserted"] = f"{img_count} images inserted by postprocess"
        else:
            post_steps["postprocess_images_inserted"] = "skipped (no figures dir)"

        # 7. Save and verify (still inside tempdir)
        stats = save_and_roundtrip_check(doc, str(out_path))

    # with exited — tempdir cleaned up, but output already saved

    # 8. Count markdown images and docx embedded images
    md_text_for_images = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
    md_image_count = len(re.findall(r'!\[.*?\]\(([^)]+)\)', md_text_for_images))
    docx_embedded_images = 0
    if out_path.exists():
        try:
            import zipfile as _zf
            with _zf.ZipFile(str(out_path), 'r') as _z:
                docx_embedded_images = len([n for n in _z.namelist() if n.startswith("word/media/")])
        except Exception:
            pass

    # 8b. Validate required assets
    asset_warnings = _validate_assets_embedded(md_text, assets, placeholder_stats)
    fatal_asset_warnings = asset_warnings  # all asset warnings are fatal
    warnings.extend(asset_warnings)

    # Asset stats for build log
    asset_fig_required = sum(1 for f in assets.get("figures", []) if f.get("required", True)) if assets else 0
    asset_fig_replaced = placeholder_stats.get("figures_replaced", 0)
    asset_tbl_required = sum(1 for t in assets.get("tables", []) if t.get("required", True)) if assets else 0
    asset_tbl_replaced = placeholder_stats.get("tables_replaced", 0)
    asset_missing = len(placeholder_stats.get("figures_missing", [])) + len(placeholder_stats.get("tables_missing", []))

    # 9. Write build log
    log_path = args.log if args.log else str(out_path.parent / "docx_build_log.md")
    write_build_log(
        log_path,
        pandoc_source=pandoc_source,
        pandoc_version=pandoc_version,
        markdown=args.markdown,
        reference_doc=reference_doc or "(none)",
        template_rules_path=args.template_rules or "(none)",
        tables_dir=args.tables or "(none)",
        figures_dir=args.figures or "(none)",
        inline_formulas=inline_count,
        block_formulas=block_count,
        math_omathpara=stats.get("math_omathpara", 0),
        math_omath=stats.get("math_omath", 0),
        paragraphs=stats.get("paragraphs", 0),
        tables=stats.get("tables", 0),
        sections=stats.get("sections", 0),
        markdown_images=md_image_count,
        docx_embedded_images=docx_embedded_images,
        postprocess_images_inserted=img_count,
        post_steps=post_steps,
        warnings=warnings,
        manifest_path=args.manifest or "(not provided)",
        manifest_output_format=manifest.get("output_format", "(unknown)"),
        manifest_pandoc_status=manifest.get("dependency_status", {}).get("pandoc", "(unknown)"),
        assets_manifest_path=args.assets_manifest or "(not provided)",
        asset_fig_required=asset_fig_required,
        asset_fig_replaced=asset_fig_replaced,
        asset_tbl_required=asset_tbl_required,
        asset_tbl_replaced=asset_tbl_replaced,
        asset_missing=asset_missing,
    )

    print(f"OK: {out_path}")
    print(f"  paragraphs: {stats.get('paragraphs', 0)}")
    print(f"  tables: {stats.get('tables', 0)}")
    print(f"  math objects: {stats.get('math_omath', 0)}")
    print(f"  images embedded: {docx_embedded_images}")
    print(f"  images inserted by postprocess: {img_count}")
    print(f"  log: {log_path}")

    if fatal_asset_warnings:
        print(f"FATAL: {len(fatal_asset_warnings)} asset issue(s) detected:", file=sys.stderr)
        for w in fatal_asset_warnings:
            print(f"  - {w}", file=sys.stderr)
        return 1

    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Convert Markdown draft to formatted Word document via pandoc + python-docx",
    )
    parser.add_argument(
        "--manifest", required=False, default=None,
        help="Path to manifest.json from Stage 0 (optional)",
    )
    parser.add_argument(
        "--markdown", required=True,
        help="Path to paper_draft.md",
    )
    parser.add_argument(
        "--output", required=True,
        help="Output path for paper_final.docx",
    )
    parser.add_argument(
        "--reference-doc", default=None,
        help="Optional Word template for pandoc --reference-doc",
    )
    parser.add_argument(
        "--template-rules", default=None,
        help="Path to template_rules.json (from extract_word_template_rules.py)",
    )
    parser.add_argument(
        "--assets-manifest", default=None,
        help="Path to assets_manifest.json from Stage 3 coder",
    )
    parser.add_argument(
        "--tables", default=None,
        help="Path to tables directory (for reference)",
    )
    parser.add_argument(
        "--figures", default=None,
        help="Path to figures directory for image insertion",
    )
    parser.add_argument(
        "--log", default=None,
        help="Path for build log markdown",
    )
    parser.add_argument(
        "--pandoc", default=None,
        help="Path to pandoc binary (overrides auto-detection)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(levelname)s: %(message)s",
    )

    try:
        rc = build_docx(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        logger.exception("unhandled exception")
        sys.exit(1)

    sys.exit(rc)


if __name__ == "__main__":
    main()
