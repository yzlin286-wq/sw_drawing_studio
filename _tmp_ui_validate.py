"""UI 验收：代码层面验证 BOM/质检/设置/LLM"""
import sys, os
from pathlib import Path

REPO = Path(r"c:\Users\Vision\Desktop\SW 相关")
sys.path.insert(0, str(REPO))
os.chdir(REPO)

print("=" * 60)
print("[BOM 页 4 按钮验证]")
print("=" * 60)
from app.services.bom_service import extract_bom, write_bom
from app.services.pricing_service import suggest_route, calculate_quote, write_quote
print("extract_bom:", callable(extract_bom))
print("write_bom:", callable(write_bom))
print("suggest_route:", callable(suggest_route))
print("calculate_quote:", callable(calculate_quote))

rows = [{"name": "test", "qty": 1, "weight_g": 100, "material": "Q235"}]
route = suggest_route({"类别": "钣金件", "weight_g": 100})
print("route_len:", len(route))
quote = calculate_quote(rows, route)
print("total_cny:", quote.get("total_cny"))

print()
print("=" * 60)
print("[质检页按钮验证]")
print("=" * 60)
from app.services import vision_score, slddrw_to_png
from app.services.llm_client import build_default_client
print("vision_score callable:", callable(vision_score))
print("slddrw_to_png callable:", callable(slddrw_to_png))
client = build_default_client()
print("llm:", client)

print()
print("=" * 60)
print("[设置对话框 + LLM test_connection]")
print("=" * 60)
import os as _os
_os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    from app.ui.settings_dialog import SettingsDialog
    print("SettingsDialog:", SettingsDialog)
except Exception as e:
    print("SettingsDialog import error:", e)

ok, msg, latency = client.test_connection()
print(f"test_connection: ok={ok}, msg={msg!r}, latency_ms={latency}")
