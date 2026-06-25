"""测试 AddDimension2 + 对话框自动关闭

策略:
  1. 启动后台线程监控 SW 对话框
  2. 主线程调用 AddDimension2
  3. 后台线程发现对话框后发送 Enter 键关闭
  4. AddDimension2 返回
"""
import sys
import time
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))


def dismiss_dialog_thread(stop_event, result_holder):
    """后台线程：监控并关闭 SW 对话框"""
    try:
        import win32gui
        import win32con
        import ctypes
    except ImportError:
        result_holder["dialog_error"] = "win32gui not available"
        return

    result_holder["dialogs_dismissed"] = 0
    result_holder["dialog_titles"] = []

    while not stop_event.is_set():
        try:
            # 枚举所有窗口
            def enum_callback(hwnd, _):
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                try:
                    title = win32gui.GetWindowText(hwnd)
                    if not title:
                        return True
                    # 查找尺寸输入对话框
                    # SW 对话框标题可能包含: "修改", "尺寸", "Dimension", "Modify", "输入"
                    keywords = ["修改", "尺寸", "Dimension", "Modify", "输入", "Input"]
                    for kw in keywords:
                        if kw in title:
                            result_holder["dialog_titles"].append(title)
                            # 发送 Enter 键关闭对话框
                            win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
                            win32gui.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_RETURN, 0)
                            result_holder["dialogs_dismissed"] += 1
                            break
                except Exception:
                    pass
                return True

            win32gui.EnumWindows(enum_callback, None)
        except Exception:
            pass
        time.sleep(0.2)  # 200ms 轮询


def test_with_dialog_dismissal(drawing_path: str):
    """测试 AddDimension2 + 对话框自动关闭"""
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
        return False
    if doc is None:
        print("OpenDoc returned null", flush=True)
        return False
    print("Drawing opened", flush=True)

    # 激活 sheet
    try:
        sheet = doc.GetCurrentSheet
        sheet_name = sheet.GetName
        doc.ActivateSheet(sheet_name)
        print(f"Sheet activated: {sheet_name}", flush=True)
    except Exception as e:
        print(f"ActivateSheet failed: {e}", flush=True)
        return False

    # 进入草图
    try:
        doc.InsertSketch2(True)
        print("Sketch mode entered", flush=True)
    except Exception as e:
        print(f"InsertSketch2 failed: {e}", flush=True)
        return False

    sketch_mgr = doc.SketchManager

    # 画线
    start_x, start_y = 0.1, 0.1
    line_len = 0.05
    try:
        line_obj = sketch_mgr.CreateLine(start_x, start_y, 0, start_x + line_len, start_y, 0)
        print(f"Line created: {line_obj}", flush=True)
    except Exception as e:
        print(f"CreateLine failed: {e}", flush=True)
        return False

    mid_x = start_x + line_len / 2.0
    dim_y = start_y + 0.02

    # 启动对话框关闭线程
    stop_event = threading.Event()
    result_holder = {"dialogs_dismissed": 0, "dialog_titles": []}
    dismiss_thread = threading.Thread(
        target=dismiss_dialog_thread,
        args=(stop_event, result_holder),
        daemon=True,
    )
    dismiss_thread.start()
    print("Dialog dismisser thread started", flush=True)

    # 调用 AddDimension2（主线程）
    print(f"Calling AddDimension2 at ({mid_x},{dim_y})...", flush=True)
    try:
        dim = doc.AddDimension2(mid_x, dim_y, 0)
        print(f"AddDimension2 returned: {dim}", flush=True)

        # 停止对话框关闭线程
        stop_event.set()
        dismiss_thread.join(timeout=2)

        print(f"Dialogs dismissed: {result_holder['dialogs_dismissed']}", flush=True)
        print(f"Dialog titles: {result_holder['dialog_titles']}", flush=True)

        if dim is not None:
            print("SUCCESS: AddDimension2 created a dimension!", flush=True)
            try:
                dim.SystemValue = line_len  # 设置尺寸值
                print(f"Dimension value set to {line_len}m", flush=True)
            except Exception as e:
                print(f"Set dimension value failed: {e}", flush=True)
            try:
                doc.ClearSelection
                doc.InsertSketch2(True)
                doc.Save
                print("Drawing saved", flush=True)
            except Exception as e:
                print(f"Save failed: {e}", flush=True)
            return True
        else:
            print("AddDimension2 returned null", flush=True)
            try:
                doc.ClearSelection
                doc.InsertSketch2(True)
            except Exception:
                pass
            return False
    except Exception as e:
        print(f"AddDimension2 failed: {type(e).__name__}: {e}", flush=True)
        stop_event.set()
        dismiss_thread.join(timeout=2)
        print(f"Dialogs dismissed: {result_holder['dialogs_dismissed']}", flush=True)
        print(f"Dialog titles: {result_holder['dialog_titles']}", flush=True)
        try:
            doc.ClearSelection
            doc.InsertSketch2(True)
        except Exception:
            pass
        return False


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "002"
    drw_path = REPO / "3D转2D测试图纸" / f"LB26001-A-04-{target}.SLDDRW"
    success = test_with_dialog_dismissal(str(drw_path))
    print(f"\nFinal result: success={success}", flush=True)
