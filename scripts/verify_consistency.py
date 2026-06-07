#!/usr/bin/env python3
"""
verify_consistency.py — 论文一致性验证脚本

支持三种格式：
- latex（默认，兼容旧接口）：检查 .tex 文件
- markdown：检查 .md 文件（Word 路径中间产物）
- docx：检查 .docx 文件（Word 路径最终产物）

用法：
    python verify_consistency.py <paper_dir> <coder_output_dir> [--output-dir DIR] [--format auto|latex|markdown|docx]
    python verify_consistency.py --paper <paper_file> --results <results_summary.md> --output <report.md> --format markdown

示例：
    python verify_consistency.py paper_workspace/final_paper paper_workspace/03_coder/output
    python verify_consistency.py --paper paper_workspace/04_writer/output/paper_draft.md --results paper_workspace/03_coder/output/results_summary.md --format markdown --output paper_workspace/final_paper/markdown_consistency_report.md
    python verify_consistency.py --paper paper_workspace/final_paper/paper_final.docx --results paper_workspace/03_coder/output/results_summary.md --format docx --output paper_workspace/final_paper/docx_consistency_report.md

设计原则：
    results.json 是数字真源（single source of truth），以 results.json 为准。
    本脚本只读取上游文件进行比对，不修改任何上游产出（results.json、results_summary.md、analysis.py 等）。
    当发现不一致时，脚本只报告问题，由调用方决定回退到哪个 Stage 修复。
"""

import logging
import re
import sys
import os
import json
from pathlib import Path

logger = logging.getLogger(__name__)

from utils import extract_md_citation_numbers


# --- 行过滤白名单 ---
# 这些 LaTeX 命令开头的行在提取数字和字数统计时保留内容
_LINE_WHITELIST = [
    '\\caption', '\\text', '\\emph', '\\textbf',
    '\\section', '\\subsection', '\\subsubsection',
    '\\paragraph', '\\title', '\\author', '\\abstract',
]


def _should_keep_line(stripped: str) -> bool:
    """判断一行是否应该保留（非纯命令行、非注释）"""
    if stripped.startswith('%'):
        return False
    if stripped.startswith('\\'):
        return any(stripped.startswith(p) for p in _LINE_WHITELIST)
    return True


def _strip_latex_commands(text: str) -> str:
    """剥离 LaTeX 命令，保留正文内容"""
    text = re.sub(r'\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^}]*\})*', '', text)
    text = re.sub(r'[{}$\\&%#_^~]', '', text)
    return text


def extract_numbers_from_paper(paper_text: str) -> list[str]:
    """提取论文中的阿拉伯数字和百分比（排除 LaTeX 命令中的数字）"""
    lines = paper_text.split('\n')
    content_lines = []
    for line in lines:
        stripped = line.strip()
        if _should_keep_line(stripped):
            content_lines.append(line)

    text = '\n'.join(content_lines)

    # 匹配数字：整数、小数、百分比
    pattern = r'\b\d+\.?\d*%?\b'
    numbers = re.findall(pattern, text)
    # 过滤掉页码、年份（1900-2099）等常见非统计数字
    filtered = []
    for n in numbers:
        val = n.rstrip('%')
        try:
            v = float(val)
            # 跳过年份
            if 1900 <= v <= 2099:
                continue
            # 跳过小整数（很可能是页码或序号）
            if v == int(v) and 0 <= v <= 20:
                continue
            filtered.append(n)
        except ValueError:
            continue
    return filtered


def _is_statistical_number(num_str: str) -> bool:
    """判断一个数字是否为统计数字（而非结构性数字）。

    统计数字的特征：带小数点、带百分号。
    纯整数（如"三个变量"、"第一章"）归类为结构性数字。
    """
    if '%' in num_str:
        return True
    if '.' in num_str:
        return True
    return False


def extract_cite_keys(paper_text: str) -> list[str]:
    """提取论文中所有引用命令的 key，支持 \\cite, \\citep, \\citet, \\parencite 等"""
    pattern = r'\\(?:cite|citep|citet|parencite|autocite|citeauthor|textcite)\{([^}]+)\}'
    matches = re.findall(pattern, paper_text)
    keys = []
    for match in matches:
        # 支持 \cite{key1,key2} 多引用
        for key in match.split(','):
            key = key.strip()
            if key:
                keys.append(key)
    return keys


def extract_bibitem_keys(paper_text: str) -> list[str]:
    """提取 thebibliography 环境中所有 \\bibitem{} 的 key"""
    pattern = r'\\bibitem\{([^}]+)\}'
    return re.findall(pattern, paper_text)


def extract_bibtex_keys(paper_text: str, paper_dir: str) -> list[str]:
    """如果 paper 使用 BibTeX（\\bibliography{}），从 .bib 文件中提取所有 key。

    返回 key 列表；如果 paper 不使用 BibTeX，返回空列表。
    """
    # 检测 \bibliography{filename} 命令
    bib_cmd = re.search(r'\\bibliography\{([^}]+)\}', paper_text)
    if not bib_cmd:
        return []

    bib_names = [n.strip() for n in bib_cmd.group(1).split(',')]
    keys = []
    for bib_name in bib_names:
        # 尝试在 paper_dir 及其父目录查找 .bib 文件
        for base in [paper_dir, os.path.dirname(paper_dir), os.getcwd()]:
            bib_path = os.path.join(base, bib_name if bib_name.endswith('.bib') else bib_name + '.bib')
            if os.path.exists(bib_path):
                bib_text = Path(bib_path).read_text(encoding='utf-8', errors='ignore')
                # 匹配 @type{key, ...} 格式
                keys.extend(re.findall(r'@\w+\{([^,]+),', bib_text))
                break
    return keys


def extract_table_inputs(paper_text: str) -> list[str]:
    """提取论文中所有 \\input{tables/...} 的路径"""
    pattern = r'\\input\{([^}]*tables/[^}]+)\}'
    return re.findall(pattern, paper_text)


def extract_figure_refs(paper_text: str) -> list[str]:
    """提取论文中所有 \\includegraphics{} 的路径"""
    pattern = r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}'
    return re.findall(pattern, paper_text)


def count_paper_words(text: str) -> tuple[int, int, int, int]:
    """统计论文字数，返回 (总字数, 中文字符数, 英文单词数, 数字个数)。

    不含 LaTeX 命令和参考文献。
    """
    lines = text.split('\n')
    content_lines = []
    in_bib = False
    for line in lines:
        stripped = line.strip()
        if '\\begin{thebibliography}' in stripped:
            in_bib = True
            continue
        if in_bib:
            continue
        if _should_keep_line(stripped):
            content_lines.append(line)

    clean = '\n'.join(content_lines)
    clean = _strip_latex_commands(clean)

    chinese = re.findall(r'[\u4e00-\u9fff]', clean)
    english = re.findall(r'[a-zA-Z]+', clean)
    numbers = re.findall(r'\b\d+\.?\d*\b', clean)

    total = len(chinese) + len(english) + len(numbers)
    return total, len(chinese), len(english), len(numbers)


def load_results_summary(coder_output_dir: str) -> str:
    """加载 results_summary.md"""
    path = os.path.join(coder_output_dir, 'results_summary.md')
    if os.path.exists(path):
        return Path(path).read_text(encoding='utf-8')
    return ''


def load_results_json(results_json_path: str) -> dict | None:
    """加载 results.json"""
    if not results_json_path or not os.path.exists(results_json_path):
        return None
    try:
        with open(results_json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def extract_paper_text(paper_path: str) -> str:
    """从论文文件提取纯文本（支持 .tex/.md/.docx）"""
    if paper_path.endswith('.docx'):
        try:
            from docx import Document
            doc = Document(paper_path)
            return '\n'.join([p.text for p in doc.paragraphs])
        except Exception:
            return ''
    return Path(paper_path).read_text(encoding='utf-8')


def _is_ignorable_number(val: float) -> bool:
    """判断数字是否应忽略（年份、小整数、章节编号等）"""
    if 1900 <= val <= 2099:
        return True
    if val == int(val) and 0 <= val <= 20:
        return True
    return False


def verify_structured_numbers(results_json_path: str, paper_path: str) -> dict:
    """基于 results.json 的 reportable_values 验证论文数字。

    results.json 是数字真源（single source of truth）。
    本函数只读取 results.json 和 paper 进行比对，不修改任何文件。
    当发现不一致时，只报告问题，由调用方决定回退到 Stage 3 修复。
    """
    results = {
        'status': 'pass',
        'matched': [],
        'missing_must_report': [],
        'unmatched': [],
    }

    data = load_results_json(results_json_path)
    if not data:
        results['status'] = 'block'
        results['missing_must_report'] = ['results.json 不存在或无法解析']
        return results

    reportable_values = data.get('reportable_values', [])
    if not reportable_values:
        results['status'] = 'block'
        results['missing_must_report'] = ['reportable_values 为空']
        return results

    # 建立允许数字集合
    allowed_set = {}  # value_str -> rv_info
    for rv in reportable_values:
        vd = str(rv.get('value_display', ''))
        if vd:
            allowed_set[vd] = rv
        for af in rv.get('allowed_text_forms', []):
            if af not in allowed_set:
                allowed_set[af] = rv

    # 提取论文文本
    paper_text = extract_paper_text(paper_path)
    if not paper_text:
        results['status'] = 'block'
        results['missing_must_report'] = ['无法读取论文文本']
        return results

    # 提取论文中的数字 token
    all_nums = re.findall(r'\b\d+\.?\d*%?\b', paper_text)
    paper_num_values = set()
    for n in all_nums:
        clean = n.rstrip('%')
        try:
            v = float(clean)
            if not _is_ignorable_number(v):
                paper_num_values.add(clean)
        except ValueError:
            pass

    # 检查 must_report
    must_report_found = set()
    for rv in reportable_values:
        if not rv.get('must_report', False):
            continue
        vd = str(rv.get('value_display', ''))
        forms = [vd] + rv.get('allowed_text_forms', [])
        found = False
        for form in forms:
            if form in paper_num_values or form in paper_text:
                found = True
                break
        if found:
            must_report_found.add(rv['key'])
            results['matched'].append({
                'value': vd,
                'key': rv['key'],
                'label': rv.get('label', ''),
            })
        else:
            results['missing_must_report'].append(
                f"{rv['key']}: {vd} ({rv.get('label', '')})")

    # 检查论文中的疑似实证数字是否都在 allowed_set 中
    for num_str in paper_num_values:
        if num_str in allowed_set:
            continue
        # 尝试匹配：是否与某个 allowed 值接近但不一致
        try:
            nv = float(num_str)
        except ValueError:
            continue
        # 检查是否与某个 value_raw 接近（小数位不一致）
        is_close_but_wrong = False
        for rv in reportable_values:
            raw = rv.get('value_raw')
            if raw is not None and abs(float(raw) - nv) < 0.01 and str(num_str) != str(rv.get('value_display', '')):
                is_close_but_wrong = True
                break
        if is_close_but_wrong:
            # 取上下文
            context = ''
            for line in paper_text.split('\n'):
                if num_str in line:
                    context = line.strip()[:80]
                    break
            results['unmatched'].append({
                'number': num_str,
                'context': context,
            })

    # 判定
    if results['missing_must_report'] or results['unmatched']:
        results['status'] = 'block'
    return results


def format_structured_report(check: dict) -> str:
    """格式化结构化数字一致性报告"""
    lines = ['## 结构化数字一致性\n']
    status_emoji = {'pass': '✅', 'warn': '⚠️', 'block': '❌'}
    emoji = status_emoji.get(check['status'], '?')
    lines.append(f'### 总体结论\n{emoji} {check["status"].upper()}\n')

    if check['matched']:
        lines.append('### 已匹配数字\n')
        lines.append('| value | key | label |')
        lines.append('|---|---|---|')
        for m in check['matched']:
            lines.append(f"| {m['value']} | {m['key']} | {m['label']} |")
        lines.append('')

    if check['missing_must_report']:
        lines.append('### 缺失 must_report 数字\n')
        for m in check['missing_must_report']:
            lines.append(f'- {m}')
        lines.append('')

    if check['unmatched']:
        lines.append('### 疑似未匹配实证数字\n')
        lines.append('| 数字 | 上下文 |')
        lines.append('|---|---|')
        for u in check['unmatched']:
            lines.append(f"| {u['number']} | {u['context']} |")
        lines.append('')

    return '\n'.join(lines)


def load_references_used(paper_dir: str) -> str:
    """加载 references_used.md（如果存在）"""
    for subdir in ['.', '..', '04_writer/output']:
        path = os.path.join(paper_dir, subdir, 'references_used.md')
        if os.path.exists(path):
            return Path(path).read_text(encoding='utf-8')
    return ''


def verify(paper_dir: str, coder_output_dir: str, skip_word_count: bool = False) -> dict:
    """执行所有验证检查"""
    results = {
        'number_check': {'status': 'pass', 'issues': []},
        'cite_check': {'status': 'pass', 'issues': []},
        'file_check': {'status': 'pass', 'issues': []},
        'word_count': {'status': 'pass', 'count': 0, 'chinese': 0, 'english': 0, 'digits': 0, 'target': 8000},
    }

    # 加载论文
    paper_path = os.path.join(paper_dir, 'paper_final.tex')
    if not os.path.exists(paper_path):
        paper_path = os.path.join(paper_dir, 'paper_draft.tex')
    if not os.path.exists(paper_path):
        return {'error': f'找不到论文文件: {paper_dir}/paper_final.tex 或 paper_draft.tex'}

    paper_text = Path(paper_path).read_text(encoding='utf-8')
    results_summary = load_results_summary(coder_output_dir)

    # 1. 数字一致性检查
    numbers = extract_numbers_from_paper(paper_text)
    if results_summary:
        missing_stat = []      # 统计数字缺失 → block
        missing_structural = []  # 结构性数字缺失 → warn
        for num in numbers:
            num_clean = num.rstrip('%')
            # 精确匹配（word-boundary，避免 3 匹配 13）
            if re.search(r'(?<!\d)' + re.escape(num_clean) + r'(?!\d)', results_summary):
                continue
            # 模糊匹配（±0.01）
            try:
                val = float(num_clean)
                found = False
                for line in results_summary.split('\n'):
                    line_nums = re.findall(r'\d+\.?\d*', line)
                    for ln in line_nums:
                        try:
                            if abs(float(ln) - val) < 0.01:
                                found = True
                                break
                        except ValueError:
                            continue
                    if found:
                        break
                if found:
                    continue
            except ValueError:
                pass

            # 未匹配到 → 分类
            if _is_statistical_number(num):
                missing_stat.append(num)
            else:
                missing_structural.append(num)

        all_missing = missing_stat + missing_structural
        if all_missing:
            issues = all_missing[:10]
            if len(all_missing) > 10:
                issues.append(f'... 共 {len(all_missing)} 个')
            results['number_check']['issues'] = issues
            # 统计数字缺失 → block；仅有结构性数字缺失 → warn
            if missing_stat:
                results['number_check']['status'] = 'block'
            else:
                results['number_check']['status'] = 'warn'

    # 2. 引用一致性检查
    cite_keys = extract_cite_keys(paper_text)
    bibitem_keys = extract_bibitem_keys(paper_text)
    bibtex_keys = extract_bibtex_keys(paper_text, paper_dir)

    if cite_keys:
        # 确定参考文献来源
        if bibitem_keys:
            ref_keys = bibitem_keys
        elif bibtex_keys:
            ref_keys = bibtex_keys
        else:
            # 既无 thebibliography 也无 \bibliography{}，无法验证
            ref_keys = []

        if ref_keys:
            missing_refs = [k for k in cite_keys if k not in ref_keys]
            if missing_refs:
                results['cite_check']['issues'] = missing_refs
                results['cite_check']['status'] = 'block'
        else:
            # 无参考文献列表可验证
            results['cite_check']['issues'] = ['未找到 thebibliography 或 \\bibliography{}，无法验证引用']
            results['cite_check']['status'] = 'warn'

        # 交叉验证：bibitem key 是否在 references_used.md 中
        if bibitem_keys:
            refs_used = load_references_used(paper_dir)
            if refs_used:
                unverified = [k for k in bibitem_keys if k not in refs_used]
                if unverified:
                    results['cite_check']['issues'].extend(
                        [f'{k} (未在 references_used.md 中确认)' for k in unverified[:5]]
                    )
                    if results['cite_check']['status'] == 'pass':
                        results['cite_check']['status'] = 'warn'

    # 3. 文件引用检查
    table_inputs = extract_table_inputs(paper_text)
    figure_refs = extract_figure_refs(paper_text)

    # 构建搜索路径：paper_dir、paper_dir/..、coder_output_dir/tables/、coder_output_dir/figures/
    table_search_bases = [
        paper_dir,
        os.path.dirname(paper_dir),
        os.path.join(coder_output_dir, 'tables'),
    ]
    figure_search_bases = [
        paper_dir,
        os.path.dirname(paper_dir),
        os.path.join(coder_output_dir, 'figures'),
    ]

    missing_files = []
    for t in table_inputs:
        found = False
        for base in table_search_bases:
            full_path = os.path.join(base, t)
            if os.path.exists(full_path):
                found = True
                break
            if not full_path.endswith('.tex'):
                full_path += '.tex'
                if os.path.exists(full_path):
                    found = True
                    break
        if not found:
            missing_files.append(t)

    for f in figure_refs:
        found = False
        for base in figure_search_bases:
            full_path = os.path.join(base, f)
            if os.path.exists(full_path):
                found = True
                break
        if not found:
            missing_files.append(f)

    if missing_files:
        results['file_check']['issues'] = missing_files
        results['file_check']['status'] = 'block'

    # 4. 字数检查
    total, chinese, english, digits = count_paper_words(paper_text)
    results['word_count']['count'] = total
    results['word_count']['chinese'] = chinese
    results['word_count']['english'] = english
    results['word_count']['digits'] = digits
    if not skip_word_count:
        if total < 6000:  # 目标 8000 的 75%
            results['word_count']['status'] = 'block'
        elif total < 7200:  # 目标 8000 的 90%
            results['word_count']['status'] = 'warn'

    return results


def format_report(results: dict) -> str:
    """格式化验证报告"""
    if 'error' in results:
        return f"# 验证报告\n\n**错误**: {results['error']}\n"

    lines = ['# 验证报告\n']

    status_emoji = {'pass': '✅', 'warn': '⚠️', 'block': '❌'}

    # 总览
    lines.append('## 总览\n')
    for check_name, check_data in results.items():
        status = check_data.get('status', 'unknown')
        emoji = status_emoji.get(status, '?')
        label = {
            'number_check': '数字一致性',
            'cite_check': '引用一致性',
            'file_check': '文件引用',
            'word_count': '字数',
        }.get(check_name, check_name)
        lines.append(f'- {emoji} **{label}**: {status}')

    # 详细发现
    lines.append('\n## 详细发现\n')

    if results['number_check']['issues']:
        lines.append('### 数字一致性\n')
        lines.append('以下数字在 results_summary.md 中未找到来源：\n')
        for num in results['number_check']['issues']:
            lines.append(f'- {num}')
        lines.append('')

    if results['cite_check']['issues']:
        lines.append('### 引用一致性\n')
        lines.append('以下引用存在问题：\n')
        for key in results['cite_check']['issues']:
            lines.append(f'- `{key}`')
        lines.append('')

    if results['file_check']['issues']:
        lines.append('### 文件引用\n')
        lines.append('以下引用的文件不存在：\n')
        for f in results['file_check']['issues']:
            lines.append(f'- `{f}`')
        lines.append('')

    wc = results['word_count']
    lines.append('### 字数统计\n')
    lines.append(f'- 估算字数：{wc["count"]}')
    lines.append(f'  - 中文字符：{wc["chinese"]}')
    lines.append(f'  - 英文单词：{wc["english"]}')
    lines.append(f'  - 数字：{wc["digits"]}')
    lines.append(f'- 目标：{wc["target"]}')
    lines.append(f'- 状态：{wc["status"]}')
    lines.append('')

    return '\n'.join(lines)


# ==================== Markdown 模式 ====================

def extract_md_image_paths(md_text: str) -> list[str]:
    """提取 Markdown 中所有图片路径"""
    return re.findall(r'!\[.*?\]\(([^)]+)\)', md_text)


def extract_md_table_captions(md_text: str) -> list[str]:
    """提取 Markdown 中的表格标题（表1、表2...）"""
    return re.findall(r'表\s*(\d+)', md_text)


def extract_md_figure_captions(md_text: str) -> list[str]:
    """提取 Markdown 中的图标题（图1、图2...）"""
    return re.findall(r'图\s*(\d+)', md_text)


def verify_markdown(paper_path: str, results_summary: str, skip_word_count: bool = False) -> dict:
    """Markdown 格式验证"""
    results = {
        'format_check': {'status': 'pass', 'issues': []},
        'image_check': {'status': 'pass', 'issues': []},
        'numbering_check': {'status': 'pass', 'issues': []},
        'citation_check': {'status': 'pass', 'issues': []},
        'formula_check': {'status': 'pass', 'issues': []},
        'placeholder_check': {'status': 'pass', 'issues': []},
        'latex_residue_check': {'status': 'pass', 'issues': []},
        'number_check': {'status': 'pass', 'issues': []},
        'word_count': {'status': 'pass', 'count': 0, 'chinese': 0, 'english': 0, 'digits': 0, 'target': 8000},
    }

    if not os.path.exists(paper_path):
        return {'error': f'文件不存在: {paper_path}'}

    md_text = Path(paper_path).read_text(encoding='utf-8')
    md_dir = os.path.dirname(paper_path)

    # 1. 图片路径检查
    img_paths = extract_md_image_paths(md_text)
    missing_images = []
    for img in img_paths:
        full = os.path.join(md_dir, img) if not os.path.isabs(img) else img
        if not os.path.exists(full):
            missing_images.append(img)
    if missing_images:
        results['image_check']['issues'] = missing_images
        results['image_check']['status'] = 'block'

    # 2. 图表编号连续性
    table_nums = [int(n) for n in extract_md_table_captions(md_text)]
    figure_nums = [int(n) for n in extract_md_figure_captions(md_text)]
    for label, nums in [('表格', table_nums), ('图片', figure_nums)]:
        if nums:
            expected = list(range(1, max(nums) + 1))
            missing = sorted(set(expected) - set(nums))
            if missing:
                results['numbering_check']['issues'].append(f'{label}编号跳号: 缺{missing}')
                results['numbering_check']['status'] = 'warn'

    # 3. 引用编号检查
    cite_nums = extract_md_citation_numbers(md_text)
    if cite_nums:
        max_cite = max(cite_nums)
        expected = list(range(1, max_cite + 1))
        missing = sorted(set(expected) - set(cite_nums))
        if missing:
            results['citation_check']['issues'].append(f'引用编号不连续: 缺{missing}')
            results['citation_check']['status'] = 'warn'

    # 4. 公式语法检查 — 先移除公式区域再查裸露命令
    inline_formulas = re.findall(r'\$[^$]+?\$', md_text)
    block_formulas = re.findall(r'\$\$.*?\$\$', md_text, re.DOTALL)
    # 移除所有公式区域后检查裸露 LaTeX
    text_no_math = re.sub(r'\$\$.*?\$\$', '', md_text, flags=re.DOTALL)
    text_no_math = re.sub(r'(?<!\$)\$(?!\$).*?(?<!\$)\$(?!\$)', '', text_no_math, flags=re.DOTALL)
    bare_formulas = re.findall(
        r'\\(?:frac|alpha|beta|gamma|theta|lambda|varepsilon|epsilon|sum|int)\b',
        text_no_math
    )
    if bare_formulas:
        results['formula_check']['issues'] = [f'可能的未包裹 LaTeX 命令: {bare_formulas[:5]}']
        results['formula_check']['status'] = 'warn'

    # 5. 占位符检查
    placeholders = re.findall(r'(?:TODO|待补|{{table}}|{{figure}}|XXX|\[需补充\]|\[待确认\])', md_text)
    if placeholders:
        results['placeholder_check']['issues'] = [f'发现 {len(placeholders)} 个占位符']
        results['placeholder_check']['status'] = 'block'

    # 5.5 未闭合加粗检查
    for i, line in enumerate(md_text.split('\n'), 1):
        stripped = line.strip()
        # 跳过表格行和代码块
        if stripped.startswith('|') or stripped.startswith('```'):
            continue
        # 统计 ** 出现次数（排除代码块内）
        code_removed = re.sub(r'`[^`]+`', '', stripped)
        star_count = len(re.findall(r'\*\*', code_removed))
        if star_count % 2 != 0:
            results['format_check']['issues'].append(
                f'第 {i} 行 ** 出现 {star_count} 次（奇数，可能未闭合）: {stripped[:80]}'
            )
            results['format_check']['status'] = 'block'
        # 统计 __ 出现次数
        underscore_count = len(re.findall(r'__', code_removed))
        if underscore_count % 2 != 0:
            results['format_check']['issues'].append(
                f'第 {i} 行 __ 出现 {underscore_count} 次（奇数，可能未闭合）: {stripped[:80]}'
            )
            results['format_check']['status'] = 'block'

    # 6. LaTeX 残留检查
    latex_residue = re.findall(r'\\input\{[^}]*\}|\\includegraphics\{[^}]*\}|\\begin\{table\}|\\begin\{figure\}|\\end\{table\}|\\end\{figure\}', md_text)
    if latex_residue:
        results['latex_residue_check']['issues'] = [f'发现 LaTeX 环境残留: {latex_residue[:5]}']
        results['latex_residue_check']['status'] = 'block'

    # 7. 数字一致性（如果提供了 results_summary）
    if results_summary:
        numbers = extract_numbers_from_paper(md_text)
        missing_stat = []
        for num in numbers:
            num_clean = num.rstrip('%')
            if re.search(r'(?<!\d)' + re.escape(num_clean) + r'(?!\d)', results_summary):
                continue
            try:
                val = float(num_clean)
                found = False
                for line in results_summary.split('\n'):
                    line_nums = re.findall(r'\d+\.?\d*', line)
                    for ln in line_nums:
                        try:
                            if abs(float(ln) - val) < 0.01:
                                found = True
                                break
                        except ValueError:
                            continue
                    if found:
                        break
                if not found and _is_statistical_number(num):
                    missing_stat.append(num)
            except ValueError:
                pass
        if missing_stat:
            results['number_check']['issues'] = missing_stat[:10]
            results['number_check']['status'] = 'block' if len(missing_stat) > 3 else 'warn'

    # 8. 字数统计
    chinese = re.findall(r'[\u4e00-\u9fff]', md_text)
    english = re.findall(r'[a-zA-Z]+', md_text)
    digits = re.findall(r'\b\d+\.?\d*\b', md_text)
    total = len(chinese) + len(english) + len(digits)
    results['word_count']['count'] = total
    results['word_count']['chinese'] = len(chinese)
    results['word_count']['english'] = len(english)
    results['word_count']['digits'] = len(digits)
    if not skip_word_count:
        if total < 6000:
            results['word_count']['status'] = 'block'
        elif total < 7200:
            results['word_count']['status'] = 'warn'

    return results


def format_markdown_report(results: dict) -> str:
    """格式化 Markdown 验证报告"""
    if 'error' in results:
        return f"# Markdown 验证报告\n\n**错误**: {results['error']}\n"

    lines = ['# Markdown 验证报告\n']
    status_emoji = {'pass': '✅', 'warn': '⚠️', 'block': '❌'}

    label_map = {
        'format_check': '格式检查',
        'image_check': '图片路径',
        'numbering_check': '图表编号',
        'citation_check': '引用编号',
        'formula_check': '公式语法',
        'placeholder_check': '占位符',
        'latex_residue_check': 'LaTeX 残留',
        'number_check': '数字一致性',
        'word_count': '字数',
    }

    lines.append('## 总览\n')
    for key, data in results.items():
        status = data.get('status', 'unknown')
        emoji = status_emoji.get(status, '?')
        label = label_map.get(key, key)
        lines.append(f'- {emoji} **{label}**: {status}')

    lines.append('\n## 详细发现\n')
    for key, data in results.items():
        if data.get('issues'):
            label = label_map.get(key, key)
            lines.append(f'### {label}\n')
            for issue in data['issues']:
                lines.append(f'- {issue}')
            lines.append('')

    wc = results.get('word_count', {})
    if wc:
        lines.append('### 字数统计\n')
        lines.append(f'- 估算字数：{wc.get("count", 0)}')
        lines.append(f'- 目标：{wc.get("target", 8000)}')
        lines.append('')

    return '\n'.join(lines)


# ==================== DOCX 模式 ====================

def verify_docx(paper_path: str, results_summary: str, skip_word_count: bool = False) -> dict:
    """DOCX 格式验证"""
    results = {
        'number_check': {'status': 'pass', 'issues': []},
        'citation_check': {'status': 'pass', 'issues': []},
        'figure_table_check': {'status': 'pass', 'issues': []},
        'latex_residue_check': {'status': 'pass', 'issues': []},
        'formula_loss_check': {'status': 'pass', 'issues': []},
        'placeholder_check': {'status': 'pass', 'issues': []},
        'word_count': {'status': 'pass', 'count': 0, 'chinese': 0, 'english': 0, 'digits': 0, 'target': 8000},
    }

    if not os.path.exists(paper_path):
        return {'error': f'文件不存在: {paper_path}'}

    try:
        from docx import Document
    except ImportError:
        return {'error': 'python-docx 未安装，无法验证 docx 文件'}

    try:
        doc = Document(paper_path)
    except Exception as e:
        return {'error': f'无法打开 docx 文件: {e}'}

    # 提取全部文本
    full_text = '\n'.join([p.text for p in doc.paragraphs])

    # 1. 数字一致性
    if results_summary:
        numbers = re.findall(r'\b\d+\.?\d*%?\b', full_text)
        missing_stat = []
        for num in numbers:
            val_str = num.rstrip('%')
            try:
                val = float(val_str)
            except ValueError:
                continue
            if 1900 <= val <= 2099:
                continue
            if val == int(val) and 0 <= val <= 20:
                continue
            if re.search(r'(?<!\d)' + re.escape(val_str) + r'(?!\d)', results_summary):
                continue
            found = False
            for line in results_summary.split('\n'):
                for ln in re.findall(r'\d+\.?\d*', line):
                    try:
                        if abs(float(ln) - val) < 0.01:
                            found = True
                            break
                    except ValueError:
                        continue
                if found:
                    break
            if not found and ('.' in val_str or '%' in num):
                missing_stat.append(num)
        if missing_stat:
            results['number_check']['issues'] = missing_stat[:10]
            results['number_check']['status'] = 'block' if len(missing_stat) > 3 else 'warn'

    # 2. 引用编号
    cite_nums = extract_md_citation_numbers(full_text)
    if cite_nums:
        max_cite = max(cite_nums)
        missing = sorted(set(range(1, max_cite + 1)) - set(cite_nums))
        if missing:
            results['citation_check']['issues'].append(f'引用编号不连续: 缺{missing}')
            results['citation_check']['status'] = 'warn'

    # 3. 图表编号
    table_nums = [int(n) for n in re.findall(r'表\s*(\d+)', full_text)]
    figure_nums = [int(n) for n in re.findall(r'图\s*(\d+)', full_text)]
    for label, nums in [('表格', table_nums), ('图片', figure_nums)]:
        if nums:
            missing = sorted(set(range(1, max(nums) + 1)) - set(nums))
            if missing:
                results['figure_table_check']['issues'].append(f'{label}编号跳号: 缺{missing}')
                results['figure_table_check']['status'] = 'warn'

    # 4. LaTeX 残留
    latex_cmds = re.findall(r'\\(?:alpha|beta|varepsilon|sum|frac|theta|lambda|sqrt|int|prod)\b', full_text)
    if latex_cmds:
        results['latex_residue_check']['issues'] = [f'发现 {len(latex_cmds)} 处 LaTeX 命令残留']
        results['latex_residue_check']['status'] = 'block'

    # 5. 公式变量缺失句式
    loss_patterns = [
        r'设共有个', r'其中，为', r'若，说明',
        r'设共有\s*个决策单元', r'其中[，,]\s*为',
    ]
    loss_found = []
    for pat in loss_patterns:
        matches = re.findall(pat, full_text)
        loss_found.extend(matches)
    if loss_found:
        results['formula_loss_check']['issues'] = [f'发现公式变量缺失句式: {loss_found}']
        results['formula_loss_check']['status'] = 'block'

    # 6. 占位符
    placeholders = re.findall(r'(?:TODO|待补|XXX|\[需补充\]|\[待确认\])', full_text)
    if placeholders:
        results['placeholder_check']['issues'] = [f'发现 {len(placeholders)} 个占位符']
        results['placeholder_check']['status'] = 'block'

    # 7. 字数统计
    chinese = re.findall(r'[\u4e00-\u9fff]', full_text)
    english = re.findall(r'[a-zA-Z]+', full_text)
    digits = re.findall(r'\b\d+\.?\d*\b', full_text)
    total = len(chinese) + len(english) + len(digits)
    results['word_count']['count'] = total
    results['word_count']['chinese'] = len(chinese)
    results['word_count']['english'] = len(english)
    results['word_count']['digits'] = len(digits)
    if not skip_word_count:
        if total < 6000:
            results['word_count']['status'] = 'block'
        elif total < 7200:
            results['word_count']['status'] = 'warn'

    return results


def format_docx_report(results: dict) -> str:
    """格式化 DOCX 验证报告"""
    if 'error' in results:
        return f"# DOCX 验证报告\n\n**错误**: {results['error']}\n"

    lines = ['# DOCX 验证报告\n']
    status_emoji = {'pass': '✅', 'warn': '⚠️', 'block': '❌'}

    label_map = {
        'number_check': '数字一致性',
        'citation_check': '引用编号',
        'figure_table_check': '图表编号',
        'latex_residue_check': 'LaTeX 残留',
        'formula_loss_check': '公式变量缺失',
        'placeholder_check': '占位符',
        'word_count': '字数',
    }

    lines.append('## 总览\n')
    for key, data in results.items():
        status = data.get('status', 'unknown')
        emoji = status_emoji.get(status, '?')
        label = label_map.get(key, key)
        lines.append(f'- {emoji} **{label}**: {status}')

    lines.append('\n## 详细发现\n')
    for key, data in results.items():
        if data.get('issues'):
            label = label_map.get(key, key)
            lines.append(f'### {label}\n')
            for issue in data['issues']:
                lines.append(f'- {issue}')
            lines.append('')

    wc = results.get('word_count', {})
    if wc:
        lines.append('### 字数统计\n')
        lines.append(f'- 估算字数：{wc.get("count", 0)}')
        lines.append(f'- 目标：{wc.get("target", 8000)}')
        lines.append('')

    return '\n'.join(lines)


# ==================== main ====================

def main():
    import argparse

    parser = argparse.ArgumentParser(description='论文一致性验证脚本')
    # 旧接口兼容
    parser.add_argument('paper_dir', nargs='?', help='论文目录（旧接口）')
    parser.add_argument('coder_output_dir', nargs='?', help='代码输出目录（旧接口）')
    parser.add_argument('--output-dir', help='报告输出目录（旧接口）')
    # 新接口
    parser.add_argument('--paper', help='论文文件路径（.tex/.md/.docx）')
    parser.add_argument('--results', help='results_summary.md 路径')
    parser.add_argument('--results-json', help='results.json 路径（结构化数字真源）')
    parser.add_argument('--output', help='验证报告输出路径')
    parser.add_argument('--format', choices=['auto', 'latex', 'markdown', 'docx'], default='auto',
                        help='输入格式（默认 auto 自动检测）')
    parser.add_argument('--skip-word-count', action='store_true', default=False,
                        help='跳过字数门禁（字数不足时不 block/warn，仅报告字数）')

    args = parser.parse_args()

    # 判断使用新接口还是旧接口
    if args.paper:
        # 新接口
        paper_path = args.paper
        results_summary = ''
        if args.results and os.path.exists(args.results):
            results_summary = Path(args.results).read_text(encoding='utf-8')

        # 当提供 --results-json 时，results.json 是唯一 blocking 数字真源；
        # results_summary.md 不再作为数字一致性 blocker。
        if args.results_json:
            results_summary_for_number_check = ''
        else:
            results_summary_for_number_check = results_summary

        fmt = args.format
        if fmt == 'auto':
            if paper_path.endswith('.md'):
                fmt = 'markdown'
            elif paper_path.endswith('.docx'):
                fmt = 'docx'
            else:
                fmt = 'latex'

        if fmt == 'markdown':
            results = verify_markdown(paper_path, results_summary_for_number_check, skip_word_count=args.skip_word_count)
            report = format_markdown_report(results)
        elif fmt == 'docx':
            results = verify_docx(paper_path, results_summary_for_number_check, skip_word_count=args.skip_word_count)
            report = format_docx_report(results)
        else:
            # latex 模式：复用旧逻辑
            paper_dir = os.path.dirname(paper_path)
            coder_dir = os.path.dirname(args.results) if args.results else paper_dir
            # 向上找 coder output dir
            if not os.path.exists(os.path.join(coder_dir, 'results_summary.md')):
                # 尝试从 paper_workspace 结构推断
                pw_root = os.path.dirname(os.path.dirname(paper_dir))
                candidate = os.path.join(pw_root, '03_coder', 'output')
                if os.path.exists(candidate):
                    coder_dir = candidate
            results = verify(paper_dir, coder_dir, skip_word_count=args.skip_word_count)
            report = format_report(results)

        # 结构化数字检查（如果提供了 --results-json）
        if args.results_json:
            structured_check = verify_structured_numbers(args.results_json, paper_path)
            structured_report = format_structured_report(structured_check)
            report += '\n\n' + structured_report
            report += '\n\n> 已提供 results.json，数字一致性以 results.json 为准；results_summary.md 不作为 blocking 数字真源。\n'
            # 将结构化检查结果加入 results dict
            if isinstance(results, dict):
                results['structured_number_check'] = structured_check

        print(report)
        if args.output:
            output_dir = os.path.dirname(args.output)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f'\n报告已写入: {args.output}')
        else:
            # 默认写到同目录
            default_output = os.path.join(
                os.path.dirname(paper_path),
                f'{fmt}_consistency_report.md'
            )
            with open(default_output, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f'\n报告已写入: {default_output}')
    elif args.paper_dir and args.coder_output_dir:
        # 旧接口兼容
        paper_dir = args.paper_dir
        coder_output_dir = args.coder_output_dir
        output_dir = args.output_dir or paper_dir

        results = verify(paper_dir, coder_output_dir)
        report = format_report(results)
        print(report)

        output_path = os.path.join(output_dir, 'verification_report.md')
        os.makedirs(output_dir, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f'\n报告已写入: {output_path}')
    else:
        parser.print_help()
        sys.exit(1)

    # Unified exit code: 2 if any blocker, 0 otherwise
    if isinstance(results, dict) and 'error' in results:
        sys.exit(2)
    if isinstance(results, dict):
        for value in results.values():
            if isinstance(value, dict):
                status = str(value.get('status', '')).lower()
                if status in {'block', 'blocker', 'fail', 'error'}:
                    sys.exit(2)
    sys.exit(0)


if __name__ == '__main__':
    main()
