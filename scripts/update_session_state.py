#!/usr/bin/env python3
"""
update_session_state.py — 更新 session_state.md

将流水线状态覆盖写入 <workspace>/session_state.md，内容不超过 200 tokens。

用法：
    python scripts/update_session_state.py \
      --workspace paper_workspace/<run_id> \
      --completed-stage 3 \
      --next-stage "Stage 4 writer_agent" \
      --checkpoint "<workspace>/03_coder/output/user_confirmed.flag" \
      --output "<workspace>/03_coder/output/results_summary.md" \
      --output "<workspace>/03_coder/output/analysis.py" \
      --format docx \
      --note "用户已确认核心结果"

不读取论文全文，不调用 LLM。
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


def _resolve_paper_workspace():
    """找到 paper_workspace 下的唯一 run_id 目录（兼容旧接口）。"""
    cwd = Path.cwd()
    for p in [cwd, *cwd.parents]:
        candidate = p / "paper_workspace"
        if candidate.is_dir():
            subdirs = [d for d in candidate.iterdir() if d.is_dir()
                       and not d.name.startswith('.') and d.name != '__pycache__']
            if len(subdirs) == 1:
                return subdirs[0]
            elif len(subdirs) > 1:
                return None
            if (candidate / "00_intake").is_dir():
                return candidate
    return None


def _mark(path: str) -> str:
    """检查路径是否存在，返回 ✓ 或 ✗。"""
    if os.path.exists(path):
        return f"{path} ✓"
    return f"{path} ✗"


# 每个 Stage 完成后，下一阶段应读取的最小上下文（与 routing_map.md 一致）
_NEXT_READS = {
    0: [  # Stage 0 完成 → Stage 1 audit_agent
        "agents/audit_agent.md",
        "<workspace>/00_intake/output/manifest.json",
        "<workspace>/00_intake/output/framework.md",
    ],
    1: [  # Stage 1 完成 → Stage 2 modeler_agent
        "agents/modeler_agent.md",
        "references/model_selection_tree.md",
        "references/method_guardrails.md",
        "<workspace>/00_intake/output/framework.md",
        "<workspace>/01_audit/output/data_audit.md",
        "<workspace>/01_audit/output/variable_map.json",
    ],
    2: [  # Stage 2 完成 → Stage 3 coder_agent
        "agents/coder_agent.md",
        "references/results_schema.md",
        "<workspace>/00_intake/output/manifest.json",
        "<workspace>/01_audit/output/variable_map.json",
        "<workspace>/02_modeler/output/model_plan.md",
        "<workspace>/02_modeler/output/实证设计.md",
        "<workspace>/02_modeler/output/method_fit_check.md",
    ],
    3: [  # Stage 3 完成 → Stage 4 writer_agent
        "agents/writer_agent.md",
        "references/writing_standards.md",
        "references/ai_patterns_zh.md",
        "references/results_schema.md",
        "<workspace>/00_intake/output/framework.md",
        "<workspace>/02_modeler/output/实证设计.md",
        "<workspace>/02_modeler/output/method_fit_check.md",
        "<workspace>/03_coder/output/results.json",
        "<workspace>/03_coder/output/results_summary.md",
        "<workspace>/03_coder/output/assets_manifest.json",
    ],
    4: [  # Stage 4 完成 → Stage 5 reviewer_agent
        "agents/reviewer_agent.md",
        "references/review_rubric.md",
        "references/results_schema.md",
        "references/failure_modes.md",
        "<workspace>/03_coder/output/results.json",
        "<workspace>/03_coder/output/assets_manifest.json",
        "<workspace>/04_writer/output/paper_draft.md",
    ],
    5: [  # Stage 5 完成 → Stage 6 expert_reviewer_agent
        "agents/expert_reviewer_agent.md",
        "references/independent_review_rubric.md",
        "references/ai_patterns_zh.md",
    ],
}


def _required_next_reads(completed_stage: int, ws: Path, fmt: str) -> list[str]:
    """返回下一阶段建议读取的文件列表，附带存在性标记。"""
    reads = _NEXT_READS.get(completed_stage, [])
    result = ["references/routing_map.md"]  # 始终包含路由表
    for r in reads:
        # 将 <workspace> 占位符替换为实际路径
        resolved = r.replace("<workspace>", str(ws))
        if r.startswith("<workspace>"):
            result.append(_mark(resolved))
        else:
            # agent/reference 文件相对于 skill 根目录，不做存在性检查
            result.append(r)
    # 格式相关的额外读取
    if completed_stage == 3:
        if fmt == "latex":
            result.append("references/latex_formatting.md")
        # docx 时不额外读取 latex_formatting.md
    if completed_stage == 4:
        if fmt == "docx":
            result.append("references/word_format_rules.md")
    return result


def main():
    parser = argparse.ArgumentParser(description="更新 session_state.md")
    parser.add_argument("--workspace", type=str, help="workspace 目录路径（paper_workspace/<run_id>）")
    parser.add_argument("--completed-stage", type=int, required=True, help="已完成的 Stage 编号")
    parser.add_argument("--next-stage", type=str, required=True, help="下一阶段描述")
    parser.add_argument("--checkpoint", type=str, required=True, help="最后 checkpoint 路径")
    parser.add_argument("--output", type=str, action="append", default=[], help="关键输出路径（可多次指定）")
    parser.add_argument("--format", type=str, default="latex", choices=["latex", "docx"], help="输出格式")
    parser.add_argument("--note", type=str, default="无", help="备注")
    args = parser.parse_args()

    # 确定 workspace
    if args.workspace:
        ws = Path(args.workspace)
        if not ws.is_dir():
            ws.mkdir(parents=True, exist_ok=True)
    else:
        ws = _resolve_paper_workspace()
        if ws is None:
            logger.error("未找到 workspace 目录，请使用 --workspace 指定")
            sys.exit(1)

    # 构建 session_state 内容
    lines = [
        f"当前阶段: Stage {args.completed_stage} 已完成",
        f"下一阶段: {args.next_stage}",
        f"最后 checkpoint: {_mark(args.checkpoint)}",
        "关键输出:",
    ]
    for out_path in args.output:
        lines.append(f"- {_mark(out_path)}")
    lines.append(f"输出格式: {args.format}")
    # 下一阶段建议读取
    next_reads = _required_next_reads(args.completed_stage, ws, args.format)
    if next_reads:
        lines.append("下一阶段建议读取:")
        for nr in next_reads:
            lines.append(f"- {nr}")
    lines.append(f"备注: {args.note}")
    lines.append(f"更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    content = "\n".join(lines) + "\n"

    state_path = ws / "session_state.md"
    state_path.write_text(content, encoding="utf-8")
    print(f"已更新: {state_path}")
    print(content)


if __name__ == "__main__":
    main()
