"""3D-2D 视觉比对（Spec improve-drawing-scale-titlebar-inspection Task 3）

渲染 3D 模型等轴测视图为 PNG，与 2D 工程图 PNG 一起送 LLM 比对。
"""
from __future__ import annotations
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from app.services.llm_client import LLMClient
from app.services.solidworks_global_lock import require_current_job_lock

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_PNG_DIR = REPO_ROOT / "drw_output" / "model_pngs"


def _render_3d_isometric_png(part_path: str, png_out: str, timeout: int = 60) -> bool:
    """用 SolidWorks COM 渲染 3D 模型等轴测视图为 PNG。
    
    Args:
        part_path: SLDPRT 绝对路径
        png_out: 输出 PNG 路径
        timeout: 超时秒数
    
    Returns:
        True 若 PNG 生成成功且 file_size > 1KB
    """
    part_path = str(Path(part_path).resolve())
    png_out = str(Path(png_out).resolve())
    Path(png_out).parent.mkdir(parents=True, exist_ok=True)
    guard = require_current_job_lock("model_compare.render_3d_isometric_png")
    if not guard.get("ok"):
        print("[model_compare] blocked_by_solidworks_lock: " + json.dumps({
            "reason": guard.get("reason", ""),
            "owner": guard.get("owner", {}),
            "fix_suggestion": guard.get("fix_suggestion", ""),
        }, ensure_ascii=False))
        return False
    
    try:
        import win32com.client
        import pythoncom
        from win32com.client import VARIANT
        pythoncom.CoInitialize()
        
        try:
            sw = win32com.client.GetActiveObject("SldWorks.Application")
        except Exception:
            sw = win32com.client.Dispatch("SldWorks.Application")
        
        sw.Visible = True
        
        # OpenDoc6 outparams 在 pywin32 动态分派下需 VT_BYREF 包装
        errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        warnings = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        
        # OpenDoc6
        doc_type = 1  # swDocPART
        options = 1  # swOpenDocOptions_Silent
        try:
            part = sw.OpenDoc6(part_path, doc_type, options, "", errors, warnings)
        except Exception:
            # 退路：OpenDoc（旧签名）
            part = sw.OpenDoc(part_path, doc_type)
        if part is None:
            return False
        
        # SW typelib 在动态分派下会把方法标成属性，反之亦然
        def _call_or_get(obj, name, *args):
            val = getattr(obj, name)
            if callable(val):
                return val(*args)
            if args:
                try:
                    disp_id = obj._oleobj_.GetIDsOfNames(name)
                    return obj._oleobj_.Invoke(disp_id, 0, 1, True, *args)
                except Exception:
                    return val
            return val
        
        # 设置等轴测视图
        try:
            # swIsometricView = 7
            _call_or_get(part, "ShowNamedView2", "*Isometric", 7)
        except Exception:
            pass
        
        # 适配窗口
        try:
            _call_or_get(part, "ViewZoomtofit2")
        except Exception:
            pass
        
        # 保存为 PNG：SaveAs3 在动态分派下最稳定（无 by-ref 参数）
        # 注意：SaveAs3 即使返回 False，PNG 文件通常仍会生成
        title = ""
        try:
            title = _call_or_get(part, "GetTitle")
        except Exception:
            pass
        
        try:
            part.SaveAs3(png_out, 0, 1)
        except Exception:
            # 退路：Extension.SaveAs with VARIANT
            try:
                ext = part.Extension
                err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                warn = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                ext.SaveAs(png_out, 0, 1, None, err, warn)
            except Exception:
                pass
        
        # 关闭文档（不保存）
        try:
            sw.CloseDoc(title)
        except Exception:
            pass
        
        png_path = Path(png_out)
        return png_path.exists() and png_path.stat().st_size > 1024
        
    except Exception as e:
        print(f"[model_compare] render error: {e}")
        return False


def _extract_json(text: str) -> dict[str, Any] | None:
    """从 LLM 返回文本中提取 JSON"""
    if not text:
        return None
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except Exception:
            pass
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            try:
                fixed = re.sub(r",\s*([}\]])", r"\1", m.group(0))
                return json.loads(fixed)
            except Exception:
                return None
    return None


def compare_model_2d(
    part_path: str,
    slddrw_png_path: str,
    llm: LLMClient,
    model_png_path: str | None = None,
) -> dict[str, Any]:
    """3D-2D 视觉比对。
    
    Args:
        part_path: SLDPRT 路径
        slddrw_png_path: 2D 工程图 PNG 路径
        llm: LLMClient 实例
        model_png_path: 可选，若已渲染过 3D PNG 则直接用；否则自动渲染
    
    Returns:
        {consistency: int 0-100, missing_views: list, structural_diff: str,
         model_png: str, slddrw_png: str, raw_text: str, error: str}
    """
    slddrw_png = Path(slddrw_png_path)
    if not slddrw_png.exists():
        return {"consistency": 0, "missing_views": [], "structural_diff": "",
                "model_png": "", "slddrw_png": str(slddrw_png),
                "raw_text": "", "error": f"2D PNG not found: {slddrw_png_path}"}
    
    # 渲染 3D PNG（若未提供）
    if model_png_path and Path(model_png_path).exists():
        model_png = Path(model_png_path)
    else:
        MODEL_PNG_DIR.mkdir(parents=True, exist_ok=True)
        base = Path(part_path).stem
        model_png = MODEL_PNG_DIR / f"{base}_iso.png"
        ok = _render_3d_isometric_png(part_path, str(model_png))
        if not ok:
            return {"consistency": 0, "missing_views": [], "structural_diff": "",
                    "model_png": "", "slddrw_png": str(slddrw_png),
                    "raw_text": "", "error": "3D PNG 渲染失败"}
    
    # LLM 比对
    sys_prompt = (
        "你是机械制图专家。请对比 3D 模型等轴测视图与 2D 工程图，判断 2D 图是否完整表达了 3D 模型的结构。\n"
        "关注：\n"
        "1. 2D 图是否包含 3D 模型的主要结构特征\n"
        "2. 是否有遗漏的视图（如缺少俯视图/侧视图/剖视图）\n"
        "3. 尺寸标注是否覆盖关键尺寸\n"
        "请严格只输出 JSON。"
    )
    
    user_text = (
        "第 1 张图是 3D 模型等轴测视图，第 2 张图是 2D 工程图。\n"
        "请对比两张图，返回 JSON:\n"
        '{"consistency": <0-100 整数，越高越一致>,'
        '"missing_views": ["缺失的视图名，如 俯视图/剖视图"],'
        '"structural_diff": "<结构差异描述>"}\n'
        "不要输出 JSON 以外的任何字符。"
    )
    
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_text},
    ]
    
    result: dict[str, Any] = {
        "consistency": 0,
        "missing_views": [],
        "structural_diff": "",
        "model_png": str(model_png),
        "slddrw_png": str(slddrw_png),
        "raw_text": "",
        "error": "",
    }
    
    try:
        resp = llm.vision(messages, image_paths=[str(model_png), str(slddrw_png)])
        text = (resp or {}).get("text") or ""
        result["raw_text"] = text
        
        parsed = _extract_json(text)
        if isinstance(parsed, dict):
            try:
                result["consistency"] = max(0, min(100, int(parsed.get("consistency", 0))))
            except Exception:
                result["consistency"] = 0
            mv = parsed.get("missing_views", [])
            if isinstance(mv, list):
                result["missing_views"] = [str(v) for v in mv]
            result["structural_diff"] = str(parsed.get("structural_diff", ""))
        else:
            result["error"] = "LLM 返回无法解析为 JSON"
    except Exception as exc:
        result["error"] = f"LLM 调用异常: {type(exc).__name__}: {exc}"
    
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python model_compare.py <part_path> <slddrw_png_path>")
        sys.exit(1)
    from app.services.llm_client import build_default_client
    llm = build_default_client()
    r = compare_model_2d(sys.argv[1], sys.argv[2], llm)
    print(json.dumps(r, ensure_ascii=False, indent=2))
