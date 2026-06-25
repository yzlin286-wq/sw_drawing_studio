"""v1.9 Task 5: MBD/PMI Probe Service

检查模型是否存在 DimXpert / PMI / annotation views
若存在 PMI，记录可用于 2D 派生的 annotation view

输出: pmi_probe.json
"""
from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Any

from app.services.solidworks_global_lock import require_current_job_lock


def _get_sw_app():
    """获取 SolidWorks Application COM 对象"""
    guard = require_current_job_lock("pmi_probe_service._get_sw_app")
    if not guard.get("ok"):
        raise RuntimeError(
            "blocked_by_solidworks_lock: "
            + json.dumps({
                "reason": guard.get("reason", ""),
                "owner": guard.get("owner", {}),
                "fix_suggestion": guard.get("fix_suggestion", ""),
            }, ensure_ascii=False)
        )
    import win32com.client as wc
    try:
        return wc.GetActiveObject("SldWorks.Application")
    except Exception:
        try:
            return wc.Dispatch("SldWorks.Application")
        except Exception as e:
            raise RuntimeError(f"无法连接 SolidWorks: {e}")


def probe_pmi(part_path: str, run_dir: Path = None, run_id: str = "") -> dict:
    """检查模型的 PMI/DimXpert/annotation views

    通过 Add-in ProbePMI 方法调用 SW API

    Args:
        part_path: SLDPRT 绝对路径
        run_dir: run_dir 根目录（可选）
        run_id: run_id（可选）

    Returns:
        {
            "success": bool,
            "part_path": str,
            "pmi_available": bool,
            "dimxpert_available": bool,
            "annotation_views": list,
            "annotation_view_count": int,
            "pmi_features_count": int,
            "reason": str,
            "timestamp": str,
        }
    """
    result = {
        "success": False,
        "part_path": str(Path(part_path).resolve()),
        "pmi_available": False,
        "dimxpert_available": False,
        "annotation_views": [],
        "annotation_view_count": 0,
        "pmi_features_count": 0,
        "reason": "",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    part_path = str(Path(part_path).resolve())

    try:
        sw = _get_sw_app()
    except Exception as e:
        if "blocked_by_solidworks_lock" in str(e):
            result["status"] = "blocked_by_solidworks_lock"
            result["failure_bucket"] = "solidworks_lock_conflict"
        result["reason"] = f"SolidWorks 未运行: {e}"
        return result

    try:
        # 使用 Add-in ProbePMI
        from app.services.sw_addin_client import _find_addin
        addin, method = _find_addin(sw)
        if addin is None:
            result["reason"] = "Add-in 未加载"
            return result

        # 调用 Add-in ProbePMI
        ret = addin.ProbePMI(part_path, run_id)
        if isinstance(ret, str):
            try:
                parsed = json.loads(ret)
                result.update(parsed)
            except Exception:
                result["reason"] = f"Add-in 返回非 JSON: {ret[:200]}"
        else:
            result["reason"] = f"Add-in 返回类型异常: {type(ret)}"

    except Exception as e:
        result["reason"] = f"PMI probe 异常: {e}"

    return result


def probe_pmi_batch(part_paths: list, run_dir: Path = None) -> dict:
    """批量探测 PMI

    Args:
        part_paths: SLDPRT 路径列表
        run_dir: run_dir 根目录

    Returns:
        {
            "version": "v1.9",
            "task": "Task 5 MBD/PMI Probe",
            "timestamp": str,
            "targets": list,
            "summary": dict,
        }
    """
    results = {
        "version": "v1.9",
        "task": "Task 5 MBD/PMI Probe",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "targets": [],
        "summary": {
            "total": len(part_paths),
            "success": 0,
            "pmi_available": 0,
            "dimxpert_available": 0,
            "annotation_views_found": 0,
        },
    }

    for part_path in part_paths:
        result = probe_pmi(part_path, run_dir)
        results["targets"].append(result)

        if result.get("success"):
            results["summary"]["success"] += 1
        if result.get("pmi_available"):
            results["summary"]["pmi_available"] += 1
        if result.get("dimxpert_available"):
            results["summary"]["dimxpert_available"] += 1
        if result.get("annotation_view_count", 0) > 0:
            results["summary"]["annotation_views_found"] += 1

    return results


def write_pmi_probe(run_dir: Path, result: dict) -> Path:
    """写入 pmi_probe.json"""
    qc_dir = run_dir / "qc"
    qc_dir.mkdir(parents=True, exist_ok=True)
    out_path = qc_dir / "pmi_probe.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def main():
    """CLI: python pmi_probe_service.py probe <part_path>"""
    import sys
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python pmi_probe_service.py probe <part_path>")
        print("  python pmi_probe_service.py probe_batch <part_path1> <part_path2> ...")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "probe":
        if len(sys.argv) < 3:
            print("Usage: python pmi_probe_service.py probe <part_path>")
            sys.exit(1)
        result = probe_pmi(sys.argv[2])
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif cmd == "probe_batch":
        if len(sys.argv) < 3:
            print("Usage: python pmi_probe_service.py probe_batch <part_path1> ...")
            sys.exit(1)
        result = probe_pmi_batch(sys.argv[2:])
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
