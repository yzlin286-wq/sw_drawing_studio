from __future__ import annotations

from copy import deepcopy
from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.config.defaults import (
    app_data_dir,
    get_app_config,
    get_llm_config,
    save_yaml,
)
from app.services import LLMClient


PROVIDERS = ["openai", "deepseek", "dashscope", "ollama"]


class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.resize(640, 480)

        self._llm_cfg: dict[str, Any] = deepcopy(get_llm_config() or {})
        self._app_cfg: dict[str, Any] = deepcopy(get_app_config() or {})

        if "providers" not in self._llm_cfg or not isinstance(self._llm_cfg.get("providers"), dict):
            self._llm_cfg["providers"] = {}
        for name in PROVIDERS:
            self._llm_cfg["providers"].setdefault(name, {})

        self.tabs = QTabWidget(self)
        self.tabs.addTab(self._build_model_tab(), "模型")
        self.tabs.addTab(self._build_path_tab(), "路径")
        self.tabs.addTab(self._build_concurrency_tab(), "并发")
        self.tabs.addTab(self._build_experimental_tab(), "实验")

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.button_box.accepted.connect(self._on_save)
        self.button_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs, 1)
        layout.addWidget(self.button_box)

        self._load_provider_to_ui(self.cb_provider.currentText())

    def _build_model_tab(self) -> QWidget:
        w = QWidget()

        self.cb_provider = QComboBox()
        self.cb_provider.addItems(PROVIDERS)
        active = self._llm_cfg.get("active_provider")
        if active in PROVIDERS:
            self.cb_provider.setCurrentText(active)

        self.le_base_url = QLineEdit()
        self.le_api_key = QLineEdit()
        self.le_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.le_model = QLineEdit()
        self.le_vision_model = QLineEdit()
        self.dsb_temperature = QDoubleSpinBox()
        self.dsb_temperature.setRange(0.0, 2.0)
        self.dsb_temperature.setSingleStep(0.1)
        self.dsb_temperature.setDecimals(2)
        self.sb_timeout = QSpinBox()
        self.sb_timeout.setRange(1, 600)

        self.btn_test = QPushButton("测试连接")
        self.lbl_test = QLabel("")
        self.lbl_test.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Provider", self.cb_provider)
        form.addRow("base_url", self.le_base_url)
        form.addRow("api_key", self.le_api_key)
        form.addRow("model", self.le_model)
        form.addRow("vision_model", self.le_vision_model)
        form.addRow("temperature", self.dsb_temperature)
        form.addRow("timeout (秒)", self.sb_timeout)

        test_row = QHBoxLayout()
        test_row.addWidget(self.btn_test)
        test_row.addWidget(self.lbl_test, 1)

        layout = QVBoxLayout(w)
        layout.addLayout(form)
        layout.addLayout(test_row)
        layout.addStretch(1)

        self.cb_provider.currentTextChanged.connect(self._on_provider_changed)
        self.btn_test.clicked.connect(self._on_test_connection)

        return w

    def _build_path_tab(self) -> QWidget:
        w = QWidget()

        self.le_sw_path = QLineEdit(str(self._app_cfg.get("solidworks_path", "")))
        self.le_drwdot = QLineEdit(str(self._app_cfg.get("drwdot_template", "")))
        self.le_output_dir = QLineEdit(str(self._app_cfg.get("output_dir", "")))

        btn_sw = QPushButton("浏览…")
        btn_drw = QPushButton("浏览…")
        btn_out = QPushButton("浏览…")

        btn_sw.clicked.connect(lambda: self._pick_file(self.le_sw_path, "选择 SLDWORKS.exe", "Executable (*.exe)"))
        btn_drw.clicked.connect(lambda: self._pick_file(self.le_drwdot, "选择 drwdot 模板", "Drawing Template (*.drwdot)"))
        btn_out.clicked.connect(lambda: self._pick_dir(self.le_output_dir, "选择输出目录"))

        def row(le: QLineEdit, btn: QPushButton) -> QHBoxLayout:
            h = QHBoxLayout()
            h.addWidget(le, 1)
            h.addWidget(btn)
            return h

        form = QFormLayout()
        form.addRow("solidworks_path", row(self.le_sw_path, btn_sw))
        form.addRow("drwdot_template", row(self.le_drwdot, btn_drw))
        form.addRow("output_dir", row(self.le_output_dir, btn_out))

        layout = QVBoxLayout(w)
        layout.addLayout(form)
        layout.addStretch(1)
        return w

    def _build_concurrency_tab(self) -> QWidget:
        w = QWidget()

        self.sb_max_rounds = QSpinBox()
        self.sb_max_rounds.setRange(1, 20)
        try:
            self.sb_max_rounds.setValue(int(self._app_cfg.get("max_qc_rounds", 3)))
        except Exception:
            self.sb_max_rounds.setValue(3)

        self.sb_vision_min = QSpinBox()
        self.sb_vision_min.setRange(0, 100)
        try:
            self.sb_vision_min.setValue(int(self._app_cfg.get("vision_min_score", 80)))
        except Exception:
            self.sb_vision_min.setValue(80)

        form = QFormLayout()
        form.addRow("max_qc_rounds", self.sb_max_rounds)
        form.addRow("vision_min_score", self.sb_vision_min)

        layout = QVBoxLayout(w)
        layout.addLayout(form)
        layout.addStretch(1)
        return w

    def _build_experimental_tab(self) -> QWidget:
        w = QWidget()

        self.cb_refdoc_relink = QCheckBox("实验性 refdoc 强修（默认关闭，开启后即使失败也不阻断交付）")
        self.cb_refdoc_relink.setChecked(bool(self._app_cfg.get("experimental_refdoc_relink", False)))

        self.cb_relink_strategy = QComboBox()
        for s in ("auto", "pywin32_late", "pywin32_ensure_dispatch", "vba_macro", "dotnet_sidecar"):
            self.cb_relink_strategy.addItem(s)
        cur = str(self._app_cfg.get("refdoc_relink_strategy", "auto"))
        if self.cb_relink_strategy.findText(cur) >= 0:
            self.cb_relink_strategy.setCurrentText(cur)

        # v1.8 Task 6: 实验性 sidecar / vision_qc / v5 开关
        self.cb_disable_sidecar = QCheckBox("禁用 Dimension Sidecar (DISABLE_SIDECAR=1)")
        self.cb_disable_sidecar.setChecked(bool(self._app_cfg.get("disable_sidecar", False)))

        self.cb_disable_vqc2 = QCheckBox("禁用 Vision QC v2 (DISABLE_VISION_QC=1)")
        self.cb_disable_vqc2.setChecked(bool(self._app_cfg.get("disable_vision_qc", False)))

        self.cb_use_v5 = QCheckBox("强制使用 v5 引擎 (USE_V5=1)")
        self.cb_use_v5.setChecked(bool(self._app_cfg.get("use_v5", False)))

        info = QLabel(
            "<i>v1.8 回滚开关：sidecar/vision_qc/v5 均可独立禁用。"
            "SolidWorks 2025 + pywin32 环境下 ReplaceViewModel "
            "可能返回 False；strategy_used 与 attempts 会写入 manifest 的 diagnostics。</i>"
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #777;")

        form = QFormLayout()
        form.addRow(self.cb_refdoc_relink)
        form.addRow("relink strategy", self.cb_relink_strategy)
        form.addRow(self.cb_disable_sidecar)
        form.addRow(self.cb_disable_vqc2)
        form.addRow(self.cb_use_v5)
        form.addRow(info)

        layout = QVBoxLayout(w)
        layout.addLayout(form)
        layout.addStretch(1)
        return w

    def _pick_file(self, le: QLineEdit, title: str, filt: str) -> None:
        path, _ = QFileDialog.getOpenFileName(self, title, le.text(), filt)
        if path:
            le.setText(path)

    def _pick_dir(self, le: QLineEdit, title: str) -> None:
        d = QFileDialog.getExistingDirectory(self, title, le.text())
        if d:
            le.setText(d)

    def _current_provider_cfg(self) -> dict[str, Any]:
        name = self.cb_provider.currentText()
        prov = self._llm_cfg["providers"].get(name)
        if not isinstance(prov, dict):
            prov = {}
            self._llm_cfg["providers"][name] = prov
        return prov

    def _load_provider_to_ui(self, name: str) -> None:
        prov = self._llm_cfg.get("providers", {}).get(name) or {}
        if not isinstance(prov, dict):
            prov = {}
        self.le_base_url.setText(str(prov.get("base_url", "")))
        self.le_api_key.setText(str(prov.get("api_key", "")))
        self.le_model.setText(str(prov.get("model", "")))
        self.le_vision_model.setText(str(prov.get("vision_model", "")))
        try:
            self.dsb_temperature.setValue(float(prov.get("temperature", 0.2)))
        except Exception:
            self.dsb_temperature.setValue(0.2)
        try:
            self.sb_timeout.setValue(int(prov.get("timeout", 60)))
        except Exception:
            self.sb_timeout.setValue(60)
        self.lbl_test.setText("")

    def _save_ui_to_provider(self) -> None:
        prov = self._current_provider_cfg()
        prov["base_url"] = self.le_base_url.text().strip()
        prov["api_key"] = self.le_api_key.text()
        prov["model"] = self.le_model.text().strip()
        prov["vision_model"] = self.le_vision_model.text().strip()
        prov["temperature"] = float(self.dsb_temperature.value())
        prov["timeout"] = int(self.sb_timeout.value())

    def _on_provider_changed(self, name: str) -> None:
        prev = getattr(self, "_active_provider_name", None)
        if prev and prev != name:
            try:
                self._save_ui_to_provider_named(prev)
            except Exception:
                pass
        self._active_provider_name = name
        self._load_provider_to_ui(name)

    def _save_ui_to_provider_named(self, name: str) -> None:
        prov = self._llm_cfg["providers"].setdefault(name, {})
        prov["base_url"] = self.le_base_url.text().strip()
        prov["api_key"] = self.le_api_key.text()
        prov["model"] = self.le_model.text().strip()
        prov["vision_model"] = self.le_vision_model.text().strip()
        prov["temperature"] = float(self.dsb_temperature.value())
        prov["timeout"] = int(self.sb_timeout.value())

    def _on_test_connection(self) -> None:
        provider_cfg = {
            "base_url": self.le_base_url.text().strip(),
            "api_key": self.le_api_key.text(),
            "model": self.le_model.text().strip(),
            "vision_model": self.le_vision_model.text().strip(),
            "temperature": float(self.dsb_temperature.value()),
            "timeout": int(self.sb_timeout.value()),
        }
        self.lbl_test.setText("测试中…")
        self.btn_test.setEnabled(False)
        try:
            client = LLMClient(provider_cfg)
            ok, msg, latency_ms = client.test_connection()
            if ok:
                self.lbl_test.setStyleSheet("color: #2E7D32;")
                self.lbl_test.setText(f"OK · {latency_ms} ms · {msg}")
            else:
                self.lbl_test.setStyleSheet("color: #C62828;")
                self.lbl_test.setText(f"失败 · {latency_ms} ms · {msg}")
        except Exception as exc:
            self.lbl_test.setStyleSheet("color: #C62828;")
            self.lbl_test.setText(f"异常: {type(exc).__name__}: {exc}")
        finally:
            self.btn_test.setEnabled(True)

    def _on_save(self) -> None:
        self._save_ui_to_provider()
        self._llm_cfg["active_provider"] = self.cb_provider.currentText()

        self._app_cfg["solidworks_path"] = self.le_sw_path.text().strip()
        self._app_cfg["drwdot_template"] = self.le_drwdot.text().strip()
        self._app_cfg["output_dir"] = self.le_output_dir.text().strip()
        self._app_cfg["max_qc_rounds"] = int(self.sb_max_rounds.value())
        self._app_cfg["vision_min_score"] = int(self.sb_vision_min.value())
        try:
            self._app_cfg["experimental_refdoc_relink"] = bool(self.cb_refdoc_relink.isChecked())
            self._app_cfg["refdoc_relink_strategy"] = self.cb_relink_strategy.currentText()
            # v1.8 Task 6: 保存实验性开关
            self._app_cfg["disable_sidecar"] = bool(self.cb_disable_sidecar.isChecked())
            self._app_cfg["disable_vision_qc"] = bool(self.cb_disable_vqc2.isChecked())
            self._app_cfg["use_v5"] = bool(self.cb_use_v5.isChecked())
        except Exception:
            pass

        try:
            base = app_data_dir()
            save_yaml(base / "llm.yaml", self._llm_cfg)
            save_yaml(base / "app.yaml", self._app_cfg)
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", f"{type(exc).__name__}: {exc}")
            return

        QMessageBox.information(self, "已保存", f"配置已写入:\n{app_data_dir()}")
        self.accept()
