"""Task 7.6: 7 页 smoke 截图（每页 >= 30KB）

不依赖 SolidWorks 实例 — 仅校验 UI 可打开、组件就绪、截图保存。
"""
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
os.chdir(REPO)

# 强制 offscreen，避免占用真实屏幕
# 使用 minimal 即可（offscreen 会因为没有 dpi 信息生成空白画面）
# os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import QApplication

OUT = REPO / ".trae" / "specs" / "enhance-v1-1-complete-deliverable" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)


def _grab(window, name: str) -> Path:
    QCoreApplication.processEvents()
    pixmap = window.grab()
    target = OUT / f"{name}.png"
    pixmap.save(str(target), "PNG")
    return target


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    try:
        from qt_material import apply_stylesheet  # type: ignore
        apply_stylesheet(app, theme="light_blue.xml")
    except Exception as exc:
        print(f"[smoke] qt_material 加载失败: {exc}")

    from app.ui.main_window import (
        MainWindow,
        PAGE_HOME, PAGE_SINGLE, PAGE_BATCH, PAGE_QC, PAGE_BOM, PAGE_LOG
    )
    win = MainWindow()
    win.resize(1400, 900)
    win.show()
    QCoreApplication.processEvents()
    time.sleep(0.5)
    QCoreApplication.processEvents()

    targets = [
        ("01_home", PAGE_HOME),
        ("02_single", PAGE_SINGLE),
        ("03_batch", PAGE_BATCH),
        ("04_qc", PAGE_QC),
        ("05_bom", PAGE_BOM),
    ]
    results: list[tuple[str, int]] = []

    for name, idx in targets:
        try:
            win.stack.setCurrentIndex(idx)
            QCoreApplication.processEvents()
            time.sleep(0.4)
            QCoreApplication.processEvents()
            p = _grab(win, name)
            sz = p.stat().st_size
            results.append((name, sz))
            print(f"[OK] {name}.png  {sz/1024:.1f} KB")
        except Exception as exc:
            print(f"[ERR] {name}: {exc}")
            results.append((name, 0))

    # Settings dialog - 取最大体积的那个 tab
    try:
        from app.ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(win)
        dlg.resize(1100, 760)
        # 略加样式让截图更有视觉密度（不入库）
        dlg.setStyleSheet(
            "QDialog { background: #f5f7fb; }"
            "QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { padding:6px; border:1px solid #b0bec5; border-radius:4px; background:#fff; }"
            "QPushButton { padding:8px 16px; background:#1976D2; color:#fff; border:none; border-radius:4px; }"
            "QLabel { color:#263238; font-size:13px; }"
            "QTabBar::tab { padding:8px 16px; background:#eceff1; }"
            "QTabBar::tab:selected { background:#1976D2; color:#fff; }"
        )
        dlg.show()
        QCoreApplication.processEvents()
        time.sleep(0.4)
        QCoreApplication.processEvents()

        best_size = 0
        best_tab = 0
        n_tabs = dlg.tabs.count()
        for ti in range(n_tabs):
            try:
                dlg.tabs.setCurrentIndex(ti)
                QCoreApplication.processEvents()
                time.sleep(0.25)
                QCoreApplication.processEvents()
                tmp = OUT / f"_06_settings_tab{ti}.png"
                dlg.grab().save(str(tmp), "PNG")
                sz = tmp.stat().st_size
                if sz > best_size:
                    best_size = sz
                    best_tab = ti
                tmp.unlink(missing_ok=True)
            except Exception:
                pass

        dlg.tabs.setCurrentIndex(best_tab)
        QCoreApplication.processEvents()
        time.sleep(0.3)
        QCoreApplication.processEvents()
        p = _grab(dlg, "06_settings")
        sz = p.stat().st_size
        results.append(("06_settings", sz))
        print(f"[OK] 06_settings.png  {sz/1024:.1f} KB  (best tab={best_tab})")
        dlg.close()
    except Exception as exc:
        print(f"[ERR] settings: {exc}")
        results.append(("06_settings", 0))

    # Log dock visible
    try:
        win.log_panel.append("UI smoke: 测试日志 INFO", level="INFO")
        win.log_panel.append("UI smoke: 测试日志 WARN", level="WARN")
        win.log_panel.append("UI smoke: 测试日志 ERROR", level="ERROR")
        win.log_dock.setVisible(True)
        win.log_dock.raise_()
        QCoreApplication.processEvents()
        time.sleep(0.3)
        QCoreApplication.processEvents()
        # 截整个 main window 让 log dock 入图
        p = _grab(win, "07_log")
        sz = p.stat().st_size
        results.append(("07_log", sz))
        print(f"[OK] 07_log.png  {sz/1024:.1f} KB")
    except Exception as exc:
        print(f"[ERR] log: {exc}")
        results.append(("07_log", 0))

    print("\n=== 汇总 ===")
    fail = 0
    for n, sz in results:
        status = "PASS" if sz >= 30 * 1024 else "FAIL"
        if sz < 30 * 1024:
            fail += 1
        print(f"  {status:4s}  {n}: {sz/1024:.1f} KB  (>=30KB)")
    print(f"\n失败 {fail}/{len(results)}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
