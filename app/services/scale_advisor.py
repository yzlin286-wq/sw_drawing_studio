"""比例尺视觉辅助判断（Spec improve-drawing-scale-titlebar-inspection Task 1）

用 LLM 视觉模型看生成图 PNG 后判断比例是否合适。
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any

from app.services.llm_client import LLMClient


GB_STANDARD_SCALES = [(5,1),(2,1),(1,1),(1,2),(1,5),(1,10),(1,20),(1,50)]


def is_gb_standard_scale(scale: tuple[int, int] | str) -> bool:
    """判断比例是否为 GB/T 14690 标准值"""
    if isinstance(scale, str):
        m = re.match(r"(\d+)\s*:\s*(\d+)", scale)
        if not m:
            return False
        scale = (int(m.group(1)), int(m.group(2)))
    return scale in GB_STANDARD_SCALES


def advise_scale(png_path: str, current_scale: str, llm: LLMClient) -> dict[str, Any]:
    """用 LLM 视觉模型判断比例是否合适。

    Args:
        png_path: 生成图 PNG 路径
        current_scale: 当前比例，如 "1:2"
        llm: LLMClient 实例

    Returns:
        {reasonable: bool, suggestion: str, score: int 0-100, raw_text: str, error: str}
    """
    p = Path(png_path)
    if not p.exists():
        return {"reasonable": False, "suggestion": "", "score": 0, "raw_text": "", "error": f"PNG not found: {png_path}"}

    sys_prompt = (
        "你是机械制图专家，熟悉 GB/T 14690 比例标准。\n"
        "标准比例：5:1 / 2:1 / 1:1 / 1:2 / 1:5 / 1:10 / 1:20 / 1:50。\n"
        "请看这张工程图 PNG，判断当前比例是否合适：\n"
        "1. 视图是否清晰可读（不太大也不太小）\n"
        "2. 视图是否充分利用图纸幅面\n"
        "3. 尺寸标注是否清晰\n"
        "请严格只输出 JSON。"
    )

    user_text = (
        f"当前比例: {current_scale}\n"
        "请判断比例是否合理，返回 JSON:\n"
        '{"reasonable": <true/false>,'
        '"suggestion": "<建议，如为空则表示无需调整>",'
        '"score": <0-100 整数，越高越合理>}\n'
        "不要输出 JSON 以外的任何字符。"
    )

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_text},
    ]

    result: dict[str, Any] = {
        "reasonable": False,
        "suggestion": "",
        "score": 0,
        "raw_text": "",
        "error": "",
    }

    try:
        resp = llm.vision(messages, image_paths=[str(p)])
        text = (resp or {}).get("text") or ""
        result["raw_text"] = text

        # 解析 JSON
        parsed = _extract_json(text)
        if isinstance(parsed, dict):
            result["reasonable"] = bool(parsed.get("reasonable", False))
            result["suggestion"] = str(parsed.get("suggestion", ""))
            try:
                result["score"] = max(0, min(100, int(parsed.get("score", 0))))
            except Exception:
                result["score"] = 0
        else:
            result["error"] = "LLM 返回无法解析为 JSON"
    except Exception as exc:
        result["error"] = f"LLM 调用异常: {type(exc).__name__}: {exc}"

    return result


def _extract_json(text: str) -> dict[str, Any] | None:
    """从 LLM 返回文本中提取 JSON"""
    if not text:
        return None
    text = text.strip()
    # 尝试 fenced code block
    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except Exception:
            pass
    # 尝试直接解析
    try:
        return json.loads(text)
    except Exception:
        pass
    # 尝试提取第一个 JSON 对象
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


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python scale_advisor.py <png_path> <current_scale>")
        sys.exit(1)
    from app.services.llm_client import build_default_client
    llm = build_default_client()
    r = advise_scale(sys.argv[1], sys.argv[2], llm)
    print(json.dumps(r, ensure_ascii=False, indent=2))
