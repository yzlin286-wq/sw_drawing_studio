from app.services import build_default_client, vision_score, slddrw_to_png
from pathlib import Path

base = Path(r"c:\Users\Vision\Desktop\SW 相关\drw_output\v5\LB26001-A-04-001_v5")
slddrw = str(base.with_suffix(".SLDDRW"))
qcjson = str(base.with_suffix("")) + "_qc.json"
png_path = str(base.with_suffix(".PNG"))

ok = slddrw_to_png(slddrw, png_path)
print("png_render_ok:", ok, "->", png_path)

c = build_default_client()
print("LLM:", c)
result = vision_score(slddrw, qcjson, c)
import json
print(json.dumps(result, ensure_ascii=False, indent=2))
