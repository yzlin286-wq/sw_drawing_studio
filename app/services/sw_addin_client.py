"""v1.9 Task 1: SOLIDWORKS Add-in API 客户端
v2.0 Task 1: Add-in 正式化（新增 ProbeContext/ReadDimensions/GenerateDimensions/ExtractViewEntities/RelinkReferences）

定义 Add-in 方法契约，Python 通过 COM 调用已注册的 SwDrawingStudioAddin。

Add-in 方法（COM-visible）:
  Ping() -> bool
  ProbeContext(run_id) -> dict  [v2.0]
  ReadDimensions(drawing_path, run_id) -> dict  [v2.0]
  GenerateDimensions(drawing_path, part_path, run_id, policy_json) -> dict  [v2.0]
  ExtractViewEntities(drawing_path, view_names_json, run_id) -> dict  [v2.0]
  RelinkReferences(drawing_path, part_path, run_id) -> dict  [v2.0]
  GenerateAssociativeDimensions(drawing_path, part_path, run_id) -> dict  [v1.9 保留]
  RelinkDrawingReferences(drawing_path, part_path, run_id) -> dict  [v1.9 保留]
  ExtractVisibleEntities(drawing_path, view_names, run_id) -> dict  [v1.9 保留]
  ProbePMI(part_path, run_id) -> dict  [v1.9 保留]

输出: addin_status.json / addin_context.json (写入 run_dir/qc)
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# Add-in COM ProgID（C# Add-in 注册后使用）
ADDIN_PROGID = "SwDrawingStudioAddin.AddinAPI"
ADDIN_CLSID = "{B8F3E2A1-7C4D-4E5F-9A6B-1D2E3F4A5B6C}"  # 占位，C# 实现时确定


def _get_sw_app():
    """获取 SolidWorks Application COM 对象"""
    try:
        from app.services.solidworks_global_lock import require_current_job_lock

        guard = require_current_job_lock("sw_addin_client._get_sw_app")
        if not guard.get("ok"):
            raise RuntimeError(
                "blocked_by_solidworks_lock: "
                + json.dumps({
                    "reason": guard.get("reason", ""),
                    "owner": guard.get("owner", {}),
                    "fix_suggestion": guard.get("fix_suggestion", ""),
                }, ensure_ascii=False)
            )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"SolidWorks 全局锁校验失败: {exc}")

    import pythoncom
    import win32com.client as wc
    try:
        return wc.GetActiveObject("SldWorks.Application")
    except Exception:
        try:
            return wc.Dispatch("SldWorks.Application")
        except Exception as e:
            raise RuntimeError(f"无法连接 SolidWorks: {e}")


def _find_addin(sw_app) -> tuple:
    """从 SW Application 查找已注册的 Add-in COM 对象

    Add-in 在 ConnectToSW 时应将自身 COM 对象注册到 ROT (Running Object Table)
    或通过 SW Add-in Manager 暴露 API。

    Returns:
        (addin_object, method): addin_object 为 None 表示未找到
    """
    # 方式 1: 通过 GetAddInObjects (SW Add-in Manager 加载的 Add-in)
    try:
        addins = sw_app.GetAddInObjects()
        for addin in addins:
            try:
                name = str(addin.Name or "")
                if "SwDrawingStudio" in name or "DrawingStudioAddin" in name:
                    return addin, "getaddin_object"
            except Exception:
                continue
    except Exception:
        pass

    # 方式 2: 直接 Dispatch Add-in ProgID，并手动调用 ConnectToSW
    try:
        import win32com.client as wc
        addin = wc.Dispatch(ADDIN_PROGID)
        # 手动连接到 SW（Add-in 未通过 SW Add-in Manager 加载时需要）
        try:
            # 先检查是否已连接
            if not addin.Ping():
                # 调用 ConnectToSW(sw_app, cookie)
                # cookie 任意值即可，仅用于 SW 事件回调标识
                ok = addin.ConnectToSW(sw_app, 88001)
                if not ok:
                    return None, "connect_failed"
        except Exception as e:
            # ConnectToSW 可能已经连接过，忽略错误
            pass
        return addin, "dispatch"
    except Exception:
        pass

    return None, "none"


def ping() -> dict:
    """Ping Add-in，检查是否可用

    Returns:
        {
            "available": bool,
            "method": "getaddin_object" / "dispatch" / "none",
            "sw_running": bool,
            "addin_loaded": bool,
            "ping_result": bool,
            "reason": str,
            "timestamp": str,
        }
    """
    result = {
        "available": False,
        "method": "none",
        "sw_running": False,
        "addin_loaded": False,
        "ping_result": False,
        "reason": "",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    # 检查 SW 是否运行
    try:
        sw = _get_sw_app()
        result["sw_running"] = True
    except Exception as e:
        result["reason"] = f"SolidWorks 未运行: {e}"
        return result

    # 查找 Add-in
    try:
        addin, method = _find_addin(sw)
        if addin is None:
            result["reason"] = "Add-in 未加载（SwDrawingStudioAddin 未在 SW Add-in Manager 中注册）"
            return result
        result["addin_loaded"] = True
        result["method"] = method

        # 调用 Ping
        try:
            ping_ret = addin.Ping()
            result["ping_result"] = bool(ping_ret)
            result["available"] = True
            result["reason"] = "Ping 成功"
        except Exception as e:
            result["reason"] = f"Ping 调用失败: {e}"
    except Exception as e:
        result["reason"] = f"查找 Add-in 异常: {e}"

    return result


def generate_associative_dimensions(
    drawing_path: str,
    part_path: str,
    run_dir: Path,
    run_id: str = "",
) -> dict:
    """调用 Add-in 生成关联尺寸

    Args:
        drawing_path: SLDDRW 绝对路径
        part_path: SLDPRT 绝对路径
        run_dir: run_dir 根目录
        run_id: run_id

    Returns:
        {
            "success": bool,
            "method": str,
            "display_dim_count": int,
            "model_annotations_count": int,
            "visible_entities_count": int,
            "reason": str,
            "timestamp": str,
        }
    """
    result = {
        "success": False,
        "method": "addin",
        "display_dim_count": 0,
        "model_annotations_count": 0,
        "visible_entities_count": 0,
        "reason": "",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    # 确保 drawing_path 为绝对路径
    drawing_path = str(Path(drawing_path).resolve())
    part_path = str(Path(part_path).resolve())

    try:
        sw = _get_sw_app()
    except Exception as e:
        result["reason"] = f"SolidWorks 未运行: {e}"
        return result

    try:
        addin, method = _find_addin(sw)
        if addin is None:
            result["reason"] = "Add-in 未加载"
            result["method"] = "none"
            return result
        result["method"] = method

        # 调用 Add-in 方法
        ret = addin.GenerateAssociativeDimensions(drawing_path, part_path, run_id)
        if isinstance(ret, dict):
            result.update(ret)
        elif isinstance(ret, str):
            try:
                parsed = json.loads(ret)
                result.update(parsed)
            except Exception:
                result["reason"] = f"Add-in 返回非 JSON: {ret[:200]}"
        else:
            result["reason"] = f"Add-in 返回类型异常: {type(ret)}"

        result["success"] = bool(result.get("display_dim_count", 0) > 0 or result.get("model_annotations_count", 0) > 0)

    except Exception as e:
        result["reason"] = f"GenerateAssociativeDimensions 异常: {e}"
        result["method"] = "exception"

    return result


def relink_drawing_references(
    drawing_path: str,
    part_path: str,
    run_dir: Path,
    run_id: str = "",
) -> dict:
    """调用 Add-in 修复 drawing 引用

    Returns:
        {
            "success": bool,
            "method": str,
            "references_before": list,
            "references_after": list,
            "replaced_count": int,
            "reason": str,
            "timestamp": str,
        }
    """
    result = {
        "success": False,
        "method": "addin",
        "references_before": [],
        "references_after": [],
        "replaced_count": 0,
        "reason": "",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    drawing_path = str(Path(drawing_path).resolve())
    part_path = str(Path(part_path).resolve())

    try:
        sw = _get_sw_app()
    except Exception as e:
        result["reason"] = f"SolidWorks 未运行: {e}"
        return result

    try:
        addin, method = _find_addin(sw)
        if addin is None:
            result["reason"] = "Add-in 未加载"
            result["method"] = "none"
            return result
        result["method"] = method

        ret = addin.RelinkDrawingReferences(drawing_path, part_path, run_id)
        if isinstance(ret, dict):
            result.update(ret)
        elif isinstance(ret, str):
            try:
                parsed = json.loads(ret)
                result.update(parsed)
            except Exception:
                result["reason"] = f"Add-in 返回非 JSON: {ret[:200]}"
        else:
            result["reason"] = f"Add-in 返回类型异常: {type(ret)}"

        result["success"] = result.get("replaced_count", 0) > 0

    except Exception as e:
        result["reason"] = f"RelinkDrawingReferences 异常: {e}"
        result["method"] = "exception"

    return result


def extract_visible_entities(
    drawing_path: str,
    view_names: list,
    run_dir: Path,
    run_id: str = "",
) -> dict:
    """调用 Add-in 提取可见实体

    Returns:
        {
            "success": bool,
            "method": str,
            "views_processed": int,
            "edges_count": int,
            "circles_count": int,
            "arcs_count": int,
            "entities": list,
            "reason": str,
            "timestamp": str,
        }
    """
    result = {
        "success": False,
        "method": "addin",
        "views_processed": 0,
        "edges_count": 0,
        "circles_count": 0,
        "arcs_count": 0,
        "entities": [],
        "reason": "",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    drawing_path = str(Path(drawing_path).resolve())

    try:
        sw = _get_sw_app()
    except Exception as e:
        result["reason"] = f"SolidWorks 未运行: {e}"
        return result

    try:
        addin, method = _find_addin(sw)
        if addin is None:
            result["reason"] = "Add-in 未加载"
            result["method"] = "none"
            return result
        result["method"] = method

        # view_names 转 JSON 字符串传给 Add-in
        view_names_json = json.dumps(view_names, ensure_ascii=False)
        ret = addin.ExtractVisibleEntities(drawing_path, view_names_json, run_id)
        if isinstance(ret, dict):
            result.update(ret)
        elif isinstance(ret, str):
            try:
                parsed = json.loads(ret)
                result.update(parsed)
            except Exception:
                result["reason"] = f"Add-in 返回非 JSON: {ret[:200]}"
        else:
            result["reason"] = f"Add-in 返回类型异常: {type(ret)}"

        result["success"] = result.get("views_processed", 0) > 0

    except Exception as e:
        result["reason"] = f"ExtractVisibleEntities 异常: {e}"
        result["method"] = "exception"

    return result


def write_addin_status(run_dir: Path, status: dict) -> Path:
    """写入 addin_status.json"""
    qc_dir = run_dir / "qc"
    qc_dir.mkdir(parents=True, exist_ok=True)
    out_path = qc_dir / "addin_status.json"
    out_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


# ============================================================
# v2.0 Task 1: Add-in 正式化 - 新增公共 API
# ============================================================

def _call_addin_method(method_name: str, sw_app, *args) -> dict:
    """通用 Add-in 方法调用包装

    Args:
        method_name: Add-in COM 方法名
        sw_app: SolidWorks Application COM 对象
        *args: 传递给方法的参数

    Returns:
        dict: 解析后的 JSON 结果
    """
    result = {
        "success": False,
        "method": "addin",
        "reason": "",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    try:
        addin, method = _find_addin(sw_app)
        if addin is None:
            result["reason"] = "Add-in 未加载"
            result["method"] = "none"
            return result
        result["method"] = method

        # 调用 Add-in 方法
        ret = getattr(addin, method_name)(*args)
        if isinstance(ret, dict):
            result.update(ret)
        elif isinstance(ret, str):
            try:
                parsed = json.loads(ret)
                result.update(parsed)
            except Exception:
                result["reason"] = f"Add-in 返回非 JSON: {ret[:200]}"
        else:
            result["reason"] = f"Add-in 返回类型异常: {type(ret)}"

    except Exception as e:
        result["reason"] = f"{method_name} 异常: {e}"
        result["method"] = "exception"

    return result


def probe_context(run_id: str = "") -> dict:
    """v2.0 Task 1: ProbeContext - 探测当前 SW 上下文

    Returns:
        {
            "success": bool,
            "method": str,
            "active_doc": str,
            "active_doc_type": str,
            "sheet": str,
            "view_count": int,
            "sw_version": str,
            "addin_version": str,
            "reason": str,
        }
    """
    try:
        sw = _get_sw_app()
    except Exception as e:
        return {
            "success": False,
            "method": "none",
            "reason": f"SolidWorks 未运行: {e}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    return _call_addin_method("ProbeContext", sw, run_id)


def read_dimensions(drawing_path: str, run_dir: Path = None, run_id: str = "") -> dict:
    """v2.0 Task 1: ReadDimensions - 读取 drawing 中现有尺寸

    Returns:
        {
            "success": bool,
            "method": str,
            "existing_display_dim_count": int,
            "note_dim_count": int,
            "model_associative_dim_count": int,
            "view_dimensions": list,
            "reason": str,
        }
    """
    drawing_path = str(Path(drawing_path).resolve())

    try:
        sw = _get_sw_app()
    except Exception as e:
        return {
            "success": False,
            "method": "none",
            "reason": f"SolidWorks 未运行: {e}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    result = _call_addin_method("ReadDimensions", sw, drawing_path, run_id)

    # 写入 addin_context.json（如果提供了 run_dir）
    if run_dir is not None and result.get("success"):
        try:
            qc_dir = Path(run_dir) / "qc"
            qc_dir.mkdir(parents=True, exist_ok=True)
            out_path = qc_dir / "addin_context.json"
            out_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            result["output_path"] = str(out_path)
        except Exception as e:
            result["write_error"] = str(e)

    return result


def generate_dimensions(
    drawing_path: str,
    part_path: str,
    run_dir: Path = None,
    run_id: str = "",
    policy: dict = None,
) -> dict:
    """v2.0 Task 2: GenerateDimensions - Dimension Engine v2 入口

    Args:
        drawing_path: SLDDRW 绝对路径
        part_path: SLDPRT 绝对路径
        run_dir: run_dir 根目录
        run_id: run_id
        policy: 策略字典（dimension_policy, part_class 等）

    Returns:
        {
            "success": bool,
            "method": str,
            "existing_display_dim_count": int,
            "addin_created_dim_count": int,
            "model_associative_dim_count": int,
            "note_dim_count": int,
            "standard_annotation_count": int,
            "reason": str,
        }
    """
    drawing_path = str(Path(drawing_path).resolve())
    part_path = str(Path(part_path).resolve())
    policy_json = json.dumps(policy or {}, ensure_ascii=False)

    try:
        sw = _get_sw_app()
    except Exception as e:
        return {
            "success": False,
            "method": "none",
            "reason": f"SolidWorks 未运行: {e}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    result = _call_addin_method(
        "GenerateDimensions", sw, drawing_path, part_path, run_id, policy_json
    )

    # 写入 dimension_addin_result.json
    if run_dir is not None:
        try:
            qc_dir = Path(run_dir) / "qc"
            qc_dir.mkdir(parents=True, exist_ok=True)
            out_path = qc_dir / "dimension_addin_result.json"
            out_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            result["output_path"] = str(out_path)
        except Exception as e:
            result["write_error"] = str(e)

    return result


def extract_view_entities(
    drawing_path: str,
    view_names: list = None,
    run_dir: Path = None,
    run_id: str = "",
) -> dict:
    """v2.0 Task 3: ExtractViewEntities - Visible Entity Extractor

    Returns:
        {
            "success": bool,
            "method": str,
            "views_processed": int,
            "total_edges": int,
            "total_faces": int,
            "total_vertices": int,
            "total_circles": int,
            "total_arcs": int,
            "views": list,
            "reason": str,
        }
    """
    drawing_path = str(Path(drawing_path).resolve())
    view_names_json = json.dumps(view_names or [], ensure_ascii=False)

    try:
        sw = _get_sw_app()
    except Exception as e:
        return {
            "success": False,
            "method": "none",
            "reason": f"SolidWorks 未运行: {e}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    result = _call_addin_method(
        "ExtractViewEntities", sw, drawing_path, view_names_json, run_id
    )

    # 写入 view_entities.json
    if run_dir is not None:
        try:
            qc_dir = Path(run_dir) / "qc"
            qc_dir.mkdir(parents=True, exist_ok=True)
            out_path = qc_dir / "view_entities.json"
            out_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            result["output_path"] = str(out_path)
        except Exception as e:
            result["write_error"] = str(e)

    return result


def relink_references(
    drawing_path: str,
    part_path: str,
    run_dir: Path = None,
    run_id: str = "",
) -> dict:
    """v2.0 Task 4: RelinkReferences - 引用修复

    Returns:
        {
            "success": bool,
            "method": str,
            "references_before": list,
            "references_after": list,
            "reference_count_before": int,
            "reference_count_after": int,
            "replaced_count": int,
            "replace_details": list,
            "reason": str,
        }
    """
    drawing_path = str(Path(drawing_path).resolve())
    part_path = str(Path(part_path).resolve())

    try:
        sw = _get_sw_app()
    except Exception as e:
        return {
            "success": False,
            "method": "none",
            "reason": f"SolidWorks 未运行: {e}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    result = _call_addin_method(
        "RelinkReferences", sw, drawing_path, part_path, run_id
    )

    # 写入 docmgr_relink_result.json
    if run_dir is not None:
        try:
            qc_dir = Path(run_dir) / "qc"
            qc_dir.mkdir(parents=True, exist_ok=True)
            out_path = qc_dir / "docmgr_relink_result.json"
            out_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            result["output_path"] = str(out_path)
        except Exception as e:
            result["write_error"] = str(e)

    return result


# ============================================================
# v2.1 Task 1-3: Add-in v3 方法（GenerateDimensionsV3 / SeedPMI / ExtractViewEntitiesV2）
# ============================================================

def generate_dimensions_v3(
    drawing_path: str,
    part_path: str,
    run_dir: Path = None,
    run_id: str = "",
    policy: dict = None,
) -> dict:
    """v2.1 Task 1: GenerateDimensionsV3 - Dimension Engine v3 入口

    策略顺序:
      1. Import PMI / DimXpert
      2. AutoDimension (GetLines2 + SelectByID2 + AddDimension5)
      3. VisibleEntity based dimension (GetLines2 + 外形尺寸)
      4. PMI Seed copied model
      5. Standard annotation

    Returns:
        {
            "success": bool,
            "method": str,
            "engine_version": "v3.0",
            "existing_display_dim_count": int,
            "addin_created_dim_count": int,
            "model_associative_dim_count": int,
            "note_dim_count": int,
            "standard_annotation_count": int,
            "strategy_log": list,
            "reason": str,
        }
    """
    drawing_path = str(Path(drawing_path).resolve())
    part_path = str(Path(part_path).resolve())
    policy_json = json.dumps(policy or {}, ensure_ascii=False)
    run_dir_str = str(run_dir) if run_dir else ""

    try:
        sw = _get_sw_app()
    except Exception as e:
        return {
            "success": False,
            "method": "none",
            "reason": f"SolidWorks 未运行: {e}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    result = _call_addin_method(
        "GenerateDimensionsV3", sw, drawing_path, part_path, run_id, policy_json, run_dir_str
    )

    # 写入 dimension_addin_v3_result.json
    if run_dir is not None:
        try:
            qc_dir = Path(run_dir) / "qc"
            qc_dir.mkdir(parents=True, exist_ok=True)
            out_path = qc_dir / "dimension_addin_v3_result.json"
            out_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            result["output_path"] = str(out_path)
        except Exception as e:
            result["write_error"] = str(e)

    return result


def seed_pmi(
    part_path: str,
    run_dir: Path = None,
    run_id: str = "",
) -> dict:
    """v2.1 Task 3: SeedPMI - PMI Seed Engine 入口

    复制 part 到 run_dir/input_work, 在副本中创建外形 PMI, 返回副本路径

    Returns:
        {
            "success": bool,
            "method": str,
            "seed_part_path": str,
            "seed_dim_count": int,
            "overall_length": float,
            "overall_width": float,
            "overall_height": float,
            "reason": str,
        }
    """
    part_path = str(Path(part_path).resolve())
    run_dir_str = str(run_dir) if run_dir else ""

    try:
        sw = _get_sw_app()
    except Exception as e:
        return {
            "success": False,
            "method": "none",
            "reason": f"SolidWorks 未运行: {e}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    result = _call_addin_method("SeedPMI", sw, part_path, run_id, run_dir_str)

    # 写入 pmi_seed.json
    if run_dir is not None:
        try:
            qc_dir = Path(run_dir) / "qc"
            qc_dir.mkdir(parents=True, exist_ok=True)
            out_path = qc_dir / "pmi_seed.json"
            out_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            result["output_path"] = str(out_path)
        except Exception as e:
            result["write_error"] = str(e)

    return result


def extract_view_entities_v2(
    drawing_path: str,
    view_names: list = None,
    run_dir: Path = None,
    run_id: str = "",
) -> dict:
    """v2.1 Task 2: ExtractViewEntitiesV2 - Visible Entity Extractor v2

    新增 GetLines2 fallback，输出 view_entities_v2.json

    Returns:
        {
            "success": bool,
            "method": str,
            "extractor_version": "v2.1",
            "views_processed": int,
            "total_edges": int,
            "total_lines": int,
            "total_circles": int,
            "total_arcs": int,
            "views_with_getlines2_fallback": int,
            "reason_if_zero": str,
            "views": list,
            "reason": str,
        }
    """
    drawing_path = str(Path(drawing_path).resolve())
    view_names_json = json.dumps(view_names or [], ensure_ascii=False)

    try:
        sw = _get_sw_app()
    except Exception as e:
        return {
            "success": False,
            "method": "none",
            "reason": f"SolidWorks 未运行: {e}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    result = _call_addin_method(
        "ExtractViewEntitiesV2", sw, drawing_path, view_names_json, run_id
    )

    # 写入 view_entities_v2.json
    if run_dir is not None:
        try:
            qc_dir = Path(run_dir) / "qc"
            qc_dir.mkdir(parents=True, exist_ok=True)
            out_path = qc_dir / "view_entities_v2.json"
            out_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            result["output_path"] = str(out_path)
        except Exception as e:
            result["write_error"] = str(e)

    return result


def main():
    """CLI: python sw_addin_client.py <command> [args...]

Commands:
  ping                          - Ping Add-in
  probe_context [run_id]        - ProbeContext [v2.0]
  read_dimensions <drw> [run_id] - ReadDimensions [v2.0]
"""
    import sys
    if len(sys.argv) < 2:
        print("Usage: python sw_addin_client.py ping|probe_context|read_dimensions ...")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "ping":
        result = ping()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif cmd == "probe_context":
        run_id = sys.argv[2] if len(sys.argv) > 2 else ""
        result = probe_context(run_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif cmd == "read_dimensions":
        if len(sys.argv) < 3:
            print("Usage: read_dimensions <drawing_path> [run_id]")
            sys.exit(1)
        drawing_path = sys.argv[2]
        run_id = sys.argv[3] if len(sys.argv) > 3 else ""
        result = read_dimensions(drawing_path, run_id=run_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
