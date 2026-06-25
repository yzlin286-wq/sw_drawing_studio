"""使用 DialogGuard 关闭 SW 对话框"""
import sys
import time
sys.path.insert(0, r"c:\Users\Vision\Desktop\SW 相关")

from app.services.dialog_guard import DialogGuard

SW_PID = 11524

guard = DialogGuard(sw_pid=SW_PID, run_dir=None, run_id="v22_dialog_fix")
guard.start()
print(f"DialogGuard started, monitoring PID {SW_PID}")

# 等待 5 秒让 guard 处理对话框
time.sleep(5)
guard.stop(timeout_s=2)

summary = guard.get_summary()
print(f"Dialogs dismissed: {summary['dialogs_dismissed']}")
print(f"Dialogs skipped: {summary['dialogs_skipped']}")
print(f"Total actions: {summary['total_actions']}")
print(f"Dismissed titles: {summary['dismissed_titles']}")
print(f"Log entries: {len(guard.get_log())}")
for entry in guard.get_log():
    print(f"  {entry}")
