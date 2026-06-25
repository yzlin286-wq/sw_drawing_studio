"""环境自检 - 16 项 (v2.1: 新增 opencv/ultralytics/OCR/vision_model)

返回结构：
{
  "all_ok": bool,
  "pass": int,
  "warning": int,
  "fail": int,
  "items": [
    {"key": "...", "status": "pass|warning|fail", "msg": "...", "fix": "..."}
  ]
}
"""
from __future__ import annotations
import os
import time
from pathlib import Path

from app.services.solidworks_global_lock import require_current_job_lock

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

SUPPORTED_SW_REVISIONS = ("33.", "32.", "31.")  # SW2025 / 2024 / 2023


def _item(key: str, status: str, msg: str, fix: str = "") -> dict:
    return {"key": key, "status": status, "msg": msg, "fix": fix}


# === 12 检查 ===

def _c1_solidworks() -> dict:
    guard = require_current_job_lock("legacy_health_check._c1_solidworks")
    if not guard.get("ok"):
        return _item(
            "solidworks",
            "warning",
            "Legacy health check skipped: blocked_by_solidworks_lock",
            "Use System Health worker or wait for the active CAD job to release the global lock",
        ), None
    try:
        import win32com.client
        try:
            sw = win32com.client.GetActiveObject("SldWorks.Application")
            return _item("solidworks", "pass", "SolidWorks 已连接", ""), sw
        except Exception:
            return _item("solidworks", "fail", "SolidWorks 未启动或不可连接", "请先启动 SolidWorks 2025"), None
    except Exception as e:
        return _item("solidworks", "fail", f"pywin32 不可用: {e}", "请安装 pywin32: pip install pywin32"), None


def _c2_sw_revision(sw) -> dict:
    if sw is None:
        return _item("sw_revision", "warning", "无法读取（SolidWorks 未连接）", "先解决 solidworks 项")
    try:
        try: rev = str(sw.RevisionNumber())
        except Exception: rev = str(sw.RevisionNumber)
        return _item("sw_revision", "pass", f"RevisionNumber = {rev}", "")
    except Exception as e:
        return _item("sw_revision", "warning", f"读取失败: {e}", "")


def _c3_sw_revision_supported(sw) -> dict:
    if sw is None:
        return _item("sw_revision_supported", "warning", "未连接 SW，跳过版本检查", "")
    try:
        try: rev = str(sw.RevisionNumber())
        except Exception: rev = str(sw.RevisionNumber)
        if any(rev.startswith(p) for p in SUPPORTED_SW_REVISIONS):
            return _item("sw_revision_supported", "pass", f"版本 {rev} 在支持列表内", "")
        return _item("sw_revision_supported", "warning", f"版本 {rev} 不在已知支持列表 {SUPPORTED_SW_REVISIONS}", "建议升级到 SW 2024+")
    except Exception as e:
        return _item("sw_revision_supported", "warning", f"读取失败: {e}", "")


def _c4_template() -> dict:
    cands = [REPO_ROOT / "templates" / "gb_a4_landscape.DRWDOT",
             REPO_ROOT / "templates" / "gb_a4_landscape.drwdot"]
    for c in cands:
        if c.exists():
            sz = c.stat().st_size
            if sz > 10 * 1024:
                return _item("template", "pass", f"{c.name} ({sz/1024:.1f} KB)", "")
            return _item("template", "fail", f"{c.name} 文件过小 ({sz} bytes)", "重新构造模板")
    return _item("template", "fail", "templates/gb_a4_landscape.DRWDOT 不存在", "运行 templates/build_drwdot.py")


def _c5_macro_bas() -> dict:
    bas = REPO_ROOT / "templates" / "macros" / "auto_section.bas"
    if bas.exists():
        return _item("macro_bas", "pass", f"auto_section.bas 就绪", "")
    return _item("macro_bas", "fail", "auto_section.bas 缺失", "回滚 templates/macros/")


def _c6_macro_swp() -> dict:
    swp = REPO_ROOT / "templates" / "macros" / "auto_section.swp"
    if swp.exists() and swp.stat().st_size > 1000:
        return _item("macro_swp", "pass", f"auto_section.swp 就绪", "")
    return _item("macro_swp", "warning", "auto_section.swp 不存在",
                 "可选：在 SolidWorks VBA IDE 中打开 .bas 后另存为 .swp")


def _c7_output_dir() -> dict:
    out = REPO_ROOT / "drw_output"
    try:
        out.mkdir(parents=True, exist_ok=True)
        probe = out / ".health_probe.tmp"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return _item("output_dir", "pass", f"{out} 可写", "")
    except Exception as e:
        return _item("output_dir", "fail", f"输出目录不可写: {e}", "检查权限")


def _c8_chinese_path_support() -> dict:
    try:
        out = REPO_ROOT / "drw_output"
        out.mkdir(parents=True, exist_ok=True)
        probe = out / ".中文测试_probe.tmp"
        probe.write_text("中文 ok", encoding="utf-8")
        content = probe.read_text(encoding="utf-8")
        probe.unlink(missing_ok=True)
        if "中文" in content:
            return _item("chinese_path_support", "pass", "中文/空格路径支持正常", "")
        return _item("chinese_path_support", "warning", "中文路径读写不一致", "")
    except Exception as e:
        return _item("chinese_path_support", "warning", f"中文路径测试失败: {e}",
                     "建议系统区域设置开启 Unicode UTF-8 支持")


def _c9_v6_generator() -> dict:
    v6 = REPO_ROOT / ".trae" / "specs" / "build-v6-and-validate-exe-ui" / "drw_generate_v6.py"
    qc6 = REPO_ROOT / ".trae" / "specs" / "build-v6-and-validate-exe-ui" / "drw_qc_loop_v6.py"
    if v6.exists() and qc6.exists():
        return _item("v6_generator", "pass", "v6 出图脚本就绪", "")
    return _item("v6_generator", "fail", "v6 出图脚本缺失",
                 "回滚 .trae/specs/build-v6-and-validate-exe-ui/")


def _c10_v5_fallback() -> dict:
    v5 = REPO_ROOT / ".trae" / "specs" / "enforce-drawing-quality" / "drw_generate_v5.py"
    qc5 = REPO_ROOT / ".trae" / "specs" / "enforce-drawing-quality" / "drw_qc_loop.py"
    if v5.exists() and qc5.exists():
        return _item("v5_fallback", "pass", "v5 回退脚本就绪", "")
    return _item("v5_fallback", "warning", "v5 回退缺失（v6 失败时无 fallback）",
                 "回滚 .trae/specs/enforce-drawing-quality/")


def _c11_db_readable() -> dict:
    needs = [
        REPO_ROOT / "libs" / "standard_parts.db",
        REPO_ROOT / "libs" / "process" / "process.db",
        REPO_ROOT / "libs" / "pricing" / "rules.yaml",
    ]
    missing = [p for p in needs if not p.exists()]
    if missing:
        return _item("db_readable", "fail",
                     f"缺失: {', '.join(p.name for p in missing)}",
                     "运行 libs/standard_parts/build_db.py 与 libs/process/seed.py")
    try:
        import sqlite3
        for db in [needs[0], needs[1]]:
            con = sqlite3.connect(str(db))
            con.execute("SELECT 1").fetchone()
            con.close()
        return _item("db_readable", "pass", "标准件/工艺/报价 数据可读", "")
    except Exception as e:
        return _item("db_readable", "fail", f"SQLite 读取失败: {e}", "重建数据库")


def _c12_llm() -> dict:
    try:
        from app.services.llm_client import build_default_client
    except Exception as e:
        return _item("llm", "warning", f"llm_client 导入失败: {e}", "检查 app/services/llm_client.py")
    try:
        c = build_default_client()
        if not c:
            return _item("llm", "warning", "未配置 LLM provider", "在设置中配置 LLM")
        return _item("llm", "pass", f"配置就绪: {c.model}", "")
    except Exception as e:
        return _item("llm", "warning", f"LLM 配置错误: {e}", "")


# === v2.1 新增 Vision QC 依赖检查 ===

def _c13_opencv() -> dict:
    """OpenCV (cv2) - Vision QC v3 production mode 必需"""
    try:
        import cv2
        ver = getattr(cv2, "__version__", "unknown")
        return _item("opencv", "pass", f"cv2 {ver} 可用", "")
    except ImportError:
        return _item("opencv", "warning",
                     "opencv-python 未安装，Vision QC v3 将 fallback",
                     "pip install opencv-python")
    except Exception as e:
        return _item("opencv", "warning", f"cv2 导入异常: {e}",
                     "pip install opencv-python")


def _c14_ultralytics() -> dict:
    """ultralytics (YOLO) - Vision QC v3 OBB 检测必需"""
    try:
        import ultralytics
        ver = getattr(ultralytics, "__version__", "unknown")
        # 进一步尝试加载 YOLO 类
        from ultralytics import YOLO  # noqa: F401
        return _item("ultralytics", "pass", f"ultralytics {ver} 可用", "")
    except ImportError:
        return _item("ultralytics", "warning",
                     "ultralytics 未安装，YOLO OBB 检测将 fallback",
                     "pip install ultralytics")
    except Exception as e:
        return _item("ultralytics", "warning", f"ultralytics 导入异常: {e}",
                     "pip install ultralytics")


def _c15_ocr() -> dict:
    """OCR 引擎 - 工程图图号/文字识别必需，支持 paddleocr/easyocr/pytesseract"""
    engines = []
    # 1. paddleocr
    try:
        import paddleocr  # noqa: F401
        engines.append("paddleocr")
    except Exception:
        pass
    # 2. easyocr
    try:
        import easyocr  # noqa: F401
        engines.append("easyocr")
    except Exception:
        pass
    # 3. pytesseract (需要 tesseract 可执行文件)
    try:
        import pytesseract
        # 尝试获取版本以验证 tesseract 可执行
        try:
            ver = pytesseract.get_tesseract_version()
            engines.append(f"pytesseract({ver})")
        except Exception:
            # pytesseract 模块存在但 tesseract 可执行未安装
            engines.append("pytesseract(module-only)")
    except Exception:
        pass
    # 4. PyMuPDF 文本提取（fitz）作为基础 fallback
    fitz_ok = False
    try:
        import fitz  # noqa: F401
        fitz_ok = True
    except Exception:
        pass

    if engines:
        extras = " + fitz" if fitz_ok else ""
        return _item("ocr", "pass",
                     f"OCR 引擎: {', '.join(engines)}{extras}", "")
    if fitz_ok:
        return _item("ocr", "warning",
                     "仅 PyMuPDF(fitz) 可用，OCR 精度受限",
                     "pip install paddleocr 或 easyocr 或 pytesseract")
    return _item("ocr", "warning",
                 "无可用 OCR 引擎，Vision QC v3 文字识别将 fallback",
                 "pip install paddleocr (推荐) 或 easyocr 或 pytesseract")


def _c16_vision_model() -> dict:
    """视觉模型权重/ONNX - YOLO OBB 模型文件检查"""
    # 1. 检查 ultralytics YOLO 默认权重
    yolo_weights_candidates = [
        REPO_ROOT / "models" / "yolo_drawing_obb.pt",
        REPO_ROOT / "models" / "yolov8n-obb.pt",
        REPO_ROOT / "models" / "yolov8n.pt",
        REPO_ROOT / "app" / "models" / "yolo_drawing_obb.pt",
    ]
    found_weights = [p for p in yolo_weights_candidates if p.exists()]

    # 2. 检查 ONNX runtime
    onnx_ok = False
    try:
        import onnxruntime  # noqa: F401
        onnx_ok = True
    except Exception:
        pass

    # 3. 检查 ultralytics 是否可用（决定 vision_model 是否有意义）
    ultralytics_ok = False
    try:
        import ultralytics  # noqa: F401
        ultralytics_ok = True
    except Exception:
        pass

    if found_weights and ultralytics_ok:
        return _item("vision_model", "pass",
                     f"YOLO 权重: {found_weights[0].name}" +
                     (" + onnxruntime" if onnx_ok else ""), "")
    if found_weights and not ultralytics_ok:
        return _item("vision_model", "warning",
                     f"权重存在 {found_weights[0].name} 但 ultralytics 未安装",
                     "pip install ultralytics")
    if not found_weights and ultralytics_ok:
        return _item("vision_model", "warning",
                     "ultralytics 已安装但无自定义权重，将使用 COCO 预训练",
                     "训练 YOLO OBB 模型并放置到 models/yolo_drawing_obb.pt")
    if onnx_ok:
        return _item("vision_model", "warning",
                     "onnxruntime 可用但无模型权重",
                     "放置 YOLO 权重到 models/yolo_drawing_obb.pt")
    return _item("vision_model", "warning",
                 "无视觉模型权重，Vision QC v3 将使用规则+LLM fallback",
                 "训练 YOLO OBB 模型或放置权重到 models/")


def run_health_check(test_llm_connection: bool = False) -> dict:
    """执行 16 项环境自检 (v2.1: 新增 opencv/ultralytics/OCR/vision_model)"""
    sw_item, sw = _c1_solidworks()
    items = [
        sw_item,
        _c2_sw_revision(sw),
        _c3_sw_revision_supported(sw),
        _c4_template(),
        _c5_macro_bas(),
        _c6_macro_swp(),
        _c7_output_dir(),
        _c8_chinese_path_support(),
        _c9_v6_generator(),
        _c10_v5_fallback(),
        _c11_db_readable(),
        _c12_llm(),
        # v2.1 新增 Vision QC 依赖检查
        _c13_opencv(),
        _c14_ultralytics(),
        _c15_ocr(),
        _c16_vision_model(),
    ]
    pass_n = sum(1 for it in items if it["status"] == "pass")
    warn_n = sum(1 for it in items if it["status"] == "warning")
    fail_n = sum(1 for it in items if it["status"] == "fail")
    return {
        "all_ok": fail_n == 0,
        "pass": pass_n,
        "warning": warn_n,
        "fail": fail_n,
        "total": len(items),
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "items": items,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run_health_check(), ensure_ascii=False, indent=2))
