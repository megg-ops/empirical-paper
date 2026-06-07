#!/usr/bin/env python3
"""
stage_guard.py — Stage 入口 self-check 脚本

只做检查，不做业务逻辑。不读取大 markdown 文件，不调用 LLM，不修改任何文件。

用法：
    python scripts/stage_guard.py --workspace paper_workspace/<run_id> --stage 3
    python scripts/stage_guard.py --workspace paper_workspace/<run_id> --stage 4
    python scripts/stage_guard.py --workspace paper_workspace/<run_id> --infer
    python scripts/stage_guard.py --stage 3  （兼容旧接口，自动查找 workspace）

输出：
    成功 → exit code 0，打印 PASS + 检查详情
    失败 → exit code 1，打印 FAIL + 缺失项
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _resolve_paper_workspace():
    """找到 paper_workspace 下的唯一 run_id 目录（兼容旧接口）。"""
    cwd = Path.cwd()
    for p in [cwd, *cwd.parents]:
        candidate = p / "paper_workspace"
        if candidate.is_dir():
            # 查找子目录中的 run_id workspace
            subdirs = [d for d in candidate.iterdir() if d.is_dir()
                       and not d.name.startswith('.') and d.name != '__pycache__']
            if len(subdirs) == 1:
                return subdirs[0]
            elif len(subdirs) > 1:
                # 多个 workspace，无法自动选择
                return None
            # 无子目录，可能是旧式 paper_workspace 直接结构
            if (candidate / "00_intake").is_dir():
                return candidate
    return None


def _file_ok(path: str) -> bool:
    return os.path.exists(path)


def _dir_ok(path: str) -> bool:
    return os.path.isdir(path) and bool(os.listdir(path))


def _read_manifest(ws: Path):
    """读取 manifest.json，返回 data_file 路径和 output_format。"""
    manifest_path = ws / "00_intake" / "output" / "manifest.json"
    if not manifest_path.exists():
        return None, None
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("data_file"), data.get("output_format", "latex")
    except (json.JSONDecodeError, KeyError):
        return None, None


def _has_figures(ws: Path) -> bool:
    """检查 assets_manifest.json 是否声明了图片。"""
    assets_path = ws / "03_coder" / "output" / "assets_manifest.json"
    if not assets_path.exists():
        return False
    try:
        with open(assets_path, "r", encoding="utf-8") as f:
            am = json.load(f)
        return bool(am.get("figures"))
    except (json.JSONDecodeError, OSError):
        return False


STAGE_NAMES = {
    0: "材料识别",
    1: "数据审计",
    2: "研究设计",
    3: "代码分析",
    4: "论文写作",
    5: "质量审查",
    6: "独立专家审稿",
}

STAGE_AGENTS = {
    0: None,
    1: "audit_agent",
    2: "modeler_agent",
    3: "coder_agent",
    4: "writer_agent",
    5: "reviewer_agent",
    6: "expert_reviewer_agent",
}


def check_stage(stage: int, ws: Path) -> dict:
    """检查指定 Stage 的前置条件。返回 dict: ok, checked, missing, details。"""
    missing = []
    checked = []
    details = []

    data_file, output_format = _read_manifest(ws)

    if stage == 0:
        # Stage 0: 只检查是否有材料
        intake_input = ws / "00_intake" / "input"
        has_material = intake_input.is_dir() and bool(list(intake_input.iterdir()))
        # 或者项目根目录有文件
        if not has_material:
            # 也接受根目录有文件的情况（通过 manifest 判断）
            has_material = (ws / "00_intake" / "output" / "manifest.json").exists()
        checked.append("用户材料或 input 目录")
        if not has_material:
            missing.append("未找到用户材料，需确认项目目录")
        else:
            details.append("用户材料: OK")

    elif stage == 1:
        # 需要 manifest + framework + data
        items = [
            (str(ws / "00_intake" / "output" / "manifest.json"), "file", "manifest.json"),
            (str(ws / "00_intake" / "output" / "framework.md"), "file", "framework.md"),
        ]
        for path, kind, label in items:
            checked.append(label)
            if kind == "file" and not _file_ok(path):
                missing.append(path)
            elif kind == "file":
                details.append(f"{label}: OK")
        # data file from manifest (mandatory)
        if data_file:
            checked.append("数据文件")
            if not _file_ok(data_file):
                missing.append(data_file)
            else:
                details.append(f"数据文件: OK")
        else:
            checked.append("数据文件")
            missing.append("manifest.json:data_file (数据文件为必填项)")
            details.append("数据文件: manifest.json 中缺少 data_file")

    elif stage == 2:
        items = [
            (str(ws / "01_audit" / "output" / "data_audit.md"), "file", "data_audit.md"),
            (str(ws / "01_audit" / "output" / "variable_map.json"), "file", "variable_map.json"),
            (str(ws / "00_intake" / "output" / "framework.md"), "file", "framework.md"),
        ]
        for path, kind, label in items:
            checked.append(label)
            if not _file_ok(path):
                missing.append(path)
            else:
                details.append(f"{label}: OK")

    elif stage == 3:
        # 需要 Stage 2 的 user_confirmed.flag
        flag = str(ws / "02_modeler" / "output" / "user_confirmed.flag")
        checked.append("user_confirmed.flag")
        if not _file_ok(flag):
            missing.append(flag)
        else:
            details.append("user_confirmed.flag: OK")

        items = [
            (str(ws / "02_modeler" / "output" / "model_plan.md"), "file", "model_plan.md"),
            (str(ws / "02_modeler" / "output" / "实证设计.md"), "file", "实证设计.md"),
            (str(ws / "01_audit" / "output" / "variable_map.json"), "file", "variable_map.json"),
        ]
        for path, kind, label in items:
            checked.append(label)
            if not _file_ok(path):
                missing.append(path)
            else:
                details.append(f"{label}: OK")
        if data_file:
            checked.append("数据文件")
            if not _file_ok(data_file):
                missing.append(data_file)
            else:
                details.append("数据文件: OK")

    elif stage == 4:
        # 需要 Stage 3 的 user_confirmed.flag
        flag = str(ws / "03_coder" / "output" / "user_confirmed.flag")
        checked.append("user_confirmed.flag")
        if not _file_ok(flag):
            missing.append(flag)
        else:
            details.append("user_confirmed.flag: OK")

        items = [
            (str(ws / "03_coder" / "output" / "results_summary.md"), "file", "results_summary.md"),
            (str(ws / "03_coder" / "output" / "analysis.py"), "file", "analysis.py"),
            (str(ws / "03_coder" / "output" / "tables"), "dir", "tables/"),
            (str(ws / "02_modeler" / "output" / "实证设计.md"), "file", "实证设计.md"),
            (str(ws / "00_intake" / "output" / "framework.md"), "file", "framework.md"),
            (str(ws / "03_coder" / "output" / "results.json"), "file", "results.json"),
            (str(ws / "03_coder" / "output" / "assets_manifest.json"), "file", "assets_manifest.json"),
            (str(ws / "02_modeler" / "output" / "method_fit_check.md"), "file", "method_fit_check.md"),
        ]
        for path, kind, label in items:
            checked.append(label)
            if kind == "dir" and not _dir_ok(path):
                missing.append(path)
            elif kind == "file" and not _file_ok(path):
                missing.append(path)
            else:
                details.append(f"{label}: OK")

        # figures/ 只在 assets_manifest 声明有图时才要求
        if _has_figures(ws):
            figures_path = str(ws / "03_coder" / "output" / "figures")
            checked.append("figures/ (assets_manifest 声明有图)")
            if not _dir_ok(figures_path):
                missing.append(figures_path)
            else:
                details.append("figures/: OK")
        else:
            details.append("figures/: 无图论文，跳过检查")

    elif stage == 5:
        # 需要 Stage 4 的 user_confirmed.flag
        flag = str(ws / "04_writer" / "output" / "user_confirmed.flag")
        checked.append("user_confirmed.flag")
        if not _file_ok(flag):
            missing.append(flag)
        else:
            details.append("user_confirmed.flag: OK")

        # paper_draft: 至少一种存在
        draft_found = False
        for name in ["paper_draft.tex", "paper_draft.docx", "paper_draft.md"]:
            p = str(ws / "04_writer" / "output" / name)
            if _file_ok(p):
                draft_found = True
                details.append(f"{name}: OK")
                break
        checked.append("paper_draft.*")
        if not draft_found:
            missing.append("<workspace>/04_writer/output/paper_draft.{tex|docx|md}")

        items = [
            (str(ws / "03_coder" / "output" / "results_summary.md"), "file", "results_summary.md"),
            (str(ws / "03_coder" / "output" / "analysis.py"), "file", "analysis.py"),
            (str(ws / "03_coder" / "output" / "tables"), "dir", "tables/"),
            (str(ws / "03_coder" / "output" / "results.json"), "file", "results.json"),
            (str(ws / "03_coder" / "output" / "assets_manifest.json"), "file", "assets_manifest.json"),
            (str(ws / "02_modeler" / "output" / "method_fit_check.md"), "file", "method_fit_check.md"),
            (str(ws / "02_modeler" / "output" / "model_plan.md"), "file", "model_plan.md"),
        ]
        for path, kind, label in items:
            checked.append(label)
            if kind == "dir" and not _dir_ok(path):
                missing.append(path)
            elif kind == "file" and not _file_ok(path):
                missing.append(path)
            else:
                details.append(f"{label}: OK")

        # figures/ 只在 assets_manifest 声明有图时才要求
        if _has_figures(ws):
            figures_path = str(ws / "03_coder" / "output" / "figures")
            checked.append("figures/ (assets_manifest 声明有图)")
            if not _dir_ok(figures_path):
                missing.append(figures_path)
            else:
                details.append("figures/: OK")
        else:
            details.append("figures/: 无图论文，跳过检查")

        # word_count_report.json 检查
        wcr_path = ws / "04_writer" / "output" / "word_count_report.json"
        checked.append("word_count_report.json")
        if _file_ok(str(wcr_path)):
            details.append("word_count_report.json: OK")
            try:
                with open(wcr_path, "r", encoding="utf-8") as f:
                    wcr = json.load(f)
                if wcr.get("status") == "SHORT":
                    # 字数不足时必须有用户决策文件
                    decision_path = ws / "04_writer" / "output" / "user_wordcount_decision.json"
                    checked.append("user_wordcount_decision.json (SHORT 时必须)")
                    if not _file_ok(str(decision_path)):
                        missing.append(str(decision_path))
                    else:
                        details.append("user_wordcount_decision.json: OK")
            except (json.JSONDecodeError, OSError):
                missing.append(f"{wcr_path} parse_error")
                details.append("word_count_report.json: 解析失败，Stage 5 不得继续")
        else:
            missing.append(str(wcr_path))

    elif stage == 6:
        # 需要 final paper
        final_found = False
        for name in ["paper_final.tex", "paper_final.docx"]:
            p = str(ws / "final_paper" / name)
            if _file_ok(p):
                final_found = True
                details.append(f"{name}: OK")
                break
        checked.append("paper_final.*")
        if not final_found:
            missing.append("<workspace>/final_paper/paper_final.{tex|docx}")

        # reference files
        skill_dir = Path(__file__).resolve().parent.parent
        refs = [
            "references/independent_review_rubric.md",
            "references/ai_patterns_zh.md",
            "references/writing_standards.md",
        ]
        for ref in refs:
            p = str(skill_dir / ref)
            checked.append(ref)
            if not _file_ok(p):
                missing.append(p)
            else:
                details.append(f"{ref}: OK")

    return {
        "ok": len(missing) == 0,
        "checked": len(checked),
        "missing": missing,
        "details": details,
    }


def infer_stage(ws: Path) -> int:
    """从 session_state.md 或 flag 文件推断当前应执行的 Stage。"""
    # 先读 session_state
    state_path = ws / "session_state.md"
    if state_path.exists():
        try:
            content = state_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                if line.startswith("下一阶段:"):
                    text = line.split(":", 1)[1].strip()
                    # 解析 "Stage X agent_name"
                    if text.startswith("Stage "):
                        try:
                            return int(text.split()[1])
                        except (IndexError, ValueError):
                            pass
        except Exception:
            pass

    # fallback: 按 flag 文件推断
    flags = [
        ws / "04_writer" / "output" / "user_confirmed.flag",
        ws / "03_coder" / "output" / "user_confirmed.flag",
        ws / "02_modeler" / "output" / "user_confirmed.flag",
    ]
    for i, flag in enumerate(flags):
        if not flag.exists():
            # Stage 2/3/4 中第一个没 flag 的就是当前 Stage
            return [2, 3, 4][i]

    # 所有 flag 都存在
    if (ws / "final_paper" / "paper_final.tex").exists() or \
       (ws / "final_paper" / "paper_final.docx").exists():
        return 6  # 可启动专家审稿
    return 5  # 质量审查


def format_output(stage: int, result: dict, mode: str):
    """格式化输出。"""
    if result["ok"]:
        print("PASS")
        print(f"current_stage={stage}")
        agent = STAGE_AGENTS.get(stage)
        next_action = f"run_{agent}" if agent else "start_orchestrator"
        print(f"next_action={next_action}")
        print(f"inputs_checked={result['checked']}")
        print(f"missing=0")
        for d in result["details"]:
            print(f"  {d}")
    else:
        print("FAIL")
        print(f"current_stage={stage}")
        reason = "missing_flag" if any("flag" in m for m in result["missing"]) else "missing_input"
        print(f"reason={reason}")
        for m in result["missing"]:
            print(f"missing={m}")
        print(f"next_action=stop_and_ask_user")


def main():
    parser = argparse.ArgumentParser(description="Stage 入口 self-check")
    parser.add_argument("--workspace", type=str, help="workspace 目录路径（paper_workspace/<run_id>）")
    parser.add_argument("--stage", type=int, choices=range(0, 7), help="检查指定 Stage")
    parser.add_argument("--infer", action="store_true", help="自动推断当前 Stage")
    args = parser.parse_args()

    # 确定 workspace
    if args.workspace:
        ws = Path(args.workspace)
        if not ws.is_dir():
            print("FAIL")
            print(f"reason=workspace_not_found")
            print(f"missing={args.workspace}")
            print("next_action=stop_and_ask_user")
            sys.exit(1)
    else:
        ws = _resolve_paper_workspace()
        if ws is None:
            print("FAIL")
            print("reason=no_workspace_found")
            print("missing=paper_workspace/<run_id>/")
            print("hint=use --workspace paper_workspace/<run_id>")
            print("next_action=stop_and_ask_user")
            sys.exit(1)

    if args.infer:
        stage = infer_stage(ws)
        print(f"inferred_stage={stage}")
        print(f"stage_name={STAGE_NAMES.get(stage, 'unknown')}")
        result = check_stage(stage, ws)
        format_output(stage, result, "infer")
        sys.exit(0 if result["ok"] else 1)
    elif args.stage is not None:
        result = check_stage(args.stage, ws)
        format_output(args.stage, result, "explicit")
        sys.exit(0 if result["ok"] else 1)
    else:
        print("用法: python stage_guard.py --workspace <path> --stage N 或 --infer")
        sys.exit(2)


if __name__ == "__main__":
    main()
