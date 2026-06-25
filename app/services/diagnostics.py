"""诊断包 zip 生成器（Spec enhance-v1-1 Task 8）

功能：根据 run_id 把 manifest / qc / vision / logs / health_check / screenshots / version.txt
打包到 diagnostics_<run_id>.zip 供用户报障。
"""
from __future__ import annotations
import json
import platform
import sys
import time
import zipfile
from pathlib import Path

from app.services.resource_paths import runtime_root
from app.services.solidworks_global_lock import require_current_job_lock

REPO_ROOT = runtime_root()
RUNS_DIR = REPO_ROOT / "drw_output" / "runs"
DIAGNOSTICS_DIR = REPO_ROOT / "drw_output" / "diagnostics"


def _gen_version_txt() -> str:
    lines = [f"app_version: 1.1.0"]
    try:
        lines.append(f"python: {sys.version.splitlines()[0]}")
    except Exception: pass
    try:
        lines.append(f"platform: {platform.platform()}")
    except Exception: pass
    try:
        import win32com
        lines.append(f"pywin32: {getattr(win32com, '__version__', '?')}")
    except Exception:
        lines.append("pywin32: not_available")
    try:
        import win32com.client
        guard = require_current_job_lock("diagnostics.version_solidworks_revision")
        if not guard.get("ok"):
            lines.append("solidworks_revision: blocked_by_solidworks_lock")
            lines.append("solidworks_lock_conflict: " + json.dumps({
                "reason": guard.get("reason", ""),
                "owner": guard.get("owner", {}),
                "fix_suggestion": guard.get("fix_suggestion", ""),
            }, ensure_ascii=False))
            raise RuntimeError("blocked_by_solidworks_lock")
        sw = win32com.client.GetActiveObject("SldWorks.Application")
        try: rev = str(sw.RevisionNumber())
        except Exception:
            try: rev = str(sw.RevisionNumber)
            except Exception: rev = "?"
        lines.append(f"solidworks_revision: {rev}")
    except RuntimeError as exc:
        if str(exc) != "blocked_by_solidworks_lock":
            lines.append("solidworks_revision: not_connected")
    except Exception:
        lines.append("solidworks_revision: not_connected")
    lines.append(f"build_time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    return "\n".join(lines)


def _gen_health_json() -> str:
    try:
        from app.services.system_health_service import collect_system_health, system_health_payload

        rows, result = collect_system_health()
        return json.dumps(system_health_payload(rows, result), ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"system_health failed: {e}"}, ensure_ascii=False)


def build_diagnostics_zip(run_id: str, screenshots_dir: Path | None = None) -> Path:
    """根据 run_id 打包诊断 zip
    
    返回最终 zip 路径
    """
    DIAGNOSTICS_DIR.mkdir(parents=True, exist_ok=True)
    out_zip = DIAGNOSTICS_DIR / f"diagnostics_{run_id}.zip"
    run_dir = RUNS_DIR / run_id
    
    written: set[str] = set()

    def add_file(src: Path, arcname: str) -> None:
        if not src.exists() or not src.is_file() or arcname in written:
            return
        zf.write(src, arcname)
        written.add(arcname)

    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1) manifest.json
        manifest = run_dir / "manifest.json"
        add_file(manifest, "manifest.json")
        
        # 2) qc/qc.json
        qc_json = run_dir / "qc" / "qc.json"
        if not qc_json.exists():
            # 兼容老路径
            for cand in (run_dir / "qc").glob("*qc.json"):
                qc_json = cand; break
        add_file(qc_json, "qc.json")
        
        # 3) qc/vision.json
        vision_json = run_dir / "qc" / "vision.json"
        if not vision_json.exists():
            for cand in (run_dir / "qc").glob("*vision.json"):
                vision_json = cand; break
        add_file(vision_json, "vision.json")

        # v2.3: package all JSON evidence under qc/, preserving filenames.
        qc_dir = run_dir / "qc"
        if qc_dir.exists():
            preferred = [
                "vision_qc_v5.json",
                "vision_qc_v4.json",
                "vision_qc_v3.json",
                "final_quality.json",
                "part_class.json",
                "blueprint_decision.json",
                "dimension_sidecar_result.json",
                "dimension_arrange.json",
                "layout_solver_v2.json",
                "sw_session.json",
            ]
            for name in preferred:
                add_file(qc_dir / name, f"qc/{name}")
            for cand in sorted(qc_dir.glob("*.json")):
                add_file(cand, f"qc/{cand.name}")

        for cand, arcname in [
            (run_dir / "sw_session.json", "sw_session.json"),
            (run_dir / "logs" / "sw_session.json", "logs/sw_session.json"),
        ]:
            add_file(cand, arcname)
        
        # 4-6) logs/*.log
        log_dir = run_dir / "logs"
        if log_dir.exists():
            for log_name in [
                "run.log",
                "sw.log",
                "exceptions.log",
                "ui.log",
                "worker_stdout.log",
                "worker_stderr.log",
            ]:
                add_file(log_dir / log_name, f"logs/{log_name}")
            for cand in sorted(log_dir.glob("*")):
                if cand.suffix.lower() in {".log", ".json", ".txt"}:
                    add_file(cand, f"logs/{cand.name}")

        add_file(run_dir / "job_event_log.jsonl", "job_event_log.jsonl")
        
        # 7) health_check.json（即时跑一次）
        zf.writestr("health_check.json", _gen_health_json())
        
        # 8) screenshots：如指定目录则尝试加 screenshot_home.png + screenshot_qc.png
        if screenshots_dir is None:
            screenshots_dir = REPO_ROOT / ".trae" / "specs" / "enhance-v1-1-complete-deliverable" / "screenshots"
        if screenshots_dir.exists():
            for cand in sorted(screenshots_dir.glob("*.png")):
                add_file(cand, f"screenshots/{cand.name}")
            for cand_name, target in [
                ("01_home.png", "screenshot_home.png"),
                ("01_home_health.png", "screenshot_home.png"),
                ("01_dashboard.png", "screenshot_home.png"),
                ("03_qc.png", "screenshot_qc.png"),
            ]:
                p = screenshots_dir / cand_name
                if p.exists():
                    add_file(p, target)
                    if target == "screenshot_home.png":
                        break  # 只装一张 home
        
        # 9) version.txt
        zf.writestr("version.txt", _gen_version_txt())
    
    return out_zip


def list_diagnostics() -> list[Path]:
    if not DIAGNOSTICS_DIR.exists():
        return []
    return sorted(DIAGNOSTICS_DIR.glob("diagnostics_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)


if __name__ == "__main__":
    # 找最近 run
    if not RUNS_DIR.exists():
        print("no runs"); sys.exit(2)
    runs = sorted(RUNS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    if not runs:
        print("no runs"); sys.exit(2)
    rid = runs[0].name
    print(f"[diagnostics] using run_id={rid}")
    zp = build_diagnostics_zip(rid)
    print(f"[diagnostics] zip: {zp} ({zp.stat().st_size} bytes)")
    # 列内容
    with zipfile.ZipFile(zp) as zf:
        for n in zf.namelist():
            print(f"  - {n}")
