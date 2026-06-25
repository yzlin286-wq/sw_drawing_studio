"""测试多种方法在 drawing 上创建尺寸

方法 1: AddDimension2 (检查线段是否选中)
方法 2: Extension.InsertDimension2
方法 3: AddDimension2 with threading timeout
"""
import sys
import time
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))


def test_dimension_methods(drawing_path: str):
    """测试多种尺寸创建方法"""
    import win32com.client

    drawing_path = str(Path(drawing_path).resolve())
    print(f"Drawing: {drawing_path}", flush=True)

    sw = win32com.client.Dispatch("SldWorks.Application")
    try:
        sw.Visible = False
    except Exception:
        pass
    try:
        sw.UserControl = False
    except Exception:
        pass

    # 禁用尺寸输入对话框
    try:
        sw.SetUserPreferenceToggle(8, False)  # swInputDimValOnCreate
        print("Disabled swInputDimValOnCreate", flush=True)
    except Exception as e:
        print(f"SetUserPreferenceToggle failed: {e}", flush=True)

    # 打开 drawing
    try:
        doc = sw.OpenDoc(drawing_path, 3)
    except Exception as e:
        print(f"OpenDoc failed: {e}", flush=True)
        return
    if doc is None:
        print("OpenDoc returned null", flush=True)
        return
    print("Drawing opened", flush=True)

    # 激活 sheet
    try:
        sheet = doc.GetCurrentSheet
        sheet_name = sheet.GetName
        doc.ActivateSheet(sheet_name)
        print(f"Sheet activated: {sheet_name}", flush=True)
    except Exception as e:
        print(f"ActivateSheet failed: {e}", flush=True)
        return

    # 进入草图
    try:
        doc.InsertSketch2(True)
        print("Sketch mode entered", flush=True)
    except Exception as e:
        print(f"InsertSketch2 failed: {e}", flush=True)
        return

    sketch_mgr = doc.SketchManager

    # 画线
    start_x, start_y = 0.1, 0.1
    line_len = 0.05
    try:
        line_obj = sketch_mgr.CreateLine(start_x, start_y, 0, start_x + line_len, start_y, 0)
        print(f"Line created: {line_obj}", flush=True)
    except Exception as e:
        print(f"CreateLine failed: {e}", flush=True)
        return

    # 检查选中状态
    sel_count = 0
    try:
        sel_mgr = doc.SelectionManager
        sel_count = sel_mgr.GetSelectedObjectCount
        print(f"Selected object count after CreateLine: {sel_count}", flush=True)
    except Exception as e:
        print(f"SelectionManager.GetSelectedObjectCount failed: {e}", flush=True)
        try:
            sel_count = doc.GetSelectedObjectCount()
            print(f"GetSelectedObjectCount(): {sel_count}", flush=True)
        except Exception as e2:
            print(f"GetSelectedObjectCount() also failed: {e2}", flush=True)

    # 如果没有选中，尝试显式选中线段
    if not sel_count:
        print("No selection after CreateLine, trying SelectByID2...", flush=True)
        try:
            # SelectByID2(Name, Type, X, Y, Z, AppendToSelection, Callout, SelectOption)
            # 线段类型: "SKETCHSEGMENT"
            doc.SelectByID2("", "SKETCHSEGMENT", start_x + line_len / 2, start_y, 0, False, 0, 0)
            sel_count = doc.GetSelectedObjectCount
            print(f"After SelectByID2: sel_count={sel_count}", flush=True)
        except Exception as e:
            print(f"SelectByID2 failed: {e}", flush=True)

    mid_x = start_x + line_len / 2.0
    dim_y = start_y + 0.02

    # 方法 2: Extension.InsertDimension2
    print("\n--- Method 2: Extension.InsertDimension2 ---", flush=True)
    try:
        ext = doc.Extension
        print(f"Extension obtained: {ext}", flush=True)
        # InsertDimension2(X, Y, Z, DimensionType, Orientation)
        # DimensionType: 0=horizontal, 1=vertical, 2=linear
        dim = ext.InsertDimension2(mid_x, dim_y, 0, 0, 0)
        print(f"Extension.InsertDimension2 returned: {dim}", flush=True)
        if dim is not None:
            print("SUCCESS: Extension.InsertDimension2 created a dimension!", flush=True)
            doc.ClearSelection
            doc.InsertSketch2(True)
            doc.Save
            return True
    except Exception as e:
        print(f"Extension.InsertDimension2 failed: {e}", flush=True)
        import traceback
        traceback.print_exc()

    # 方法 2b: 尝试其他方法名
    print("\n--- Method 2b: Try other dimension method names ---", flush=True)
    for method_name in ["AddDimension", "AddDimension2", "AddDimension3", "AddDimension5"]:
        try:
            method = getattr(doc, method_name)
            print(f"  Found method: {method_name}", flush=True)
        except AttributeError:
            print(f"  Method not found: {method_name}", flush=True)
            continue

    # 方法 3: AddDimension2 直接调用（不用线程，看是否挂起）
    print("\n--- Method 3: AddDimension2 direct call (10s watchdog) ---", flush=True)
    result_holder = {"dim": None, "error": None, "done": False}

    def call_add_dimension():
        try:
            import pythoncom
            pythoncom.CoInitialize()
            result_holder["dim"] = doc.AddDimension2(mid_x, dim_y, 0)
        except Exception as e:
            result_holder["error"] = f"{type(e).__name__}: {e}"
            import traceback
            result_holder["traceback"] = traceback.format_exc()
        finally:
            result_holder["done"] = True
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass

    t = threading.Thread(target=call_add_dimension, daemon=True)
    t.start()
    t.join(timeout=10)

    if not result_holder["done"]:
        print("TIMEOUT: AddDimension2 hung for 10 seconds", flush=True)
        print("AddDimension2 confirmed hanging - SW dialog blocking", flush=True)
    else:
        print(f"AddDimension2 completed: dim={result_holder['dim']}", flush=True)
        if result_holder["error"]:
            print(f"  error: {result_holder['error']}", flush=True)
        if result_holder.get("traceback"):
            print(f"  traceback: {result_holder['traceback'][:500]}", flush=True)
        if result_holder["dim"] is not None:
            print("SUCCESS: AddDimension2 created a dimension!", flush=True)
            try:
                doc.ClearSelection
                doc.InsertSketch2(True)
                doc.Save
            except Exception:
                pass
            return True

    # 方法 4: 直接调用 AddDimension2（主线程，不超时）
    print("\n--- Method 4: AddDimension2 main thread (no timeout) ---", flush=True)
    print("Calling AddDimension2 on main thread...", flush=True)
    try:
        dim = doc.AddDimension2(mid_x, dim_y, 0)
        print(f"AddDimension2 returned: {dim}", flush=True)
        if dim is not None:
            print("SUCCESS: AddDimension2 created a dimension!", flush=True)
            try:
                doc.ClearSelection
                doc.InsertSketch2(True)
                doc.Save
            except Exception:
                pass
            return True
    except Exception as e:
        print(f"AddDimension2 failed: {type(e).__name__}: {e}", flush=True)
        import traceback
        traceback.print_exc()

    # 清理
    try:
        doc.ClearSelection
        doc.InsertSketch2(True)
    except Exception:
        pass

    return False


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "002"
    drw_path = REPO / "3D转2D测试图纸" / f"LB26001-A-04-{target}.SLDDRW"
    success = test_dimension_methods(str(drw_path))
    print(f"\nFinal result: success={success}", flush=True)
