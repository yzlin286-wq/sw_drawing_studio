"""v2.2 Task 2: 通过 pywin32 直接在 drawing 上创建草图尺寸

v2.1: 使用无边界 _dismiss_dialog_thread 关闭对话框
v2.2: 改用生产级 DialogGuard（PID 过滤 + 精确匹配 + 动作记录）

策略:
  1. 打开 drawing
  2. 激活 sheet
  3. InsertSketch2 进入草图
  4. SketchManager.CreateLine 画线
  5. 启动 DialogGuard（只监控 SW PID 下的"修改"对话框）
  6. AddDimension2 添加尺寸
  7. 停止 DialogGuard
  8. 退出草图
  9. 保存 drawing
"""
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from app.services.solidworks_global_lock import require_current_job_lock


def _blocked_by_lock_result(operation: str, path: str = "") -> dict:
    guard = require_current_job_lock(operation)
    if guard.get("ok"):
        return {}
    return {
        "success": False,
        "status": "blocked_by_solidworks_lock",
        "failure_bucket": "solidworks_lock_conflict",
        "reason": guard.get("reason", "blocked_by_solidworks_lock"),
        "owner": guard.get("owner", {}),
        "fix_suggestion": guard.get("fix_suggestion", "等待当前 CAD job 完成，或手动确认后释放 stale lock"),
        "drawing_path": path,
    }


def _get_sw_pid(sw) -> int:
    """获取 SW 进程 PID（通过窗口标题查找）"""
    try:
        import win32gui
        import win32process

        result = [0]
        def callback(hwnd, _):
            title = win32gui.GetWindowText(hwnd)
            if "SOLIDWORKS" in title:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                result[0] = pid
                return False
            return True

        win32gui.EnumWindows(callback, None)
        return result[0]
    except Exception:
        return 0


def create_sheet_sketch_dimension(drawing_path: str, run_dir: Path = None, run_id: str = "") -> dict:
    """在 drawing sheet 上创建草图尺寸"""
    blocked = _blocked_by_lock_result("sheet_sketch_dimension_service.create_sheet_sketch_dimension", drawing_path)
    if blocked:
        return blocked
    import win32com.client
    import pythoncom

    result = {
        "success": False,
        "method": "pywin32_sheet_sketch",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "drawing_path": drawing_path,
        "addin_created_dim_count": 0,
        "reason": "",
    }

    try:
        print("[sidecar] Dispatching SldWorks.Application...", flush=True)
        sw = win32com.client.Dispatch("SldWorks.Application")
        drawing_path = str(Path(drawing_path).resolve())
        print(f"[sidecar] SW dispatched, drawing: {drawing_path}", flush=True)

        # 设置 SW 为不可见，避免 AddDimension2 弹出尺寸输入对话框
        try:
            sw.Visible = False
        except Exception:
            pass
        try:
            sw.UserControl = False
        except Exception:
            pass
        print("[sidecar] SW set to invisible", flush=True)

        # 检查文档是否已打开
        doc = None
        try:
            doc = sw.GetOpenDocumentByName(drawing_path)
        except Exception:
            doc = None

        if doc is None:
            # 打开 drawing - 使用 OpenDoc6 with proper ref params
            print("[sidecar] Opening drawing via OpenDoc6...", flush=True)
            try:
                errors = 0
                warnings = 0
                doc = sw.OpenDoc6(drawing_path, 3, 1, "", errors, warnings)
                print(f"[sidecar] OpenDoc6 result: doc={doc}, errors={errors}", flush=True)
            except Exception as e:
                print(f"[sidecar] OpenDoc6 failed: {e}, trying OpenDoc...", flush=True)
                # fallback: OpenDoc
                try:
                    doc = sw.OpenDoc(drawing_path, 3)
                except Exception as e:
                    result["reason"] = f"OpenDoc 失败: {e}"
                    return result

        if doc is None:
            result["reason"] = "OpenDoc6/OpenDoc 均返回 null"
            return result

        print("[sidecar] Document opened successfully", flush=True)

        # 激活文档
        try:
            sw.ActivateDoc3(drawing_path, True, 0)
        except Exception:
            pass
        print("[sidecar] Document activated", flush=True)

        # 读取插入前尺寸数
        dim_before = 0
        try:
            sheet = doc.GetCurrentSheet
            views = sheet.GetViews
            if views:
                for view in views:
                    try:
                        disp_dims = view.GetDisplayDimensions
                        if disp_dims:
                            dim_before += len(disp_dims) if not isinstance(disp_dims, int) else disp_dims
                    except Exception:
                        pass
        except Exception:
            pass
        result["dim_before"] = dim_before

        # 激活 sheet
        print("[sidecar] Activating sheet...", flush=True)
        try:
            sheet = doc.GetCurrentSheet
            sheet_name = sheet.GetName
            doc.ActivateSheet(sheet_name)
        except Exception as e:
            result["reason"] = f"ActivateSheet 失败: {e}"
            return result
        print(f"[sidecar] Sheet activated: {sheet_name}", flush=True)

        # 获取第一个 view 的 outline 作为参考位置
        start_x = 0.1
        start_y = 0.1
        line_len = 0.05

        try:
            views = sheet.GetViews
            if views:
                for view in views:
                    try:
                        view_type = view.Type
                        if view_type == 0:
                            continue
                        outline = view.Outline
                        if outline and len(outline) >= 6:
                            min_x = outline[0]
                            min_y = outline[1]
                            max_x = outline[3]
                            max_y = outline[4]
                            start_x = min_x
                            start_y = max_y + 0.03
                            line_len = max_x - min_x
                            if line_len < 0.001:
                                line_len = 0.05
                            break
                    except Exception:
                        continue
        except Exception:
            pass
        print(f"[sidecar] View outline: start=({start_x},{start_y}), len={line_len}", flush=True)

        # 进入草图模式
        print("[sidecar] Entering sketch mode (InsertSketch2)...", flush=True)
        try:
            doc.InsertSketch2(True)
        except Exception as e:
            result["reason"] = f"InsertSketch2 失败: {e}"
            return result
        print("[sidecar] Sketch mode entered", flush=True)

        # 获取 SketchManager
        try:
            sketch_mgr = doc.SketchManager
        except Exception as e:
            result["reason"] = f"SketchManager 获取失败: {e}"
            try:
                doc.InsertSketch2(True)  # 退出草图
            except Exception:
                pass
            return result
        print("[sidecar] SketchManager obtained", flush=True)

        # 画一条水平线
        print(f"[sidecar] Creating line from ({start_x},{start_y}) to ({start_x+line_len},{start_y})...", flush=True)
        try:
            line_obj = sketch_mgr.CreateLine(start_x, start_y, 0, start_x + line_len, start_y, 0)
            if line_obj is None:
                result["reason"] = "CreateLine 返回 null"
                try:
                    doc.InsertSketch2(True)  # 退出草图
                except Exception:
                    pass
                return result
        except Exception as e:
            result["reason"] = f"CreateLine 失败: {e}"
            try:
                doc.InsertSketch2(True)
            except Exception:
                pass
            return result
        print("[sidecar] Line created", flush=True)

        # AddDimension2（CreateLine 后线段应自动选中）
        mid_x = start_x + line_len / 2.0
        dim_y = start_y + 0.02

        # 禁用尺寸创建时的输入对话框 (swInputDimValOnCreate = 8)
        # 这是 AddDimension2 挂起的根本原因 - SW2025 会弹出尺寸值输入对话框
        try:
            sw.SetUserPreferenceToggle(8, False)
            print("[sidecar] Disabled swInputDimValOnCreate", flush=True)
        except Exception as e:
            print(f"[sidecar] SetUserPreferenceToggle failed: {e}", flush=True)

        # v2.2: 使用生产级 DialogGuard 替换无边界 _dismiss_dialog_thread
        # 只监控当前 SW PID 下的"修改"对话框，避免误关其他窗口
        sw_pid = _get_sw_pid(sw)
        print(f"[sidecar] SW PID: {sw_pid}", flush=True)

        from app.services.dialog_guard import DialogGuard
        guard = DialogGuard(sw_pid=sw_pid, run_dir=run_dir, run_id=run_id)
        guard.start()
        print("[sidecar] DialogGuard started (PID-filtered)", flush=True)

        print(f"[sidecar] Calling AddDimension2 at ({mid_x},{dim_y})...", flush=True)
        try:
            dim = doc.AddDimension2(mid_x, dim_y, 0)
            print(f"[sidecar] AddDimension2 returned: {dim}", flush=True)

            # 停止 DialogGuard
            guard.stop(timeout_s=2)
            guard_summary = guard.get_summary()
            result["dialogs_dismissed"] = guard_summary["dialogs_dismissed"]
            result["dialog_titles"] = guard_summary["dismissed_titles"]
            result["dialog_guard_skipped"] = guard_summary["dialogs_skipped"]
            result["dialog_guard_actions"] = guard_summary["total_actions"]

            if dim is not None:
                result["addin_created_dim_count"] = 1
                result["success"] = True
                result["reason"] = "AddDimension2 成功创建尺寸（DialogGuard 自动关闭对话框）"

                # 立即设置尺寸值
                try:
                    dim_value_m = line_len  # 单位：米
                    dim.SystemValue = dim_value_m
                    result["dim_value_set"] = True
                    result["dim_value_mm"] = dim_value_m * 1000.0
                except Exception as e:
                    result["dim_value_set"] = False
                    result["dim_value_error"] = str(e)
            else:
                result["reason"] = "AddDimension2 返回 null"
        except Exception as e:
            guard.stop(timeout_s=2)
            guard_summary = guard.get_summary()
            result["reason"] = f"AddDimension2 失败: {e}"
            result["dialogs_dismissed"] = guard_summary["dialogs_dismissed"]
            result["dialog_titles"] = guard_summary["dismissed_titles"]

        # 保存 DialogGuard 日志
        if run_dir:
            try:
                guard.save_log(run_dir)
            except Exception:
                pass

        # 立即清除选择
        print("[sidecar] Clearing selection...", flush=True)
        try:
            doc.ClearSelection
        except Exception:
            pass

        # 退出草图
        print("[sidecar] Exiting sketch mode...", flush=True)
        try:
            doc.InsertSketch2(True)
        except Exception:
            pass
        print("[sidecar] Sketch exited", flush=True)

        # 读取插入后尺寸数
        dim_after = 0
        try:
            sheet = doc.GetCurrentSheet
            views = sheet.GetViews
            if views:
                for view in views:
                    try:
                        disp_dims = view.GetDisplayDimensions
                        if disp_dims:
                            dim_after += len(disp_dims) if not isinstance(disp_dims, int) else disp_dims
                    except Exception:
                        pass
        except Exception:
            pass
        result["dim_after"] = dim_after
        print(f"[sidecar] dim_after={dim_after}", flush=True)

        # 保存 drawing
        print("[sidecar] Saving drawing...", flush=True)
        try:
            doc.Save
            result["saved"] = True
        except Exception as e:
            result["save_error"] = str(e)
            try:
                errors = 0
                warnings = 0
                doc.Save3(1, errors, warnings)
                result["saved"] = True
            except Exception as e2:
                result["save_error_2"] = str(e2)
                result["saved"] = False
        print(f"[sidecar] Save result: {result.get('saved')}", flush=True)

    except Exception as e:
        result["reason"] = f"异常: {e}"
        result["method"] = "exception"

    # 写入结果
    if run_dir is not None:
        try:
            qc_dir = Path(run_dir) / "qc"
            qc_dir.mkdir(parents=True, exist_ok=True)
            out_path = qc_dir / "sheet_sketch_dimension.json"
            out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            result["output_path"] = str(out_path)
        except Exception as e:
            result["write_error"] = str(e)

    return result


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "002"
    # 从 REPO 根目录查找测试图纸
    test_dir = REPO / "3D转2D测试图纸"
    drw_path = test_dir / f"LB26001-A-04-{target}.SLDDRW"
    run_id = f"sidecar_{target}_{int(time.time())}"
    run_dir = REPO / "drw_output" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"Creating sheet sketch dimension for {target}...")
    print(f"  drw_path: {drw_path}")
    print(f"  exists: {drw_path.exists()}")
    result = create_sheet_sketch_dimension(str(drw_path), run_dir, run_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
