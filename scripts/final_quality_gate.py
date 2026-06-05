#!/usr/bin/env python3
"""
final_quality_gate.py — 最终质量门禁脚本

汇总所有前置检查报告，按统一分级规则给出最终结论。

结论只能是：PASS / PASS_WITH_MINOR / WARN / FAIL / INCOMPLETE

用法：
    python final_quality_gate.py --workspace paper_workspace --output paper_workspace/final_paper/final_gate_report.md
    python final_quality_gate.py --help
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path


# === Severity detection ===

_SEVERITY_PATTERNS = [
    ('BLOCKER', re.compile(r'\bBLOCKER\b|blocker|\bFAIL\b|fail|❌', re.IGNORECASE)),
    ('MAJOR', re.compile(r'\bMAJOR\b', re.IGNORECASE)),
    ('MINOR', re.compile(r'\bMINOR\b', re.IGNORECASE)),
    ('LIMITATION', re.compile(r'\bLIMITATION\b', re.IGNORECASE)),
    ('WARN', re.compile(r'\bWARN\b|\bWARNING\b|⚠️', re.IGNORECASE)),
    ('PASS', re.compile(r'\bPASS\b|✅', re.IGNORECASE)),
]

_SEVERITY_ORDER = {
    'BLOCKER': 0,
    'INCOMPLETE': 1,
    'MAJOR': 2,
    'WARN': 3,
    'MINOR': 4,
    'LIMITATION': 5,
    'PASS': 6,
}


def _detect_severity(text: str) -> str:
    """从文本中检测最高严重等级。"""
    best = 'PASS'
    best_rank = _SEVERITY_ORDER['PASS']
    for sev, pat in _SEVERITY_PATTERNS:
        if pat.search(text):
            rank = _SEVERITY_ORDER.get(sev, 99)
            if rank < best_rank:
                best = sev
                best_rank = rank
    return best


def _higher(a: str, b: str) -> str:
    """返回两者中更高的严重等级。"""
    return a if _SEVERITY_ORDER.get(a, 99) <= _SEVERITY_ORDER.get(b, 99) else b


# === Report collection ===

def _collect_reports(workspace: str, output_format: str) -> list[dict]:
    """收集所有前置检查报告。"""
    base = workspace.rstrip('/')
    reports = []

    def _add(name: str, path: str, required: bool, applicable: bool = True):
        reports.append({
            'name': name,
            'path': path,
            'required': required,
            'applicable': applicable,
        })

    # Method fit check
    _add(
        'Method Fit Check',
        f'{base}/02_modeler/output/method_fit_check.md',
        required=True,
    )

    # Structured results
    _add(
        'Structured Results (results.json)',
        f'{base}/03_coder/output/results.json',
        required=True,
    )

    # Markdown consistency report (always applicable)
    _add(
        'Markdown Consistency',
        f'{base}/final_paper/markdown_consistency_report.md',
        required=True,
    )

    # Word-specific reports
    if output_format == 'docx':
        _add(
            'DOCX Validation',
            f'{base}/final_paper/docx_validation_report.md',
            required=True,
        )
        _add(
            'DOCX Consistency',
            f'{base}/final_paper/docx_consistency_report.md',
            required=True,
        )
        _add(
            'DOCX Build Log',
            f'{base}/final_paper/docx_build_log.md',
            required=False,
        )
    else:
        # LaTeX compile log
        _add(
            'LaTeX Compile Log',
            f'{base}/final_paper/compile_log.txt',
            required=False,
        )

    # quality_check.md from reviewer
    _add(
        'Reviewer quality_check.md',
        f'{base}/final_paper/quality_check.md',
        required=False,
    )

    return reports


def _check_results_json(path: str) -> str:
    """专门检查 results.json 是否有效。"""
    if not os.path.exists(path):
        return 'BLOCKER'
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        rv = data.get('reportable_values', [])
        if not rv:
            return 'BLOCKER'
        return 'PASS'
    except (json.JSONDecodeError, OSError):
        return 'BLOCKER'


def _check_method_fit(path: str) -> str:
    """专门检查 method_fit_check.md 的 Stage 2 判定。"""
    if not os.path.exists(path):
        return 'INCOMPLETE'
    text = Path(path).read_text(encoding='utf-8', errors='ignore')
    # Look for Stage 2 判定 line
    m = re.search(r'Stage\s*2\s*判定.*?(PASS|WARN|BLOCKER)', text, re.IGNORECASE | re.DOTALL)
    if m:
        verdict = m.group(1).upper()
        if verdict == 'BLOCKER':
            return 'BLOCKER'
        return 'PASS'
    # Fallback: general severity detection
    return _detect_severity(text)


def run_gate(workspace: str, output_format: str) -> dict:
    """执行门禁检查。"""
    reports = _collect_reports(workspace, output_format)

    overall = 'PASS'
    blockers = []
    majors = []
    minors = []
    limitations = []
    source_rows = []

    for r in reports:
        if not r['applicable']:
            continue

        path = r['path']
        exists = os.path.exists(path)

        if not exists:
            if r['required']:
                detected = 'INCOMPLETE'
                overall = _higher(overall, 'INCOMPLETE')
                source_rows.append({
                    'name': r['name'],
                    'exists': False,
                    'severity': 'INCOMPLETE',
                    'note': '必要报告缺失',
                })
            else:
                source_rows.append({
                    'name': r['name'],
                    'exists': False,
                    'severity': 'SKIP',
                    'note': '非必要，跳过',
                })
            continue

        # Special handling for structured files
        if 'results.json' in r['name'].lower():
            detected = _check_results_json(path)
        elif 'method fit' in r['name'].lower():
            detected = _check_method_fit(path)
        else:
            text = Path(path).read_text(encoding='utf-8', errors='ignore')
            detected = _detect_severity(text)

        overall = _higher(overall, detected)

        note = ''
        if detected == 'BLOCKER':
            blockers.append(f"{r['name']}: {path}")
            note = '存在 BLOCKER/FAIL'
        elif detected == 'MAJOR':
            majors.append(f"{r['name']}: {path}")
            note = '存在 MAJOR'
        elif detected == 'MINOR':
            minors.append(f"{r['name']}: {path}")
            note = '存在 MINOR'
        elif detected == 'LIMITATION':
            limitations.append(f"{r['name']}: {path}")
            note = '存在 LIMITATION'
        else:
            note = '通过'

        source_rows.append({
            'name': r['name'],
            'exists': True,
            'severity': detected,
            'note': note,
        })

    # Final verdict mapping
    if _SEVERITY_ORDER.get(overall, 99) <= _SEVERITY_ORDER['BLOCKER']:
        verdict = 'FAIL'
    elif overall == 'INCOMPLETE':
        verdict = 'INCOMPLETE'
    elif overall == 'MAJOR':
        verdict = 'WARN'
    elif overall == 'WARN':
        verdict = 'WARN'
    elif overall == 'MINOR':
        verdict = 'PASS_WITH_MINOR'
    elif overall == 'LIMITATION':
        verdict = 'PASS_WITH_MINOR'
    else:
        verdict = 'PASS'

    return {
        'verdict': verdict,
        'source_rows': source_rows,
        'blockers': blockers,
        'majors': majors,
        'minors': minors,
        'limitations': limitations,
    }


def format_report(result: dict) -> str:
    """格式化门禁报告。"""
    lines = ['# Final Quality Gate Report\n']
    lines.append(f'## Final Verdict\n\n{result["verdict"]}\n')

    lines.append('## Source Reports\n')
    lines.append('| Report | Exists | Detected Severity | Notes |')
    lines.append('|---|---|---|---|')
    for row in result['source_rows']:
        lines.append(
            f"| {row['name']} | {'Yes' if row['exists'] else 'No'} "
            f"| {row['severity']} | {row['note']} |"
        )
    lines.append('')

    if result['blockers']:
        lines.append('## BLOCKER\n')
        for b in result['blockers']:
            lines.append(f'- {b}')
        lines.append('')

    if result['majors']:
        lines.append('## MAJOR\n')
        for m in result['majors']:
            lines.append(f'- {m}')
        lines.append('')

    if result['minors']:
        lines.append('## MINOR\n')
        for m in result['minors']:
            lines.append(f'- {m}')
        lines.append('')

    if result['limitations']:
        lines.append('## LIMITATION\n')
        for l in result['limitations']:
            lines.append(f'- {l}')
        lines.append('')

    if result['verdict'] != 'PASS':
        lines.append('## Required Fixes Before PASS\n')
        for b in result['blockers']:
            lines.append(f'- [BLOCKER] {b}')
        for m in result['majors']:
            lines.append(f'- [MAJOR] {m}')
        lines.append('')

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='最终质量门禁脚本')
    parser.add_argument('--workspace', required=True, help='paper_workspace 目录路径')
    parser.add_argument('--output', required=True, help='门禁报告输出路径')
    parser.add_argument('--format', choices=['latex', 'docx'], default='latex',
                        help='输出格式（决定检查哪些报告）')
    parser.add_argument('--allow-warn', action='store_true', default=False,
                        help='允许 WARN 判定通过（exit 0）。默认 WARN 视为不通过（exit 2）')
    args = parser.parse_args()

    # Try to detect output_format from manifest
    output_format = args.format
    manifest_path = os.path.join(args.workspace, '00_intake/output/manifest.json')
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            mf = manifest.get('output_format', '')
            if mf in ('latex', 'docx'):
                output_format = mf
        except (json.JSONDecodeError, OSError):
            pass

    result = run_gate(args.workspace, output_format)
    report = format_report(result)

    # Write report
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(report)

    print(report)
    print(f'\n报告已写入: {args.output}')

    # Exit code
    # FAIL/INCOMPLETE: always exit 2
    # WARN: exit 2 unless --allow-warn
    # PASS/PASS_WITH_MINOR: exit 0
    if result['verdict'] in ('FAIL', 'INCOMPLETE'):
        sys.exit(2)
    if result['verdict'] == 'WARN' and not args.allow_warn:
        sys.exit(2)
    sys.exit(0)


if __name__ == '__main__':
    main()
