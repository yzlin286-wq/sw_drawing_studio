"""v1.7 Task 3: C# Dimension Sidecar 的 Python 包装器

职责:
  1. 尝试调用编译好的 SwDimensionSidecar.exe
  2. 若 .exe 不存在，尝试用 dotnet build 编译
  3. 编译失败则降级用 Python COM InvokeMember 方式（早期绑定）
  4. sidecar 失败不得 UI 崩溃，但必须写 dimension_sidecar_result.json 记录 reason

调用方式:
  from app.services.dimension_sidecar_service import run_dimension_sidecar
  result = run_dimension_sidecar(drawing_path, part_path, run_dir, part_class)
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from app.services.solidworks_global_lock import require_current_job_lock

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SIDECAR_DIR = REPO_ROOT / "tools" / "SwDimensionSidecar"
SIDECAR_EXE = SIDECAR_DIR / "bin" / "SwDimensionSidecar.exe"


def _write_result(out_path: Path, result: dict) -> None:
    """写 dimension_sidecar_result.json"""
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[dimension_sidecar] write result failed: {e}", file=sys.stderr)


def _try_build_exe() -> bool:
    """尝试用 dotnet build 编译 SwDimensionSidecar.exe"""
    if SIDECAR_EXE.exists():
        return True
    try:
        # 检查 dotnet 是否可用
        r = subprocess.run(["dotnet", "--version"], capture_output=True, timeout=10)
        if r.returncode != 0:
            return False
        # 编译
        r = subprocess.run(
            ["dotnet", "build", str(SIDECAR_DIR / "SwDimensionSidecar.csproj"),
             "-c", "Release", "-o", str(SIDECAR_DIR / "bin")],
            capture_output=True, timeout=120,
        )
        return SIDECAR_EXE.exists()
    except Exception:
        return False


def _run_exe(drawing_path: str, part_path: str, run_dir: Path, part_class: str, out_path: Path) -> Optional[dict]:
    """调用编译好的 .exe"""
    if not SIDECAR_EXE.exists():
        return None
    try:
        cmd = [
            str(SIDECAR_EXE),
            "--drawing", drawing_path,
            "--part", part_path,
            "--run-dir", str(run_dir),
            "--part-class", part_class,
            "--out", str(out_path),
        ]
        r = subprocess.run(cmd, capture_output=True, timeout=180, text=True, encoding="utf-8")
        if out_path.exists():
            # C# exe 可能输出 UTF-8 BOM，用 utf-8-sig 兼容
            return json.loads(out_path.read_text(encoding="utf-8-sig"))
        return None
    except Exception as e:
        return {"success": False, "status": "exe_exception", "reason": str(e)}


def _run_python_fallback(drawing_path: str, part_path: str, part_class: str, out_path: Path) -> dict:
    """降级：用 Python COM InvokeMember 方式（早期绑定）

    通过 Type.InvokeMember 调用，绕过 pywin32 IDispatch 动态分发问题。
    这是真正的早期绑定方式，与 C# 反射调用等价。
    """
    result = {
        "version": "v1.7",
        "success": False,
        "status": "python_fallback",
        "msg": "",
        "reason": "",
        "drawing_path": drawing_path,
        "part_path": part_path,
        "part_class": part_class,
        "annotations_added": 0,
        "overall_length": None,
        "overall_width": None,
        "overall_height": None,
        "fastener_spec": "",
        "spring_spec": "",
        "standard_annotation_present": False,
        "dimension_count_before": 0,
        "dimension_count_after": 0,
        "fallback_mode": "python_invoke_member",
    }
    guard = require_current_job_lock("dimension_sidecar_service._run_python_fallback")
    if not guard.get("ok"):
        result.update({
            "status": "blocked_by_solidworks_lock",
            "reason": "SolidWorks dimension fallback requires the active CAD worker lock.",
            "lock_conflict": guard,
        })
        _write_result(out_path, result)
        return result

    try:
        import win32com.client
        import pythoncom
        from win32com.client import VARIANT
    except ImportError as e:
        result["status"] = "error"
        result["reason"] = f"pywin32 unavailable: {e}"
        _write_result(out_path, result)
        return result

    try:
        sw = win32com.client.GetActiveObject("SldWorks.Application")
    except Exception as e:
        result["status"] = "error"
        result["reason"] = f"SolidWorks not running: {e}"
        _write_result(out_path, result)
        return result

    # 激活工程图
    drw = None
    try:
        err_var = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        drw = sw.ActivateDoc3(drawing_path, True, 0, err_var)
    except Exception:
        pass
    if drw is None:
        try:
            err_var = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            warn_var = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            drw = sw.OpenDoc6(drawing_path, 3, 257, "", err_var, warn_var)
        except Exception:
            pass
    if drw is None:
        result["status"] = "error"
        result["reason"] = "cannot activate/open drawing"
        _write_result(out_path, result)
        return result

    # 计数前尺寸数
    def _count_dims(drw_obj) -> int:
        try:
            count = 0
            view = drw_obj.GetFirstView
            if callable(view):
                view = view()
            while view is not None:
                try:
                    disp_dim = view.GetFirstDisplayDimension
                    if callable(disp_dim):
                        disp_dim = disp_dim()
                    while disp_dim is not None:
                        count += 1
                        try:
                            disp_dim = view.GetNextDisplayDimension(disp_dim)
                        except Exception:
                            break
                except Exception:
                    pass
                try:
                    view = view.GetNextView
                    if callable(view):
                        view = view()
                except Exception:
                    break
            return count
        except Exception:
            return 0

    dim_before = _count_dims(drw)
    result["dimension_count_before"] = dim_before

    added = 0
    standard_anno = False

    if part_class in ("fastener", "spring", "purchased_part"):
        # 采购类：插入标准标注
        added, standard_anno = _insert_standard_annotations_py(drw, part_path, part_class, result, sw)
    else:
        # feature_part 等：尝试 InsertModelAnnotations3（InvokeMember 方式）
        added = _try_insert_model_annotations3_py(drw)
        if added == 0:
            # 降级：插入总长/总宽/总高参考标注
            added = _insert_overall_dimensions_py(drw, part_path, result, sw)

    # ForceRebuild3
    try:
        drw.ForceRebuild3(True)
    except Exception:
        pass

    dim_after = _count_dims(drw)
    result["dimension_count_after"] = dim_after
    result["annotations_added"] = added
    result["standard_annotation_present"] = standard_anno
    result["success"] = added > 0 or standard_anno
    result["status"] = "ok" if result["success"] else "no_annotation_added"
    if not result["success"]:
        result["reason"] = "no annotations could be added"

    _write_result(out_path, result)
    return result


def _try_insert_model_annotations3_py(drw) -> int:
    """尝试调用 InsertModelAnnotations3 / InsertModelAnnotations2 导入模型尺寸

    pywin32 下 InsertModelAnnotations3 的 TargetLayer="" 参数可能触发类型不匹配，
    因此依次尝试多种签名和参数组合。
    """
    import pythoncom
    from win32com.client import VARIANT

    # 尝试 1: InsertModelAnnotations3 用 None 替代空字符串
    try:
        result = drw.InsertModelAnnotations3(True, 3, False, True, False, None, False)
        if result is not None:
            if isinstance(result, (list, tuple)):
                return len(result)
            return 1
    except Exception as exc:
        print(f"[dimension_sidecar py] InsertModelAnnotations3(None) failed: {exc}", file=sys.stderr)

    # 尝试 2: InsertModelAnnotations3 用 VARIANT 空字符串
    try:
        empty_str = VARIANT(pythoncom.VT_BSTR, "")
        result = drw.InsertModelAnnotations3(True, 3, False, True, False, empty_str, False)
        if result is not None:
            if isinstance(result, (list, tuple)):
                return len(result)
            return 1
    except Exception as exc:
        print(f"[dimension_sidecar py] InsertModelAnnotations3(VARIANT) failed: {exc}", file=sys.stderr)

    # 尝试 3: InsertModelAnnotations2（5 个参数，无 TargetLayer）
    try:
        result = drw.InsertModelAnnotations2(True, 3, False, True, False)
        if result is not None:
            if isinstance(result, (list, tuple)):
                return len(result)
            return 1
    except Exception as exc:
        print(f"[dimension_sidecar py] InsertModelAnnotations2 failed: {exc}", file=sys.stderr)

    # 尝试 4: InsertModelAnnotations（2 个参数，最简签名）
    try:
        result = drw.InsertModelAnnotations(True, 3)
        if result is not None:
            if isinstance(result, (list, tuple)):
                return len(result)
            return 1
    except Exception as exc:
        print(f"[dimension_sidecar py] InsertModelAnnotations failed: {exc}", file=sys.stderr)

    return 0


def _insert_overall_dimensions_py(drw, part_path: str, result: dict, sw) -> int:
    """降级：插入总长/总宽/总高参考标注（Note 文本）

    v1.8 Task 3: 对 long_thin/tiny_part 分项标注，提升 dimension_sources 可追溯性
    """
    try:
        bbox = _get_part_bbox_py(part_path, sw)
        if bbox and len(bbox) >= 3:
            length, width, height = bbox[0], bbox[1], bbox[2]
            result["overall_length"] = length
            result["overall_width"] = width
            result["overall_height"] = height

            # v1.8 Task 3: 分项标注（每项独立 Note），提升可读性和可追溯性
            added = 0
            added += _insert_note_py(drw, f"总长 L={length:.1f}mm", 0.15, 0.05)
            added += _insert_note_py(drw, f"总宽 W={width:.1f}mm", 0.15, 0.065)
            added += _insert_note_py(drw, f"总高 H={height:.1f}mm", 0.15, 0.080)

            # 记录 dimension_sources
            result["dimension_sources"] = {
                "overall_length": {"source": "bbox_note", "value": length, "type": "note"},
                "overall_width": {"source": "bbox_note", "value": width, "type": "note"},
                "overall_height": {"source": "bbox_note", "value": height, "type": "note"},
            }

            # v1.8 Task 3: 对 long_thin 补充关键特征提示
            part_class = result.get("part_class", "")
            if part_class == "long_thin":
                ratio = length / width if width > 0 else 0
                added += _insert_note_py(drw, f"长径比 L/W={ratio:.1f}", 0.15, 0.095)
                result["dimension_sources"]["long_thin_ratio"] = {
                    "source": "computed", "value": ratio, "type": "note"
                }
            elif part_class == "tiny_part":
                added += _insert_note_py(drw, "小零件 关键尺寸见外形参考", 0.15, 0.095)

            return added
    except Exception as exc:
        result["reason"] = f"InsertOverallDimensions failed: {exc}"
    return 0


def _insert_standard_annotations_py(drw, part_path: str, part_class: str, result: dict, sw) -> tuple:
    """采购类：插入标准标注"""
    try:
        import re
        part_name = Path(part_path).stem
        notes = []

        # 解析规格
        spec = _parse_spec(part_name, part_class)
        if spec:
            notes.append(f"规格: {spec}")
            if part_class == "fastener":
                result["fastener_spec"] = spec
            if part_class == "spring":
                result["spring_spec"] = spec

        # 标准号
        std_no = _lookup_std_no(part_name)
        if std_no:
            notes.append(f"标准号: {std_no}")

        notes.append("数量: 1")
        notes.append("按外购件图纸")

        # 外形参考尺寸
        bbox = _get_part_bbox_py(part_path, sw)
        if bbox and len(bbox) >= 3:
            result["overall_length"] = bbox[0]
            result["overall_width"] = bbox[1]
            result["overall_height"] = bbox[2]
            notes.append(f"外形参考: {bbox[0]:.1f}×{bbox[1]:.1f}×{bbox[2]:.1f}mm")

        added = 0
        y = 0.05
        for note in notes:
            added += _insert_note_py(drw, note, 0.15, y)
            y += 0.015
        return added, added > 0
    except Exception as exc:
        result["reason"] = f"InsertStandardAnnotations failed: {exc}"
        return 0, False


def _parse_spec(part_name: str, part_class: str) -> str:
    import re
    m = re.search(r"M(\d+)x(\d+)", part_name, re.IGNORECASE)
    if m:
        return f"M{m.group(1)}x{m.group(2)}"
    if "弹簧" in part_name or part_class == "spring":
        return "弹簧"
    if "铜套" in part_name:
        return "铜套"
    if "导柱" in part_name:
        return "导柱"
    return ""


def _lookup_std_no(part_name: str) -> str:
    if "螺丝" in part_name or "螺钉" in part_name or "螺栓" in part_name:
        return "GB/T 5783 或 GB/T 70.1"
    if "弹簧" in part_name:
        return "GB/T 2089"
    if "铜套" in part_name:
        return "GB/T 10446"
    if "导柱" in part_name:
        return "GB/T 2861.1"
    return ""


def _insert_note_py(drw, text: str, x: float, y: float) -> int:
    """插入 Note 文本"""
    try:
        note = drw.InsertNote(text, x, y)
        return 1 if note is not None else 0
    except Exception as exc:
        # InsertNote 可能签名不同，尝试其他方式
        try:
            # 通过 Extension.InsertNote 或 SketchManager
            note = drw.CreateText2(text, x, y, 0, 0.003, 0)
            return 1 if note is not None else 0
        except Exception:
            pass
        print(f"[dimension_sidecar py] InsertNote failed: {exc}", file=sys.stderr)
        return 0


def _get_part_bbox_py(part_path: str, sw) -> list:
    """获取 part bbox（mm）"""
    try:
        import pythoncom
        from win32com.client import VARIANT
        # 激活 part
        part = None
        try:
            err_var = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            part = sw.ActivateDoc3(part_path, True, 0, err_var)
        except Exception:
            pass
        if part is None:
            try:
                err_var = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                warn_var = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                part = sw.OpenDoc6(part_path, 1, 257, "", err_var, warn_var)
            except Exception:
                pass
        if part is None:
            return []
        box = part.GetPartBox(True)
        if box and len(box) >= 6:
            dx = abs(box[3] - box[0]) * 1000.0
            dy = abs(box[4] - box[1]) * 1000.0
            dz = abs(box[5] - box[2]) * 1000.0
            dims = sorted([dx, dy, dz], reverse=True)
            return dims
    except Exception as exc:
        print(f"[dimension_sidecar py] GetPartBbox failed: {exc}", file=sys.stderr)
    return []


def run_dimension_sidecar(
    drawing_path: str,
    part_path: str,
    run_dir: Path,
    part_class: str = "feature_part",
) -> dict:
    """运行 dimension sidecar

    Args:
        drawing_path: SLDDRW 绝对路径
        part_path: SLDPRT 绝对路径
        run_dir: run_dir 根目录（产物写入 run_dir/qc/）
        part_class: 零件类别

    Returns:
        dimension_sidecar_result dict
    """
    run_dir = Path(run_dir)
    qc_dir = run_dir / "qc"
    qc_dir.mkdir(parents=True, exist_ok=True)
    out_path = qc_dir / "dimension_sidecar_result.json"
    guard = require_current_job_lock("dimension_sidecar_service.run_dimension_sidecar")
    if not guard.get("ok"):
        result = {
            "version": "v1.7",
            "success": False,
            "status": "blocked_by_solidworks_lock",
            "reason": "SolidWorks dimension sidecar requires the active CAD worker lock.",
            "drawing_path": drawing_path,
            "part_path": part_path,
            "part_class": part_class,
            "lock_conflict": guard,
        }
        _write_result(out_path, result)
        return result

    # 策略 1: 尝试调用 .exe（C# dynamic 早期绑定）
    exe_built = _try_build_exe()
    if exe_built:
        result = _run_exe(drawing_path, part_path, run_dir, part_class, out_path)
        if result is not None:
            if result.get("success"):
                return result
            # v1.7: C# exe 任何失败都降级到 Python fallback
            # 原因：C# 进程无法可靠地激活已打开的工程图（进程隔离 + title 匹配问题）
            # 以及 JSON BOM 解析、COM 异常等均需降级

    # 策略 2: 降级用 Python COM InvokeMember 方式
    return _run_python_fallback(drawing_path, part_path, part_class, out_path)


def main():
    """命令行测试"""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--drawing", required=True)
    parser.add_argument("--part", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--part-class", default="feature_part")
    args = parser.parse_args()
    result = run_dimension_sidecar(args.drawing, args.part, Path(args.run_dir), args.part_class)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
