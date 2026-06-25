"""案例 2D 图库（Spec validate-real-drawings-with-llm-vision Task 2）

把 3D转2D测试图纸/ 中已有 SLDDRW 渲染成 PNG 基准库，
供 vision_score_with_reference() 对标使用。
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any

from app.services.solidworks_global_lock import require_current_job_lock

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CASE_DIR = REPO_ROOT / "3D转2D测试图纸"
LIB_DIR = REPO_ROOT / "drw_output" / "case_library"


def _render_pdf_to_png(pdf_path: Path, png_out: Path, zoom: float = 2.0) -> bool:
    """用 PyMuPDF 把 PDF 第 1 页渲染成 PNG"""
    try:
        import fitz  # type: ignore
    except Exception:
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
    except Exception:
        return False


def _find_pdf_for_slddrw(slddrw_path: Path) -> Path | None:
    """找 SLDDRW 对应的 PDF（同名 .PDF 或 .pdf）"""
    for ext in [".PDF", ".pdf"]:
        cand = slddrw_path.with_suffix(ext)
        if cand.exists():
            return cand
    return None


def _export_slddrw_to_pdf_via_solidworks(
    slddrw_path: Path, pdf_out: Path
) -> bool:
    """用 SolidWorks COM API 把 SLDDRW 导出成 PDF（PDF 不存在时的兜底）。

    SLDDRW 需要 SolidWorks 才能打开，本函数通过 win32com 调用
    SldWorks.Application 打开工程图并 Extension.SaveAs 导出 PDF。
    """
    guard = require_current_job_lock("case_library.export_slddrw_to_pdf")
    if not guard.get("ok"):
        return False
    try:
        import win32com.client  # type: ignore
        import pythoncom  # type: ignore
        from win32com.client import VARIANT  # type: ignore
    except Exception:
        return False

    sw = None
    doc_opened = False
    title = ""
    try:
        pythoncom.CoInitialize()
        sw = win32com.client.Dispatch("SldWorks.Application")
        sw.Visible = True

        errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        warnings = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        # docType=3 (swDocDRAWING), options=1 (swOpenDocOptions_ReadOnly)
        drw = sw.OpenDoc6(str(slddrw_path), 3, 1, "", errors, warnings)
        if drw is None:
            return False
        doc_opened = True
        try:
            title = drw.GetTitle()
        except Exception:
            title = ""

        pdf_out.parent.mkdir(parents=True, exist_ok=True)
        pdf_data = sw.GetExportFileData(1)  # swExportPdfData
        err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        warn = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        # 即使返回 False，PDF 文件通常仍会生成（err=1 为警告）
        drw.Extension.SaveAs(str(pdf_out), 0, 1, pdf_data, err, warn)
        ok = pdf_out.exists() and pdf_out.stat().st_size > 1024
        return ok
    except Exception:
        return False
    finally:
        # 关闭文档（按 title 或路径）
        if sw is not None and doc_opened:
            try:
                if title:
                    sw.CloseDoc(title)
                else:
                    sw.CloseDoc(str(slddrw_path))
            except Exception:
                pass


def _render_slddrw_to_png_via_solidworks(
    slddrw_path: Path, png_out: Path
) -> bool:
    """SLDDRW 无对应 PDF 时，用 SolidWorks 导出 PDF 再渲染 PNG。"""
    tmp_pdf = png_out.with_suffix(".pdf")
    if not _export_slddrw_to_pdf_via_solidworks(slddrw_path, tmp_pdf):
        return False
    ok = _render_pdf_to_png(tmp_pdf, png_out)
    # 清理临时 PDF
    try:
        if tmp_pdf.exists():
            tmp_pdf.unlink()
    except Exception:
        pass
    return ok


def build_case_library(force: bool = False) -> dict[str, Any]:
    """构建案例图库。

    Args:
        force: True 则强制重新渲染所有 PNG；False 则跳过已存在的

    Returns:
        {"total": int, "rendered": int, "skipped": int, "failed": list, "index_path": str}
    """
    LIB_DIR.mkdir(parents=True, exist_ok=True)

    slddrw_files = sorted(CASE_DIR.glob("*.SLDDRW"))
    # 排除 ~$ 临时文件
    slddrw_files = [f for f in slddrw_files if not f.name.startswith("~$")]

    index: list[dict] = []
    rendered = 0
    skipped = 0
    failed: list[dict] = []

    for slddrw in slddrw_files:
        base = slddrw.stem
        png_out = LIB_DIR / f"{base}.png"

        if png_out.exists() and not force:
            # 已存在，跳过渲染但仍记入 index
            index.append({
                "base_name": base,
                "slddrw_path": str(slddrw),
                "png_path": str(png_out),
                "file_size": png_out.stat().st_size,
            })
            skipped += 1
            continue

        pdf_path = _find_pdf_for_slddrw(slddrw)

        # 优先用已有 PDF 渲染
        if pdf_path is not None:
            ok = _render_pdf_to_png(pdf_path, png_out)
            if ok:
                index.append({
                    "base_name": base,
                    "slddrw_path": str(slddrw),
                    "png_path": str(png_out),
                    "file_size": png_out.stat().st_size,
                    "source": "pdf",
                })
                rendered += 1
                continue
            # PDF 渲染失败，继续尝试 SolidWorks 兜底

        # 无 PDF 或 PDF 渲染失败 → 用 SolidWorks COM 兜底
        ok = _render_slddrw_to_png_via_solidworks(slddrw, png_out)
        if ok:
            index.append({
                "base_name": base,
                "slddrw_path": str(slddrw),
                "png_path": str(png_out),
                "file_size": png_out.stat().st_size,
                "source": "solidworks",
            })
            rendered += 1
        else:
            failed.append({
                "base_name": base,
                "slddrw_path": str(slddrw),
                "pdf_path": str(pdf_path) if pdf_path else "",
                "reason": "no PDF and SolidWorks render failed",
            })

    # 写 index
    index_path = LIB_DIR / "case_index.json"
    index_data = {
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(slddrw_files),
        "rendered": rendered,
        "skipped": skipped,
        "failed_count": len(failed),
        "items": index,
        "failed": failed,
    }
    index_path.write_text(json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "total": len(slddrw_files),
        "rendered": rendered,
        "skipped": skipped,
        "failed": failed,
        "index_path": str(index_path),
    }


def find_case_png(base_name: str) -> str | None:
    """查询某个 base_name 的案例图 PNG 路径。

    Args:
        base_name: SLDPRT/SLDDRW 的 stem（不含扩展名）

    Returns:
        PNG 路径字符串，若不存在返回 None
    """
    if not base_name:
        return None
    # 尝试直接匹配
    png = LIB_DIR / f"{base_name}.png"
    if png.exists() and png.stat().st_size > 1024:
        return str(png)
    return None


def list_case_library() -> dict[str, Any]:
    """读取案例库索引"""
    index_path = LIB_DIR / "case_index.json"
    if not index_path.exists():
        return {"total": 0, "items": []}
    try:
        return json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        return {"total": 0, "items": []}


if __name__ == "__main__":
    result = build_case_library()
    print(f"[case_library] total={result['total']} rendered={result['rendered']} skipped={result['skipped']} failed={len(result['failed'])}")
    print(f"[case_library] index: {result['index_path']}")
    if result['failed']:
        print("[case_library] failed items:")
        for f in result['failed'][:5]:
            print(f"  - {f['base_name']}: {f['reason']}")
