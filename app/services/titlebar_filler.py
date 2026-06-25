"""标题栏字段智能填充（Spec harden-drawing-pipeline-quality-v1-4 Task 3）

按优先级合并字段：UI录入 > 文件名解析 > 模板默认 > SLDPRT属性
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import Any


# 标题栏 7 个核心字段
TITLEBAR_FIELDS = ["品名", "图号", "材质", "数量", "表面处理", "类别", "机型"]


def parse_filename(sldprt_path: str) -> dict[str, str]:
    """从文件名解析标题栏字段。

    支持格式：
    - LB26001-A-04-001 → 图号=LB26001-A-04-001, 类别=A, 序号=001
    - XXX-A-001 → 图号=XXX-A-001, 类别=A, 序号=001
    - XXX-001 → 图号=XXX-001, 序号=001
    - XXX → 图号=XXX
    """
    base = Path(sldprt_path).stem
    result: dict[str, str] = {}

    # 图号 = 完整文件名（去后缀）
    result["图号"] = base

    # 尝试解析类别和序号
    # 匹配 XXX-CLASS-NNN 或 XXX-CLASS-NN-NNN 等格式
    parts = base.split("-")
    if len(parts) >= 2:
        # 找字母段作为类别（如 A/B/C）
        for p in parts[1:]:
            if re.match(r"^[A-Z]$", p):
                result["类别"] = p
                break
        # 末段若是纯数字，作为序号
        last = parts[-1]
        if re.match(r"^\d+$", last):
            # 序号不直接填入标题栏字段，但可用于品名推断
            pass

    # 品名默认 = 文件名（可被 overrides 覆盖）
    result["品名"] = base

    return result


def fill_titlebar_fields(
    sldprt_path: str,
    src_props: dict[str, str] | None,
    template: dict[str, Any] | None,
    overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    """按优先级合并标题栏字段。

    优先级（高→低）：
    1. overrides（UI 录入）
    2. 文件名解析
    3. template（模板默认值）
    4. src_props（SLDPRT 自定义属性）

    Args:
        sldprt_path: SLDPRT 文件路径
        src_props: SLDPRT 自定义属性 dict
        template: titlebar_template.yaml 加载的 dict
        overrides: UI 录入的 overrides dict

    Returns:
        7 个字段填充后的 dict
    """
    src_props = src_props or {}
    template = template or {}
    overrides = overrides or {}

    # 文件名解析
    parsed = parse_filename(sldprt_path)

    # 模板字段映射
    tpl_company = template.get("company", {}) or {}
    tpl_drawing = template.get("drawing", {}) or {}
    tpl_technical = template.get("technical", {}) or {}

    result: dict[str, str] = {}

    for field in TITLEBAR_FIELDS:
        # 1. overrides 最高优先级
        if field in overrides and overrides[field]:
            result[field] = str(overrides[field])
            continue
        # 2. 文件名解析
        if field in parsed and parsed[field]:
            result[field] = str(parsed[field])
            continue
        # 3. 模板默认值
        tpl_val = ""
        if field == "品名":
            tpl_val = tpl_drawing.get("product_name", "") or ""
        elif field == "图号":
            tpl_val = tpl_drawing.get("drawing_no", "") or ""
        elif field == "材质":
            tpl_val = tpl_technical.get("material", "") or ""
        elif field == "数量":
            tpl_val = tpl_drawing.get("quantity", "") or "1"
        elif field == "表面处理":
            tpl_val = tpl_technical.get("surface_treatment", "") or ""
        elif field == "类别":
            tpl_val = tpl_drawing.get("category", "") or ""
        elif field == "机型":
            tpl_val = tpl_drawing.get("model", "") or "通用"
        if tpl_val:
            result[field] = str(tpl_val)
            continue
        # 4. SLDPRT 自定义属性
        if field in src_props and src_props[field]:
            result[field] = str(src_props[field])
            continue
        # 5. 兜底空字符串
        result[field] = ""

    return result


if __name__ == "__main__":
    # 自测
    import json
    test_path = r"c:\Users\Vision\Desktop\SW 相关\3D转2D测试图纸\LB26001-A-04-001.SLDPRT"
    parsed = parse_filename(test_path)
    print("parse_filename:", json.dumps(parsed, ensure_ascii=False, indent=2))

    filled = fill_titlebar_fields(
        test_path,
        src_props={"材质": "Q235"},
        template={"company": {"name": "测试公司"}, "drawing": {"designer": "张三"}},
        overrides={"品名": "支架"},
    )
    print("fill_titlebar_fields:", json.dumps(filled, ensure_ascii=False, indent=2))
