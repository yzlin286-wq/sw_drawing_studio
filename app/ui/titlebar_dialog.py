"""标题栏字段录入对话框（Spec harden-drawing-pipeline-quality-v1-4 Task 3）

用户可在出图前手动填写品名/图号/材质/数量/表面处理/类别/机型等字段。
"""
from __future__ import annotations
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QDialogButtonBox, QLabel, QGroupBox,
)

from app.services.titlebar_filler import TITLEBAR_FIELDS


class TitleBarDialog(QDialog):
    """标题栏字段录入对话框"""

    def __init__(self, sldprt_path: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("标题栏字段录入")
        self.setModal(True)
        self.setMinimumWidth(420)

        self._sldprt_path = sldprt_path
        self._line_edits: dict[str, QLineEdit] = {}

        layout = QVBoxLayout(self)

        # 提示
        info_label = QLabel(
            f"源文件: {sldprt_path or '(未选择)'}\n"
            "填写字段后点击“确定”，留空字段将自动从文件名/模板/SLDPRT属性填充。\n"
            "点击“跳过”则全部使用自动填充。"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # 字段输入组
        group = QGroupBox("标题栏字段")
        form = QFormLayout(group)
        for field in TITLEBAR_FIELDS:
            le = QLineEdit()
            le.setPlaceholderText(f"留空则自动填充 {field}")
            self._line_edits[field] = le
            form.addRow(f"{field}:", le)
        layout.addWidget(group)

        # 按钮
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal, self,
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("确定")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("跳过")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_overrides(self) -> dict[str, str]:
        """返回用户填写的 overrides dict（空字符串字段不包含）"""
        result: dict[str, str] = {}
        for field, le in self._line_edits.items():
            text = le.text().strip()
            if text:
                result[field] = text
        return result


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    dlg = TitleBarDialog(r"c:\Users\Vision\Desktop\SW 相关\3D转2D测试图纸\LB26001-A-04-001.SLDPRT")
    if dlg.exec() == QDialog.DialogCode.Accepted:
        print("overrides:", dlg.get_overrides())
    else:
        print("用户跳过")
