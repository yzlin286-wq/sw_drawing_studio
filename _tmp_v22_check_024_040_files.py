"""检查 024/040 输出文件状态"""
import os
import time
from pathlib import Path

v5 = Path(r"c:\Users\Vision\Desktop\SW 相关\drw_output\v5")
for base in ["LB26001-A-04-024", "LB26001-A-04-040"]:
    print(f"=== {base} ===")
    for ext in ["SLDDRW", "PDF", "DXF", "PNG"]:
        p = v5 / f"{base}_v5.{ext}"
        if p.exists():
            sz = os.path.getsize(p)
            mt = time.strftime("%H:%M:%S", time.localtime(os.path.getmtime(p)))
            print(f"  {ext}: {sz} bytes, {mt}")
        else:
            print(f"  {ext}: MISSING")
