"""统一运行会话管理（Spec enhance-v1-1 Task 1）

提供 RunContext + new_run() + write_manifest()，把所有产物归集到
drw_output/runs/<run_id>/{input,drawing,qc,bom,quote,logs}/
"""
from __future__ import annotations
import json
import os
import shutil
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from app.services.resource_paths import (
    bundle_root,
    child_process_env,
    pipeline_command,
    pipeline_script_path,
    runtime_path,
)
from app.services.solidworks_global_lock import require_current_job_lock

REPO_ROOT = bundle_root()
RUNTIME_ROOT = runtime_path(".")
RUNS_DIR = runtime_path("drw_output") / "runs"

APP_VERSION = "1.1.0"


def _short_uuid() -> str:
    return uuid.uuid4().hex[:12]


def _try_get_sw_revision() -> str:
    if os.environ.get("SWDS_ALLOW_RUN_MANAGER_SW_COM_PROBE", "").strip() not in {"1", "true", "TRUE", "yes"}:
        return "deferred_to_worker"
    guard = require_current_job_lock("run_manager._try_get_sw_revision")
    if not guard.get("ok"):
        return "blocked_by_solidworks_lock"
    try:
        import win32com.client
        sw = win32com.client.GetActiveObject("SldWorks.Application")
        try: return str(sw.RevisionNumber())
        except Exception:
            try: return str(sw.RevisionNumber)
            except Exception: return "?"
    except Exception:
        return "not_connected"


@dataclass
class RunContext:
    run_id: str
    started_at: str
    finished_at: str = ""
    app_version: str = APP_VERSION
    sw_revision: str = ""
    strategy: str = "v6_recommended"
    input_part_path_abs: str = ""
    output_dir: str = ""
    output_files: dict = field(default_factory=dict)
    hard_fail: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    drawing_usable: dict = field(default_factory=dict)
    qc_pass_count: int = 0
    score_total: int = 12
    vision_score: int | None = None
    dim_total: int = 0
    bom_status: str = "skip"
    process_status: str = "skip"
    quote_status: str = "skip"
    llm_status: str = "skip"
    fallback_used: bool = False
    exception_summary: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    # v1.7 Task 5: QC 等级制
    dimension_grade: str = ""  # A / B / C / D
    usable_for: list = field(default_factory=list)  # manufacturing / assembly / procurement
    part_class: str = ""  # feature_part / fastener / spring / ...
    standard_annotation_present: bool = False
    has_valid_sidecar_annotation: bool = False
    # v1.8 Task 2: drawing_accuracy_score
    drawing_accuracy_score: dict = field(default_factory=dict)
    # v1.8 Task 3: dimension_sources
    dimension_sources: dict = field(default_factory=dict)
    # v1.8 Task 5: final_quality
    final_quality: dict = field(default_factory=dict)
    # v1.9 Task 6: QC 字段升级
    display_dim_count: int = 0  # 真实 DisplayDimension 数量（Add-in 读取）
    note_dim_count: int = 0  # Note 标注数量（sidecar）
    model_associative_dim_count: int = 0  # 模型关联尺寸数量（InsertModelAnnotations）
    addin_dimension_count: int = 0  # Add-in 生成的尺寸数量
    docmgr_reference_count: int = 0  # Document Manager 读取的引用数量
    pmi_available: bool = False  # 模型是否有 PMI/DimXpert

    @property
    def run_dir(self) -> Path:
        return RUNS_DIR / self.run_id

    def subdir(self, name: str) -> Path:
        d = self.run_dir / name
        d.mkdir(parents=True, exist_ok=True)
        return d

    def add_output_file(self, category: str, src: str | Path) -> Path | None:
        """复制 src 到 run_dir/<category>/，返回目标路径。src 不存在则返回 None"""
        src = Path(src)
        if not src.exists():
            return None
        tgt_dir = self.subdir(category)
        tgt = tgt_dir / src.name
        try:
            shutil.copy2(src, tgt)
        except Exception as e:
            self.exception_summary.append(f"add_output_file({category}, {src.name}): {e}")
            return None
        self.output_files.setdefault(category, []).append(str(tgt))
        return tgt

    def write_log(self, name: str, text: str):
        try:
            log = self.subdir("logs") / name
            with log.open("a", encoding="utf-8") as f:
                f.write(time.strftime("[%Y-%m-%d %H:%M:%S] "))
                f.write(text.rstrip("\n") + "\n")
        except Exception: pass

    def write_manifest(self) -> Path:
        if not self.finished_at:
            self.finished_at = time.strftime("%Y-%m-%d %H:%M:%S")
        manifest = self.subdir("logs").parent / "manifest.json"
        data = asdict(self)
        try:
            manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            self.exception_summary.append(f"write_manifest: {e}")
        return manifest


def new_run(strategy: str = "v6_recommended", input_part_path: str = "") -> RunContext:
    """创建新 run。自动 mkdir 子目录。"""
    rid = _short_uuid()
    ctx = RunContext(
        run_id=rid,
        started_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        sw_revision=_try_get_sw_revision(),
        strategy=strategy,
        input_part_path_abs=str(Path(input_part_path).resolve()) if input_part_path else "",
    )
    ctx.output_dir = str(ctx.run_dir)
    # 提前 mkdir 6 个子目录
    for d in ["input", "drawing", "qc", "bom", "quote", "logs"]:
        ctx.subdir(d)
    # 复制输入文件到 input/
    if input_part_path and Path(input_part_path).exists():
        try:
            shutil.copy2(input_part_path, ctx.subdir("input") / Path(input_part_path).name)
            ctx.output_files.setdefault("input", []).append(str(ctx.subdir("input") / Path(input_part_path).name))
        except Exception as e:
            ctx.exception_summary.append(f"copy input: {e}")
    return ctx


def list_recent_runs(limit: int = 5) -> list[dict]:
    """列出最近 N 次 run（按 started_at 倒序）"""
    out = []
    if not RUNS_DIR.exists():
        return out
    for d in sorted(RUNS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir():
            continue
        m = d / "manifest.json"
        if m.exists():
            try:
                data = json.loads(m.read_text(encoding="utf-8"))
                run_id = data.get("run_id") or d.name
                out.append({
                    "run_id": run_id,
                    "started_at": data.get("started_at") or data.get("generated_at") or "",
                    "finished_at": data.get("finished_at", ""),
                    "drawing_usable": data.get("drawing_usable", {}).get("pass", False),
                    "qc_pass_count": data.get("qc_pass_count", 0),
                    "vision_score": data.get("vision_score"),
                    "manifest": str(m),
                })
                if len(out) >= limit:
                    break
            except Exception:
                pass
    return out


def full_pipeline(part_path: str, strategy: str = "v6_recommended", titlebar_overrides: dict = None) -> "RunContext":
    """单件出图 full_pipeline：v6 → QC → vision → BOM → 工艺 → 报价 → manifest"""
    import os
    import subprocess
    import sys
    import json as _json

    ctx = new_run(strategy=strategy, input_part_path=part_path)
    ctx.write_log("run.log", f"=== Full pipeline start ===")
    ctx.write_log("run.log", f"strategy={strategy}")
    ctx.write_log("run.log", f"input_part={ctx.input_part_path_abs}")
    ctx.write_log("run.log", f"sw_revision={ctx.sw_revision}")
    if titlebar_overrides:
        ctx.write_log("run.log", f"titlebar_overrides={_json.dumps(titlebar_overrides, ensure_ascii=False)}")

    # 1) 出图（v6）
    qc_loop_v6 = pipeline_script_path("drw_qc_loop_v6")
    qc_loop_v5 = pipeline_script_path("drw_qc_loop_v5")
    use_v5 = (strategy == "v5_compat") or (not qc_loop_v6.exists())
    qc_script_key = "drw_qc_loop_v5" if use_v5 else "drw_qc_loop_v6"
    qc_script = str(qc_loop_v5) if use_v5 else str(qc_loop_v6)
    ctx.write_log("run.log", f"qc_script={qc_script}")

    sw_log = ctx.subdir("logs") / "sw.log"
    try:
        with sw_log.open("w", encoding="utf-8") as f:
            f.write(f"[runner] using {'v5 fallback' if use_v5 else 'v6'}\n")
            # v1.4 Task 3.5: 构造 sub_env，注入 PYTHONPATH（与 Task 1 一致）
            # 和 TITLEBAR_OVERRIDES_JSON（UI 录入的 overrides，最高优先级）
            # v1.7 Task 1: 注入 RUN_DIR，让 subprocess 的 sidecar/seed/QC 写入 run_dir
            sub_env = child_process_env()
            sub_env["RUN_DIR"] = str(ctx.run_dir)
            sub_env["RUN_ID"] = ctx.run_id
            if titlebar_overrides:
                sub_env["TITLEBAR_OVERRIDES_JSON"] = _json.dumps(titlebar_overrides, ensure_ascii=False)
            r = subprocess.run(
                pipeline_command(qc_script_key, [ctx.input_part_path_abs]),
                cwd=str(RUNTIME_ROOT), env=sub_env,
                stdout=f, stderr=subprocess.STDOUT, timeout=1500,
            )
            f.write(f"\n[runner] exit_code={r.returncode}\n")
        ctx.write_log("run.log", f"qc_loop exit_code={r.returncode}")
    except Exception as e:
        ctx.exception_summary.append(f"qc_loop subprocess: {e}")
        ctx.write_log("exceptions.log", f"qc_loop subprocess: {e}")

    # 检查 fallback_used
    try:
        sw_log_text = sw_log.read_text(encoding="utf-8", errors="ignore")
        ctx.fallback_used = use_v5 or ("using v5 fallback" in sw_log_text)
    except Exception:
        pass

    # 2) 收集 SLDDRW/PDF/DXF/PNG
    base = Path(ctx.input_part_path_abs).stem
    drw_dir_old = runtime_path("drw_output") / "v5"
    for ext in ["SLDDRW", "PDF", "DXF", "PNG"]:
        cand = drw_dir_old / f"{base}_v5.{ext}"
        if cand.exists():
            ctx.add_output_file("drawing", cand)
        else:
            cand_lower = drw_dir_old / f"{base}_v5.{ext.lower()}"
            if cand_lower.exists():
                ctx.add_output_file("drawing", cand_lower)

    # v1.4 Task 5 回退: 若 PNG 不存在，用 PyMuPDF 从 PDF 渲染 PNG
    png_cand = drw_dir_old / f"{base}_v5.PNG"
    if not png_cand.exists():
        png_cand_lower = drw_dir_old / f"{base}_v5.png"
        if png_cand_lower.exists():
            png_cand = png_cand_lower
        else:
            # PDF→PNG 回退渲染
            pdf_cand = drw_dir_old / f"{base}_v5.PDF"
            if not pdf_cand.exists():
                pdf_cand = drw_dir_old / f"{base}_v5.pdf"
            if pdf_cand.exists():
                try:
                    import fitz  # PyMuPDF
                    doc = fitz.open(str(pdf_cand))
                    if doc.page_count > 0:
                        page = doc[0]
                        # 渲染分辨率 200 DPI（默认 72）
                        mat = fitz.Matrix(200/72, 200/72)
                        pix = page.get_pixmap(matrix=mat)
                        png_out = drw_dir_old / f"{base}_v5.PNG"
                        pix.save(str(png_out))
                        doc.close()
                        ctx.write_log("run.log", f"PNG 回退渲染: PDF→{png_out.name} ({png_out.stat().st_size//1024}KB)")
                        print(f"[v1.4 PNG fallback] {png_out.name} rendered ({png_out.stat().st_size//1024}KB)")
                        # 重新收集 PNG
                        ctx.add_output_file("drawing", png_out)
                except ImportError:
                    ctx.write_log("exceptions.log", "PNG 回退失败: PyMuPDF(fitz) 未安装")
                    print("[v1.4 PNG fallback] PyMuPDF not installed")
                except Exception as e:
                    ctx.write_log("exceptions.log", f"PNG 回退渲染失败: {e}")
                    print(f"[v1.4 PNG fallback] render failed: {e}")

    # 3) 收集 qc.json + vision.json
    rows = []
    route = []
    qc_json_src = drw_dir_old / f"{base}_v5_qc.json"
    if qc_json_src.exists():
        ctx.add_output_file("qc", qc_json_src)
        try:
            qc_data = json.loads(qc_json_src.read_text(encoding="utf-8"))
            ctx.hard_fail = qc_data.get("hard_fail", [])
            ctx.warnings = qc_data.get("warnings", [])
            ctx.drawing_usable = qc_data.get("drawing_usable", {})
            ctx.qc_pass_count = qc_data.get("score_pass_count", 0)
            ctx.dim_total = qc_data.get("checks", {}).get("dim_count_sufficient", {}).get("dim_total", 0)
            # v1.7 Task 5: 收集 dimension_grade / usable_for / part_class / standard_annotation_present
            ctx.dimension_grade = qc_data.get("dimension_grade", "")
            ctx.usable_for = qc_data.get("usable_for", [])
            ctx.part_class = qc_data.get("part_class", "")
            ctx.standard_annotation_present = qc_data.get("standard_annotation_present", False)
            ctx.has_valid_sidecar_annotation = qc_data.get("has_valid_sidecar_annotation", False)
            # v1.8 Task 2: drawing_accuracy_score
            ctx.drawing_accuracy_score = qc_data.get("drawing_accuracy_score", {})
            # v1.8 Task 3: dimension_sources
            ctx.dimension_sources = qc_data.get("dimension_sources", {})
            # v1.9 Task 6: QC 字段升级（从 qc.json 读取，如果存在）
            ctx.display_dim_count = qc_data.get("display_dim_count", 0)
            ctx.note_dim_count = qc_data.get("note_dim_count", 0)
            ctx.model_associative_dim_count = qc_data.get("model_associative_dim_count", 0)
            ctx.addin_dimension_count = qc_data.get("addin_dimension_count", 0)
            ctx.docmgr_reference_count = qc_data.get("docmgr_reference_count", 0)
            ctx.pmi_available = qc_data.get("pmi_available", False)
        except Exception as e:
            ctx.exception_summary.append(f"parse qc.json: {e}")
    vision_json_src = drw_dir_old / f"{base}_v5_vision.json"
    if vision_json_src.exists():
        ctx.add_output_file("qc", vision_json_src)
        try:
            v_data = json.loads(vision_json_src.read_text(encoding="utf-8"))
            ctx.vision_score = v_data.get("score")
            ctx.llm_status = "ok"
        except Exception as e:
            ctx.exception_summary.append(f"parse vision.json: {e}")
            ctx.llm_status = "error"
    else:
        ctx.llm_status = "skip"

    # v1.7 Task 1: 收集 part_class.json / dimension_sidecar_result.json 到 manifest
    # 这些文件由 subprocess 直接写入 run_dir/qc/（通过 RUN_DIR 环境变量）
    _qc_subdir = ctx.subdir("qc")
    for _qc_artifact in ["part_class.json", "dimension_sidecar_result.json", "standard_annotation.json"]:
        _qc_artifact_path = _qc_subdir / _qc_artifact
        if _qc_artifact_path.exists():
            _existing = ctx.output_files.get("qc", [])
            if str(_qc_artifact_path) not in _existing:
                ctx.output_files.setdefault("qc", []).append(str(_qc_artifact_path))

    # v1.4 Task 5 回退后重评: 若 PNG 现已存在（回退渲染成功），从 hard_fail 移除 png_missing 并重算 drawing_usable.pass
    # 原因: QC 在步骤 1 subprocess 中运行时 PNG 尚未生成，png_missing 被写入 qc.json；
    #       步骤 2 的 PDF→PNG 回退渲染成功后，需在此修正 QC 结论。
    png_exists_now = (drw_dir_old / f"{base}_v5.PNG").exists() or (drw_dir_old / f"{base}_v5.png").exists()
    if png_exists_now and "png_missing" in ctx.hard_fail:
        ctx.hard_fail = [x for x in ctx.hard_fail if x != "png_missing"]
        if isinstance(ctx.drawing_usable, dict):
            criteria = ctx.drawing_usable.get("criteria", {})
            if isinstance(criteria, dict):
                criteria["files_exported"] = (
                    "drawing_not_created" not in ctx.hard_fail
                    and "pdf_missing" not in ctx.hard_fail
                    and "dxf_missing" not in ctx.hard_fail
                    and "png_missing" not in ctx.hard_fail
                )
                ctx.drawing_usable["criteria"] = criteria
            ctx.drawing_usable["pass"] = (len(ctx.hard_fail) == 0)
        ctx.write_log("run.log", "PNG 回退后重评: png_missing 已从 hard_fail 移除，drawing_usable.pass 已重算")
        print(f"[v1.4 PNG fallback] reconciled hard_fail={ctx.hard_fail}, drawing_usable.pass={ctx.drawing_usable.get('pass') if isinstance(ctx.drawing_usable, dict) else None}")

    # 4) BOM
    try:
        from libs.bom import extract, write_csv, write_xlsx
        rows = extract(ctx.input_part_path_abs)
        bom_csv = ctx.subdir("bom") / "bom.csv"
        bom_xlsx = ctx.subdir("bom") / "bom.xlsx"
        bom_json = ctx.subdir("bom") / "bom.json"
        write_csv(rows, bom_csv)
        write_xlsx(rows, bom_xlsx)
        bom_json.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        ctx.output_files.setdefault("bom", []).extend([str(bom_csv), str(bom_xlsx), str(bom_json)])
        ctx.bom_status = "ok" if rows else "empty"
        ctx.write_log("run.log", f"bom rows={len(rows)}")
    except Exception as e:
        ctx.bom_status = "error"
        ctx.exception_summary.append(f"bom: {e}")
        ctx.write_log("exceptions.log", f"bom: {e}")

    # 5) 工艺路线
    try:
        from libs.process import suggest_route
        route = suggest_route({"类别": "钣金件", "weight_g": 100})
        proc_json = ctx.subdir("quote") / "process_route.json"
        proc_json.write_text(json.dumps(route, ensure_ascii=False, indent=2), encoding="utf-8")
        ctx.output_files.setdefault("quote", []).append(str(proc_json))
        try:
            from openpyxl import Workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "工艺路线"
            ws.append(["op_no", "process_name", "qty", "minutes", "cny"])
            for i, r in enumerate(route, 1):
                ws.append([i, r.get("name", ""), r.get("qty", 0), r.get("minutes", 0), r.get("cny", 0)])
            proc_xlsx = ctx.subdir("quote") / "process_route.xlsx"
            wb.save(proc_xlsx)
            ctx.output_files.setdefault("quote", []).append(str(proc_xlsx))
        except Exception:
            pass
        ctx.process_status = "ok"
    except Exception as e:
        ctx.process_status = "error"
        ctx.exception_summary.append(f"process: {e}")
        ctx.write_log("exceptions.log", f"process: {e}")

    # 6) 报价
    try:
        from libs.pricing.quote import calculate, write_quote_md
        quote_result = calculate(rows, route)
        quote_json = ctx.subdir("quote") / "quote.json"
        quote_md = ctx.subdir("quote") / "quote.md"
        quote_json.write_text(json.dumps(quote_result, ensure_ascii=False, indent=2), encoding="utf-8")
        write_quote_md(quote_result, rows, route, quote_md)
        ctx.output_files.setdefault("quote", []).extend([str(quote_json), str(quote_md)])
        try:
            from openpyxl import Workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "报价单"
            ws.append(["项目", "金额(元)"])
            br = quote_result.get("breakdown", {})
            for k in ["material_cny", "process_cny", "surface_cny", "packing_cny", "subtotal_cny"]:
                ws.append([k, br.get(k, 0)])
            ws.append(["total_cny", quote_result.get("total_cny", 0)])
            quote_xlsx = ctx.subdir("quote") / "quote.xlsx"
            wb.save(quote_xlsx)
            ctx.output_files.setdefault("quote", []).append(str(quote_xlsx))
        except Exception:
            pass
        ctx.quote_status = f"ok total={quote_result.get('total_cny', 0)}"
    except Exception as e:
        ctx.quote_status = "error"
        ctx.exception_summary.append(f"quote: {e}")
        ctx.write_log("exceptions.log", f"quote: {e}")

    # 7) v1.8 Task 4+5: vision_qc_v2 + final_quality
    try:
        from app.services.vision_qc_v2 import run_vision_qc_v2
        from app.services.final_quality import compute_final_quality
        _qc_json_v18 = None
        _png_v18 = None
        _qc_subdir_v18 = ctx.subdir("qc")
        for _f in _qc_subdir_v18.glob("*_qc.json"):
            _qc_json_v18 = _f
            break
        for _f in (ctx.subdir("drawing")).glob("*.PNG"):
            _png_v18 = _f
            break
        if not _png_v18:
            for _f in (ctx.subdir("drawing")).glob("*.png"):
                _png_v18 = _f
                break
        if _qc_json_v18 and _png_v18:
            _vqc2 = run_vision_qc_v2(_qc_json_v18, _png_v18, ctx.run_dir)
            ctx.output_files.setdefault("qc", []).append(str(ctx.run_dir / "qc" / "vision_qc_v2.json"))
            # final_quality
            _fq = compute_final_quality(ctx, _vqc2)
            ctx.final_quality = _fq
            _fq_path = ctx.run_dir / "qc" / "final_quality.json"
            _fq_path.write_text(json.dumps(_fq, ensure_ascii=False, indent=2), encoding="utf-8")
            ctx.output_files.setdefault("qc", []).append(str(_fq_path))
        elif _qc_json_v18:
            # PNG 缺失也要生成 final_quality
            from app.services.vision_qc_v2 import run_vision_qc_v2
            from app.services.final_quality import compute_final_quality
            _vqc2 = run_vision_qc_v2(_qc_json_v18, _png_v18 or Path(""), ctx.run_dir)
            _fq = compute_final_quality(ctx, _vqc2)
            ctx.final_quality = _fq
            _fq_path = ctx.run_dir / "qc" / "final_quality.json"
            _fq_path.write_text(json.dumps(_fq, ensure_ascii=False, indent=2), encoding="utf-8")
            ctx.output_files.setdefault("qc", []).append(str(_fq_path))
    except Exception as e:
        ctx.exception_summary.append(f"vision_qc_v2/final_quality: {e}")
        ctx.write_log("exceptions.log", f"vision_qc_v2/final_quality: {e}")

    # 8) manifest
    ctx.write_manifest()
    ctx.write_log("run.log", f"=== Full pipeline done. drawing_usable={ctx.drawing_usable.get('pass') if isinstance(ctx.drawing_usable, dict) else None} ===")
    return ctx


if __name__ == "__main__":
    ctx = new_run(strategy="v6_recommended")
    ctx.write_manifest()
    print(f"[run_manager] new_run created: {ctx.run_id}")
    print(f"[run_manager] dir: {ctx.run_dir}")
    print(f"[run_manager] manifest: {ctx.run_dir / 'manifest.json'}")
    print(f"[run_manager] subdirs: {[p.name for p in ctx.run_dir.iterdir() if p.is_dir()]}")
