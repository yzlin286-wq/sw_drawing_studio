"""持续运行 DialogGuard 监控 SW 对话框

在 v6 pipeline 运行期间持续监控并关闭"修改"对话框
"""
import sys
import time
import threading
sys.path.insert(0, r"c:\Users\Vision\Desktop\SW 相关")

from app.services.dialog_guard import DialogGuard

SW_PID = 11524  # 从进程列表获取

class ContinuousDialogGuard:
    def __init__(self, sw_pid, duration_s=600):
        self.sw_pid = sw_pid
        self.duration_s = duration_s
        self.guard = None
        self._stop = False
        self.total_dismissed = 0
        self.total_actions = 0
        self.all_logs = []

    def run(self):
        start = time.time()
        while not self._stop and (time.time() - start) < self.duration_s:
            try:
                self.guard = DialogGuard(sw_pid=self.sw_pid, run_dir=None, run_id="v22_continuous")
                self.guard.start()
                time.sleep(3)
                self.guard.stop(timeout_s=1)
                summary = self.guard.get_summary()
                self.total_dismissed += summary["dialogs_dismissed"]
                self.total_actions += summary["total_actions"]
                if summary["dialogs_dismissed"] > 0:
                    self.all_logs.extend(self.guard.get_log())
                    print(f"[{time.strftime('%H:%M:%S')}] dismissed {summary['dialogs_dismissed']} dialogs (total: {self.total_dismissed})")
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] guard error: {e}")
            time.sleep(2)  # 间隔 2 秒
        print(f"[{time.strftime('%H:%M:%S')}] ContinuousDialogGuard stopped. Total dismissed: {self.total_dismissed}")

    def stop(self):
        self._stop = True


if __name__ == "__main__":
    guard = ContinuousDialogGuard(SW_PID, duration_s=600)
    try:
        guard.run()
    except KeyboardInterrupt:
        guard.stop()
