"""从 PDF 生成 PNG（PyMuPDF 300 DPI）"""
import sys
import time
from pathlib import Path

sys.path.insert(0, r"c:\Users\Vision\Desktop\SW 相关")

from app.services.pdf_render_service import render_pdf_first_page

v5_dir = Path(r"c:\Users\Vision\Desktop\SW 相关\drw_output\v5")

parts = ["LB26001-A-04-024", "LB26001-A-04-040"]

for base in parts:
    pdf = v5_dir / f"{base}_v5.PDF"
    png = v5_dir / f"{base}_v5.PNG"
    if png.exists():
        print(f"{base}: PNG already exists ({png.stat().st_size} bytes)")
        continue
    if not pdf.exists():
        print(f"{base}: PDF not found, skip")
        continue
    print(f"{base}: rendering PNG from PDF...")
    t0 = time.time()
    ok = render_pdf_first_page(pdf, png, dpi=300)
    dt = time.time() - t0
    if ok and png.exists():
        print(f"  -> OK ({dt:.1f}s) {png.stat().st_size} bytes")
    else:
        print(f"  -> FAIL ({dt:.1f}s)")
