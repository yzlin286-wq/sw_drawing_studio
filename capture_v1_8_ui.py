"""v1.8 Task 6: UI 2.0 截图验证

启动 UI，截图 6 个页面，保存到 drw_output/ui_v1_8_screenshots/
"""
import sys
import os
from pathlib import Path

# 设置环境变量避免 SW 连接
os.environ["DISABLE_SW_CONNECT"] = "1"

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPixmap

def main():
    app = QApplication(sys.argv)

    # 延迟导入避免 SW 初始化
    from app.ui.main_window import MainWindow

    win = MainWindow()
    win.resize(1280, 800)
    win.show()

    # 等待 UI 渲染
    app.processEvents()

    screenshots_dir = REPO_ROOT / "drw_output" / "ui_v1_8_screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    pages = [
        (0, "01_dashboard.png"),
        (1, "02_single_part.png"),
        (2, "03_batch.png"),
        (3, "04_qc.png"),
        (4, "05_bom.png"),
        (5, "06_settings.png"),
    ]

    def capture_page(page_idx, filename):
        win.stack.setCurrentIndex(page_idx)
        app.processEvents()
        # 对于设置页，打开 SettingsDialog 截图
        if page_idx == 5:
            from app.ui.settings_dialog import SettingsDialog
            dlg = SettingsDialog(win)
            dlg.resize(800, 700)
            # 切换到实验性 tab
            if hasattr(dlg, 'tabs') and dlg.tabs.count() > 3:
                dlg.tabs.setCurrentIndex(3)  # 实验性 tab
            dlg.show()
            app.processEvents()
            QTimer.singleShot(500, lambda: None)
            app.processEvents()
            pix = dlg.grab()
            dlg.close()
        else:
            QTimer.singleShot(500, lambda: None)
            app.processEvents()
            pix = win.grab()
        out_path = screenshots_dir / filename
        pix.save(str(out_path), "PNG")
        size = out_path.stat().st_size
        print(f"  {filename}: {size} bytes {'OK' if size > 30*1024 else 'WARN <30KB'}")

    for idx, fname in pages:
        capture_page(idx, fname)

    print(f"\n截图保存到: {screenshots_dir}")
    win.close()
    app.quit()

if __name__ == "__main__":
    main()
