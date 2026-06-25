"""v2.1 Task 8.5 后处理: 为 drw_output/v5/ 中缺少 PNG 的零件生成 PNG

v6 pipeline 直接调用 drw_generate_v6.py，跳过了 run_manager 的 PDF→PyMuPDF 回退，
导致 PNG 缺失。本脚本用 PyMuPDF 从已生成的 PDF 渲染 PNG。
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
V5_DIR = REPO / "drw_output" / "v5"


def render_pdf_to_png(pdf_path: Path, png_out: Path, zoom: float = 2.0) -> bool:
    """用 PyMuPDF 把 PDF 第 1 页渲染成 PNG"""
    try:
        import fitz  # type: ignore
    except Exception:
        print("  [FAIL] PyMuPDF (fitz) 未安装", flush=True)
        return False
    try:
        doc = fitz.open(str(pdf_path))
        if doc.page_count == 0:
            doc.close()
            return False
        page = doc.load_page(0)
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        png_out.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(png_out))
        doc.close()
        return png_out.exists() and png_out.stat().st_size > 1024
    except Exception as e:
        print(f"  [FAIL] 渲染异常: {e}", flush=True)
        return False


def main():
    if not V5_DIR.exists():
        print(f"目录不存在: {V5_DIR}", flush=True)
        sys.exit(1)

    # 找所有 _v5.PDF 文件
    pdfs = sorted(V5_DIR.glob("*_v5.PDF"))
    print(f"找到 {len(pdfs)} 个 PDF 文件", flush=True)

    generated = 0
    skipped = 0
    failed = 0

    for pdf in pdfs:
        png = pdf.with_suffix(".PNG")
        base = pdf.stem  # e.g. LB26001-A-04-015_v5

        if png.exists() and png.stat().st_size > 1024:
            skipped += 1
            continue

        print(f"  生成: {base}.PNG", flush=True)
        if render_pdf_to_png(pdf, png, zoom=2.0):
            generated += 1
            print(f"    [OK] {png.stat().st_size} bytes", flush=True)
        else:
            failed += 1

    print(f"\n=== PNG 生成汇总 ===", flush=True)
    print(f"Total PDF: {len(pdfs)}", flush=True)
    print(f"Generated: {generated}", flush=True)
    print(f"Skipped (已存在): {skipped}", flush=True)
    print(f"Failed: {failed}", flush=True)


if __name__ == "__main__":
    main()
