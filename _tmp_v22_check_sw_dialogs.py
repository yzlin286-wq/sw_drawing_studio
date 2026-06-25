"""检查 SW 进程下的对话框窗口"""
import win32gui
import win32process
import win32con

SW_PID = 11524  # 从进程列表获取

dialogs = []

def enum_callback(hwnd, _):
    try:
        if not win32gui.IsWindowVisible(hwnd):
            return
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid != SW_PID:
            return
        title = win32gui.GetWindowText(hwnd)
        cls = win32gui.GetClassName(hwnd)
        if title or cls == "#32770":
            dialogs.append({
                "hwnd": hwnd,
                "title": title,
                "class": cls,
                "pid": pid,
            })
    except Exception:
        pass

win32gui.EnumWindows(enum_callback, None)

print(f"SW PID {SW_PID} 的可见窗口 ({len(dialogs)}):")
for d in dialogs:
    print(f"  hwnd={d['hwnd']} class={d['class']} title={d['title']!r}")
