"""annotate_sidecar_service.py — v1.6 Task 2: VBA sidecar 尺寸标注服务

背景：pywin32 动态调用 InsertModelAnnotations3 在 SW2025 下抛
`<unknown>.InsertModelAnnotations3` 异常。改用 VBA 宏（早期绑定）调用
IDrawingDoc.InsertModelAnnotations3，避免 pywin32 的 COM 方法分发问题。

主函数：run_annotate_sidecar(drawing_path, run_dir)
- 设置 ANNOTATE_RESULT_PATH 环境变量
- 用 pywin32 连接 SolidWorks（GetActiveObject 优先）
- 激活工程图文档
- 调用 sw.RunMacro2 执行 VBA 宏
- 读取 annotate_result.json 解析结果
- 失败不得抛异常，返回 success=False
"""
from __future__ import annotations
import os
import re
import json
import time
from pathlib import Path

from app.services.solidworks_global_lock import require_current_job_lock

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MACRO_DIR = REPO_ROOT / "templates" / "macros"


def _parse_annotation_count(msg: str) -> int:
    """从 msg 中解析尺寸数量，失败返回 0。

    VBA 宏返回的 msg 格式：
    - "Inserted 12 annotations"
    - "InsertModelAnnotations3 returned empty"
    - "Err 1234: ..."
    """
    if not msg:
        return 0
    # 优先匹配 "Inserted N annotations"
    m = re.search(r"Inserted\s+(\d+)\s+annotations", msg, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except (ValueError, TypeError):
            return 0
    return 0


def _read_result_json(result_path: Path) -> dict:
    """读取 annotate_result.json，失败返回默认 error dict。"""
    default = {
        "status": "exception",
        "msg": "result json not found or unreadable",
        "annotation_count": 0,
        "macro_path": "",
        "success": False,
    }
    if not result_path.exists():
        default["msg"] = f"result json not found: {result_path}"
        return default
    try:
        # 等待文件写入完成（VBA 宏可能刚关闭文件）
        for _ in range(10):
            try:
                text = result_path.read_text(encoding="utf-8")
                if text.strip():
                    break
            except Exception:
                pass
            time.sleep(0.1)
        else:
            text = result_path.read_text(encoding="utf-8")
        data = json.loads(text)
        status = str(data.get("status", "error"))
        msg = str(data.get("msg", ""))
        return {
            "status": status,
            "msg": msg,
            "annotation_count": _parse_annotation_count(msg),
            "macro_path": "",
            "success": status in ("success", "success_zero"),
        }
    except Exception as exc:
        default["msg"] = f"result json parse failed: {exc}"
        return default


def run_annotate_sidecar(drawing_path: str, run_dir: Path) -> dict:
    """主函数：用 VBA sidecar 调用 InsertModelAnnotations3。

    Args:
        drawing_path: SLDDRW 工程图绝对路径（需已保存到磁盘）
        run_dir: 工作目录，结果写入 run_dir/qc/annotate_result.json

    Returns:
        dict: {
            "status": "success" | "success_zero" | "error" | "sidecar_not_found" | "exception",
            "msg": str,
            "annotation_count": int,  # 从 msg 解析，失败时为 0
            "macro_path": str,
            "success": bool,  # status == "success" or "success_zero"
        }
    """
    result = {
        "status": "exception",
        "msg": "",
        "annotation_count": 0,
        "macro_path": "",
        "success": False,
    }
    guard = require_current_job_lock("annotate_sidecar_service.run_annotate_sidecar")
    if not guard.get("ok"):
        result.update({
            "status": "blocked_by_solidworks_lock",
            "msg": "SolidWorks annotation sidecar requires the active CAD worker lock.",
            "success": False,
            "lock_conflict": guard,
        })
        return result

    try:
        # 1) 定位宏文件：优先 .swp，否则 .bas
        swp_path = MACRO_DIR / "auto_annotate.swp"
        bas_path = MACRO_DIR / "auto_annotate.bas"
        macro_path = ""
        if swp_path.exists():
            macro_path = str(swp_path)
        elif bas_path.exists():
            macro_path = str(bas_path)
        else:
            result["status"] = "sidecar_not_found"
            result["msg"] = f"VBA sidecar not found: {swp_path} / {bas_path}"
            return result
        result["macro_path"] = macro_path

        # 2) 设置 ANNOTATE_RESULT_PATH 环境变量
        try:
            run_dir = Path(run_dir).resolve()
        except Exception:
            run_dir = Path(run_dir)
        qc_dir = run_dir / "qc"
        try:
            qc_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        result_path = qc_dir / "annotate_result.json"
        # 清理旧结果文件
        try:
            if result_path.exists():
                result_path.unlink()
        except Exception:
            pass
        os.environ["ANNOTATE_RESULT_PATH"] = str(result_path)

        # 3) 用 pywin32 连接 SolidWorks（GetActiveObject 优先）
        try:
            import pythoncom
            import win32com.client as wc
            from win32com.client import VARIANT
        except ImportError as exc:
            result["status"] = "exception"
            result["msg"] = f"pywin32 导入失败: {exc}"
            return result

        sw = None
        try:
            sw = wc.GetActiveObject("SldWorks.Application")
        except Exception:
            try:
                sw = wc.Dispatch("SldWorks.Application")
            except Exception as exc:
                result["status"] = "exception"
                result["msg"] = f"连接 SolidWorks 失败: {exc}"
                return result

        if sw is None:
            result["status"] = "exception"
            result["msg"] = "SolidWorks 连接返回 None"
            return result

        # 4) 激活工程图文档
        drawing_path_abs = str(Path(drawing_path).resolve())
        err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        try:
            sw.ActivateDoc3(drawing_path_abs, True, 0, err)
        except Exception:
            # 降级 ActivateDoc2
            try:
                sw.ActivateDoc2(drawing_path_abs, True, err)
            except Exception:
                pass
        # 再降级：用文件名（不含路径）激活
        try:
            drw_title = os.path.basename(drawing_path_abs)
            sw.ActivateDoc3(drw_title, True, 0, err)
        except Exception:
            pass

        # 确认活动文档是工程图
        try:
            active = sw.ActiveDoc
            if active is None:
                result["status"] = "error"
                result["msg"] = "激活后活动文档为 None"
                return result
            # GetType 在 pywin32 中可能是属性或方法，兼容处理
            doc_type = None
            try:
                gt = active.GetType
                if callable(gt):
                    doc_type = gt()
                else:
                    doc_type = gt
            except Exception:
                doc_type = None
            if doc_type != 3:  # swDocDRAWING = 3
                result["status"] = "error"
                result["msg"] = f"活动文档不是工程图 (type={doc_type})"
                return result
        except Exception as exc:
            result["status"] = "error"
            result["msg"] = f"检查活动文档类型失败: {exc}"
            return result

        # 5) 调用 RunMacro2 执行 VBA 宏
        # RunMacro2(FileName, ModuleName, ProcedureName, Options, Errors)
        # Options=1 (swRunMacroDefault), Errors 为 byref int
        run_ok = False
        run_err_msg = ""
        try:
            err_var = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            run_ok = sw.RunMacro2(macro_path, "auto_annotate", "main", 1, err_var)
        except Exception as exc:
            run_err_msg = f"RunMacro2 异常: {exc}"
            # 如果是 .bas 文件，尝试先 LoadFile2 加载
            if macro_path.lower().endswith(".bas"):
                try:
                    # LoadFile2(FileName, LoadOption) — LoadOption=0 (swThisFile)
                    sw.LoadFile2(macro_path, 0)
                    time.sleep(0.5)
                    err_var2 = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                    run_ok = sw.RunMacro2(macro_path, "auto_annotate", "main", 1, err_var2)
                    run_err_msg = ""
                except Exception as exc2:
                    run_err_msg = f"LoadFile2 + RunMacro2 失败: {exc2}"

        if not run_ok and run_err_msg:
            # RunMacro2 返回 False 或抛异常
            result["status"] = "error"
            result["msg"] = run_err_msg if run_err_msg else "RunMacro2 returned False"
            return result

        # 6) 等待并读取 annotate_result.json
        # VBA 宏是同步执行的，RunMacro2 返回后结果应已写入
        time.sleep(0.3)
        json_result = _read_result_json(result_path)
        json_result["macro_path"] = macro_path
        return json_result

    except Exception as exc:
        result["status"] = "exception"
        result["msg"] = f"未预期异常: {exc}"
        return result
