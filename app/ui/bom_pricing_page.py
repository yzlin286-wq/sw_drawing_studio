"""BOM 与核价 页面"""
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableView,
    QFileDialog, QLabel, QMessageBox, QSplitter
)

from app.services.bom_service import extract_bom, write_bom
from app.services.pricing_service import suggest_route, calculate_quote, write_quote


class BomPricingPage(QWidget):
    request_ai_route = Signal(dict)  # 让 main_window 调 LLM

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bom_rows: list[dict] = []
        self._route_rows: list[dict] = []
        self._current_file: Path | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        title = QLabel("<h2>BOM 与核价</h2>")
        layout.addWidget(title)

        btn_row = QHBoxLayout()
        self.btn_open = QPushButton("打开 SLDPRT")
        self.btn_ai_route = QPushButton("AI 工艺建议")
        self.btn_quote = QPushButton("生成报价")
        self.btn_export = QPushButton("导出 CSV/XLSX")
        btn_row.addWidget(self.btn_open)
        btn_row.addWidget(self.btn_ai_route)
        btn_row.addWidget(self.btn_quote)
        btn_row.addWidget(self.btn_export)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        splitter = QSplitter(Qt.Vertical)

        # 上：BOM 表
        self.bom_view = QTableView()
        self.bom_model = QStandardItemModel(0, 8, self)
        self.bom_model.setHorizontalHeaderLabels(["序号","件号","名称","规格","数量","材质","重量(g)","备注"])
        self.bom_view.setModel(self.bom_model)
        splitter.addWidget(self.bom_view)

        # 中：工艺路线表
        self.route_view = QTableView()
        self.route_model = QStandardItemModel(0, 4, self)
        self.route_model.setHorizontalHeaderLabels(["工序","数量","工时(min)","金额(元)"])
        self.route_view.setModel(self.route_model)
        splitter.addWidget(self.route_view)

        # 下：报价摘要
        self.quote_label = QLabel("<i>未生成报价</i>")
        self.quote_label.setWordWrap(True)
        splitter.addWidget(self.quote_label)

        layout.addWidget(splitter, stretch=1)

        self.btn_open.clicked.connect(self._on_open)
        self.btn_ai_route.clicked.connect(self._on_ai_route)
        self.btn_quote.clicked.connect(self._on_quote)
        self.btn_export.clicked.connect(self._on_export)

    def _refresh_bom(self):
        self.bom_model.removeRows(0, self.bom_model.rowCount())
        for r in self._bom_rows:
            row = [QStandardItem(str(r.get(k, ""))) for k in ["序号","件号","名称","规格","数量","材质","重量(g)","备注"]]
            self.bom_model.appendRow(row)

    def _refresh_route(self):
        self.route_model.removeRows(0, self.route_model.rowCount())
        for r in self._route_rows:
            row = [QStandardItem(str(r.get(k, ""))) for k in ["name","qty","minutes","cny"]]
            self.route_model.appendRow(row)

    def _on_open(self):
        file, _ = QFileDialog.getOpenFileName(self, "选择 SLDPRT/SLDASM", "", "SolidWorks (*.SLDPRT *.SLDASM)")
        if not file: return
        try:
            self._current_file = Path(file)
            self._bom_rows = extract_bom(file)
            self._refresh_bom()
            QMessageBox.information(self, "BOM", f"加载 {len(self._bom_rows)} 行 BOM")
        except Exception as e:
            QMessageBox.warning(self, "BOM", f"读取失败：{e}")

    def _on_ai_route(self):
        if not self._bom_rows:
            QMessageBox.warning(self, "工艺", "请先加载 BOM"); return
        # 默认用本地推断；GUI 可选弹出 emit signal 由 LLM 推断
        first = self._bom_rows[0]
        meta = {"类别": first.get("类别", "钣金件"), "weight_g": float(first.get("weight_g") or 0)}
        try:
            self._route_rows = suggest_route(meta)
            self._refresh_route()
        except Exception as e:
            QMessageBox.warning(self, "工艺", f"推断失败：{e}")
        # 可选 emit 让 main_window 接 LLM
        try: self.request_ai_route.emit(meta)
        except Exception: pass

    def _on_quote(self):
        if not self._bom_rows:
            QMessageBox.warning(self, "核价", "请先加载 BOM"); return
        if not self._route_rows:
            self._on_ai_route()
        try:
            result = calculate_quote(self._bom_rows, self._route_rows)
            total = result.get("total_cny", 0)
            br = result.get("breakdown", {})
            self.quote_label.setText(
                f"<h3>总价 ¥{total}</h3>"
                f"<p>材料 ¥{br.get('material_cny',0)} · "
                f"加工 ¥{br.get('process_cny',0)} · "
                f"表面 ¥{br.get('surface_cny',0)} · "
                f"包装 ¥{br.get('packing_cny',0)}</p>"
            )
            QMessageBox.information(self, "核价", f"总价 ¥{total}")
        except Exception as e:
            QMessageBox.warning(self, "核价", f"核价失败：{e}")

    def _on_export(self):
        if not self._bom_rows:
            QMessageBox.warning(self, "导出", "无 BOM 可导出"); return
        if not self._current_file:
            self._current_file = Path.cwd() / "bom"
        out_base = str(self._current_file.with_suffix(""))
        try:
            csv_path, xlsx_path = write_bom(self._bom_rows, out_base)
            if self._route_rows:
                result = calculate_quote(self._bom_rows, self._route_rows)
                js, md = write_quote(result, self._bom_rows, self._route_rows, out_base)
                QMessageBox.information(self, "导出", f"已导出:\n{csv_path}\n{xlsx_path}\n{js}\n{md}")
            else:
                QMessageBox.information(self, "导出", f"已导出:\n{csv_path}\n{xlsx_path}")
        except Exception as e:
            QMessageBox.warning(self, "导出", f"导出失败：{e}")
