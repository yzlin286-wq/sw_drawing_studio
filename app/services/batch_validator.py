"""批量全量验证（Spec validate-real-drawings-with-llm-vision Task 4）

遍历 3D转2D测试图纸/*.SLDPRT，对每个执行 full_pipeline + vision_score_with_reference，
汇总到 drw_output/batch_validation/<batch_id>/。
"""
from __future__ import annotations
import json
import time
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CASE_DIR = REPO_ROOT / "3D转2D测试图纸"
BATCH_DIR = REPO_ROOT / "drw_output" / "batch_validation"


def _short_uuid() -> str:
    return uuid.uuid4().hex[:12]


def _collect_sldprt_files(limit: int | None = None) -> list[Path]:
    """收集所有 SLDPRT 文件（排除 ~$ 临时文件）"""
    files = sorted(CASE_DIR.glob("*.SLDPRT"))
    files = [f for f in files if not f.name.startswith("~$")]
    if limit and limit > 0:
        files = files[:limit]
    return files


def _classify_status(ctx) -> str:
    """根据 RunContext 判断状态: success / warning / failed"""
    if not isinstance(ctx.drawing_usable, dict):
        return "failed"
    if ctx.hard_fail:
        return "failed"
    if ctx.drawing_usable.get("pass"):
        return "success" if not ctx.warnings else "warning"
    return "failed"


def run_batch_validation(
    strategy: str = "v6_recommended",
    limit: int | None = None,
    skip_vision: bool = False,
) -> dict[str, Any]:
    """批量验证。

    Args:
        strategy: v6_recommended / v5_compat / v6_debug
        limit: 限制处理数量（用于小批量测试）；None 表示全量
        skip_vision: True 则跳过 LLM 视觉评分（加速）

    Returns:
        {batch_id, started_at, finished_at, total, success, warning, failed, items[]}
    """
    batch_id = _short_uuid()
    batch_dir = BATCH_DIR / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)

    started_at = time.strftime("%Y-%m-%d %H:%M:%S")
    sldprt_files = _collect_sldprt_files(limit)
    total = len(sldprt_files)

    items: list[dict] = []
    success = 0
    warning = 0
    failed = 0

    # LLM client（若 skip_vision 则不初始化）
    llm = None
    if not skip_vision:
        try:
            from app.services.llm_client import build_default_client
            llm = build_default_client()
        except Exception as e:
            print(f"[batch] LLM init failed: {e}")

    for i, sldprt in enumerate(sldprt_files, 1):
        base = sldprt.stem
        print(f"[batch] {i}/{total} processing: {base}")
        item: dict[str, Any] = {
            "base": base,
            "sldprt_path": str(sldprt),
            "run_id": None,
            "vision_score": None,
            "reference_diff": None,
            "hard_fail": [],
            "warnings": [],
            "drawing_usable": False,
            "qc_pass_count": 0,
            "status": "failed",
            "error": "",
        }

        try:
            # 1) full_pipeline
            from app.services.run_manager import full_pipeline
            ctx = full_pipeline(str(sldprt), strategy=strategy)
            item["run_id"] = ctx.run_id
            item["hard_fail"] = list(ctx.hard_fail or [])
            item["warnings"] = list(ctx.warnings or [])
            item["qc_pass_count"] = ctx.qc_pass_count
            if isinstance(ctx.drawing_usable, dict):
                item["drawing_usable"] = bool(ctx.drawing_usable.get("pass"))
            item["status"] = _classify_status(ctx)

            # 2) vision_score_with_reference（若 LLM 可用且不跳过）
            if llm is not None and not skip_vision:
                try:
                    from app.services.vision_qc import vision_score_with_reference
                    from app.services.case_library import find_case_png

                    # 找生成的 SLDDRW
                    slddrw_path = None
                    qc_json_path = None
                    for ext in [".SLDDRW"]:
                        # 优先从 run_dir 找
                        cand = ctx.run_dir / "drawing" / f"{base}_v5{ext}"
                        if cand.exists():
                            slddrw_path = str(cand)
                            break
                        # 兜底从 drw_output/v5 找
                        cand2 = REPO_ROOT / "drw_output" / "v5" / f"{base}_v5{ext}"
                        if cand2.exists():
                            slddrw_path = str(cand2)
                            break

                    # 找 qc.json
                    cand_qc = ctx.run_dir / "qc" / f"{base}_v5_qc.json"
                    if cand_qc.exists():
                        qc_json_path = str(cand_qc)
                    else:
                        cand_qc2 = REPO_ROOT / "drw_output" / "v5" / f"{base}_v5_qc.json"
                        if cand_qc2.exists():
                            qc_json_path = str(cand_qc2)

                    # 找案例图
                    ref_png = find_case_png(base)

                    if slddrw_path and qc_json_path:
                        v_result = vision_score_with_reference(
                            slddrw_path, qc_json_path, llm,
                            reference_png_path=ref_png,
                        )
                        item["vision_score"] = v_result.get("score")
                        item["reference_diff"] = v_result.get("reference_diff")
                        # 把 vision 结果写入 run_dir/qc/vision_ref.json
                        try:
                            vision_ref_path = ctx.run_dir / "qc" / "vision_ref.json"
                            vision_ref_path.write_text(
                                json.dumps(v_result, ensure_ascii=False, indent=2),
                                encoding="utf-8"
                            )
                        except Exception:
                            pass
                    else:
                        item["error"] = "SLDDRW or qc.json not found for vision"
                except Exception as e:
                    item["error"] = f"vision: {type(e).__name__}: {e}"

            # 计数
            if item["status"] == "success":
                success += 1
            elif item["status"] == "warning":
                warning += 1
            else:
                failed += 1

        except Exception as e:
            item["status"] = "failed"
            item["error"] = f"pipeline: {type(e).__name__}: {e}"
            failed += 1

        items.append(item)

        # 增量写 summary（防止中途崩溃丢失进度）
        _write_summary(batch_dir, batch_id, started_at, "", total, success, warning, failed, items)

    finished_at = time.strftime("%Y-%m-%d %H:%M:%S")
    result = _write_summary(batch_dir, batch_id, started_at, finished_at, total, success, warning, failed, items)
    return result


def _write_summary(
    batch_dir: Path, batch_id: str, started_at: str, finished_at: str,
    total: int, success: int, warning: int, failed: int, items: list,
) -> dict[str, Any]:
    """写 batch_summary.json"""
    summary = {
        "batch_id": batch_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "total": total,
        "success": success,
        "warning": warning,
        "failed": failed,
        "items": items,
    }
    summary_path = batch_dir / "batch_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def write_batch_report(batch_id: str) -> Path:
    """生成 batch_report.md（Task 5 实现，此处先占位）"""
    # Task 5 会实现完整报告
    batch_dir = BATCH_DIR / batch_id
    summary_path = batch_dir / "batch_summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"batch_summary.json not found for batch_id={batch_id}")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    report_path = batch_dir / "batch_report.md"

    total_n = summary.get("total", 0) or 0
    pass_n = summary.get("success", 0) + summary.get("warning", 0)
    pass_pct = f"{pass_n / total_n * 100:.1f}%" if total_n else "0.0%"
    lines = [
        f"# 批量验证报告 {batch_id}",
        "",
        f"- 开始: {summary.get('started_at')}",
        f"- 结束: {summary.get('finished_at')}",
        f"- 总数: {total_n}",
        f"- 成功: {summary.get('success')}",
        f"- 警告: {summary.get('warning')}",
        f"- 失败: {summary.get('failed')}",
        f"- 通过率: {pass_n}/{total_n} ({pass_pct})",
        "",
    ]

    # top 5 vision_score
    items_with_score = [it for it in summary.get("items", []) if it.get("vision_score") is not None]
    top5 = sorted(items_with_score, key=lambda x: x.get("vision_score", 0), reverse=True)[:5]
    lines.append("## Top 5 vision_score")
    if top5:
        for it in top5:
            lines.append(f"- {it['base']}: {it.get('vision_score')}/100 (status={it.get('status')})")
    else:
        lines.append("- （无 vision_score 数据）")
    lines.append("")

    # bottom 5 vision_score
    bottom5 = sorted(items_with_score, key=lambda x: x.get("vision_score", 0))[:5]
    lines.append("## Bottom 5 vision_score")
    if bottom5:
        for it in bottom5:
            lines.append(f"- {it['base']}: {it.get('vision_score')}/100 (status={it.get('status')})")
    else:
        lines.append("- （无 vision_score 数据）")
    lines.append("")

    # 失败清单
    failed_items = [it for it in summary.get("items", []) if it.get("status") == "failed"]
    lines.append("## 失败清单")
    if failed_items:
        for it in failed_items:
            hard_fail = it.get("hard_fail") or []
            err = it.get("error", "") or ""
            parts = []
            if hard_fail:
                parts.append(f"hard_fail=[{', '.join(hard_fail)}]")
            if err:
                parts.append(f"error={err[:120]}")
            detail = " ".join(parts) if parts else "（无详细原因）"
            lines.append(f"- {it['base']}: {detail}")
    else:
        lines.append("- （无失败项）")
    lines.append("")

    # 对标差异典型样例
    items_with_diff = [it for it in summary.get("items", []) if it.get("reference_diff")]
    lines.append("## 对标差异典型样例（前 3）")
    if items_with_diff:
        for it in items_with_diff[:3]:
            diff = it["reference_diff"]
            lines.append(f"### {it['base']}")
            lines.append(f"- similarity: {diff.get('similarity')}")
            lines.append(f"- structural_diff: {diff.get('structural_diff', '')[:200]}")
            missing = diff.get("missing_elements", [])
            if missing:
                lines.append(f"- missing_elements: {', '.join(str(m) for m in missing[:5])}")
            lines.append("")
    else:
        lines.append("- （无对标差异数据，可能案例图未匹配或 reference_diff 为 null）")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


if __name__ == "__main__":
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    result = run_batch_validation(strategy="v6_recommended", limit=limit)
    print(f"\n[batch] batch_id={result['batch_id']}")
    print(f"[batch] total={result['total']} success={result['success']} warning={result['warning']} failed={result['failed']}")
    report = write_batch_report(result["batch_id"])
    print(f"[batch] report: {report}")
