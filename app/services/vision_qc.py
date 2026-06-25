from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from app.services.llm_client import LLMClient


GB_RULES_BRIEF = """\
中国 GB 制图规范摘要（用于打分参考）：
1. 图纸幅面 GB/T 14689：A4 297×210（横）或 210×297（纵），图框线粗 0.7mm，
   标题栏置于右下角；第一角投影符号位于标题栏正上方。
2. 比例 GB/T 14690：使用标准比例 5:1 / 2:1 / 1:1 / 1:2 / 1:5 / 1:10 / 1:20，
   不允许 1:3 / 1:4 / 1:7 等非标准值；同张图原则同比例。
3. 字体 GB/T 14691：长仿宋体，字高 3.5/5/7/10mm，标题栏字高 ≥ 5mm。
4. 视图 GB/T 17452 + 4458.4：第一角投影；主视图 + 必要俯/左视图 + 剖视。
5. 尺寸标注 GB/T 4458.4：尺寸线粗 0.25mm，尺寸界线伸出尺寸线 2-3mm，
   箭头长度 ≈ 字高，倾斜 15°-20°；同方向尺寸优先共线。
6. 表面粗糙度 GB/T 131-2006：Ra 标注在轮廓线或延伸线上，符号开口背离尺寸线；
   全图统一时在标题栏右上角统一标注 “其余 Ra=…”。
7. 形位公差 GB/T 1182-2008：公差框格 + 基准三角符号；基准代号大写字母。
8. 一般公差 GB/T 1804-m：未注线性尺寸 ±0.1 ~ ±0.5（按 m 级）。
9. 注释栏：技术要求标注于标题栏左侧或图纸下方，逐条以阿拉伯数字编号。
10. 标题栏：必含 零件名称 / 零件号 / 材料 / 比例 / 投影 / 设计/审核签字。
"""


def _try_pymupdf(pdf_path: Path, png_out: Path) -> bool:
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
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        png_out.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(png_out))
        doc.close()
        return png_out.exists()
    except Exception:
        return False


def _try_pdf2image(pdf_path: Path, png_out: Path) -> bool:
    try:
        from pdf2image import convert_from_path  # type: ignore
    except Exception:
        return False
    try:
        images = convert_from_path(str(pdf_path), dpi=150, first_page=1, last_page=1)
        if not images:
            return False
        png_out.parent.mkdir(parents=True, exist_ok=True)
        images[0].save(str(png_out), "PNG")
        return png_out.exists()
    except Exception:
        return False


def _try_existing_png(slddrw_path: Path, png_out: Path) -> bool:
    candidate = slddrw_path.with_suffix(".PNG")
    if not candidate.exists():
        candidate = slddrw_path.with_suffix(".png")
    if candidate.exists():
        try:
            png_out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(str(candidate), str(png_out))
            return True
        except Exception:
            return False
    return False


def slddrw_to_png(slddrw_path: str, png_out: str) -> bool:
    drw = Path(slddrw_path)
    out = Path(png_out)

    pdf_candidates = [
        drw.with_suffix(".PDF"),
        drw.with_suffix(".pdf"),
    ]
    pdf_path: Path | None = None
    for cand in pdf_candidates:
        if cand.exists():
            pdf_path = cand
            break

    if pdf_path is not None:
        if _try_pymupdf(pdf_path, out):
            return True
        if _try_pdf2image(pdf_path, out):
            return True

    if _try_existing_png(drw, out):
        return True

    return False


def _extract_json_block(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
    if fenced:
        snippet = fenced.group(1)
        try:
            return json.loads(snippet)
        except Exception:
            pass
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        snippet = m.group(0)
        try:
            return json.loads(snippet)
        except Exception:
            try:
                fixed = re.sub(r",\s*([}\]])", r"\1", snippet)
                return json.loads(fixed)
            except Exception:
                return None
    return None


def vision_score(slddrw_path: str, qc_json_path: str, llm: LLMClient) -> dict[str, Any]:
    drw = Path(slddrw_path)
    base = drw.stem

    png_out = drw.with_name(f"{base}_vision.png")
    png_ok = slddrw_to_png(str(drw), str(png_out))

    qc_data: dict[str, Any] = {}
    qc_path = Path(qc_json_path)
    if qc_path.exists():
        try:
            with qc_path.open("r", encoding="utf-8") as f:
                qc_data = json.load(f)
        except Exception:
            qc_data = {}

    qc_summary = {
        "pass": qc_data.get("pass"),
        "score_pass_count": qc_data.get("score_pass_count"),
        "issues": qc_data.get("issues", [])[:20],
        "checks_keys": list((qc_data.get("checks") or {}).keys()),
    }

    sys_prompt = (
        "你是资深机械制图审图专家，熟悉中国国标 GB/T 14689 / 14690 / 14691 / "
        "4458.4 / 17452 / 131-2006 / 1182-2008 / 1804-m。\n"
        "下面给出 GB 规范摘要与 SolidWorks 自动 QC 的 JSON 结果，并附上一张图纸 PNG。\n"
        "请综合判断本张工程图的整体质量并返回 JSON。\n\n"
        + GB_RULES_BRIEF
    )

    user_text = (
        f"零件: {base}\n"
        f"QC 摘要 JSON:\n{json.dumps(qc_summary, ensure_ascii=False, indent=2)}\n\n"
        "请严格只输出 JSON, 字段如下:\n"
        '{"score": <0-100 整数>,'
        '"issues":[{"key":"...","desc":"...","fix":"..."}, ...],'
        '"summary":"一句话总结"}\n'
        "score 越高越合规；issues 列出主要问题与修复建议；不要输出 JSON 以外的任何字符。"
    )

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_text},
    ]

    image_paths = [str(png_out)] if png_ok else []

    result_obj: dict[str, Any] = {
        "score": 0,
        "issues": [],
        "summary": "",
        "png": str(png_out) if png_ok else "",
        "png_ok": png_ok,
        "raw_text": "",
        "error": "",
    }

    if not png_ok:
        result_obj["error"] = "PNG 渲染失败：未找到 PDF 也无法用 fitz/pdf2image 转换"

    try:
        resp = llm.vision(messages, image_paths=image_paths)
        text = (resp or {}).get("text") or ""
        result_obj["raw_text"] = text
        parsed = _extract_json_block(text)
        if isinstance(parsed, dict):
            score = parsed.get("score")
            try:
                score_int = int(score)
            except Exception:
                score_int = 0
            score_int = max(0, min(100, score_int))
            issues = parsed.get("issues") or []
            if not isinstance(issues, list):
                issues = []
            cleaned_issues = []
            for it in issues:
                if isinstance(it, dict):
                    cleaned_issues.append({
                        "key": str(it.get("key", "")),
                        "desc": str(it.get("desc", "")),
                        "fix": str(it.get("fix", "")),
                    })
                elif isinstance(it, str):
                    cleaned_issues.append({"key": "", "desc": it, "fix": ""})
            summary = str(parsed.get("summary", ""))
            result_obj["score"] = score_int
            result_obj["issues"] = cleaned_issues
            result_obj["summary"] = summary
        else:
            if not result_obj["error"]:
                result_obj["error"] = "LLM 返回无法解析为 JSON"
    except Exception as exc:
        result_obj["error"] = f"LLM 调用异常: {type(exc).__name__}: {exc}"

    # === Spec enhance-v1-1 Task 5: 字段规范化 + fix_suggestion ===
    THRESHOLD = 60

    FIX_HINTS = {
        "gb_titlebar_complete": "标题栏的 6 个字段（品名、图号、材质、数量、设计、日期）若为空，请在 SLDPRT 的 CustomProperty 中补齐对应键值；或重新使用 templates/gb_a4_landscape.DRWDOT 模板生成。",
        "titlebar_empty": "标题栏内容为空。请确认 13 个 CustomProperty 注入完成且 SLDDRW 链接到模板的 $PRP 占位符。",
        "missing_frame_titleblock": "缺少标准图框/标题栏。请检查模板路径配置 templates/gb_a4_landscape.DRWDOT 是否生效。",
        "has_datum_a": "建议在主视图左侧增加基准 A 标识；可用 InsertDatumTag2 或 InsertNote('△A') 配合形位公差框。",
        "missing_datum": "未识别基准 A。建议人工补充 InsertDatumTag2(\"A\")。",
        "has_ra_note": "建议在右上角添加默认表面粗糙度注释：'其余 √Ra3.2'。",
        "missing_roughness": "粗糙度标注缺失。建议添加 '其余 Ra3.2'。",
        "duplicate_redundant_roughness": "粗糙度标注重复。请删除冗余 NoteBlock，仅保留 1 条。",
        "gb_has_section_view_or_skipped": "未检出剖视图。如该零件结构简单可忽略；如需要请人工确认或运行 templates/macros/auto_section.bas。",
        "section_view_missing": "缺少剖视图。本零件可能不需要；如需要请通过 SW VBA 宏 auto_section.swp 兜底生成。",
        "refdoc_correct": "SolidWorks 2025 + pywin32 平台限制：SaveAs 后 view.ReferencedDocument 未持久化。该项作为警告不阻断交付。",
        "has_tech_note": "技术要求注解未识别。建议补充 1 条多行 Note：技术要求 1./2./3.",
        "missing_all_dimension": "无任何尺寸标注。请运行 RunCommand(826) 自动拉模型尺寸。",
        "view_layout_noncompliant": "视图布局不符合 GB 第一角投影。建议使用 v6 的 T 字布局算法。",
        "residual_view_arrow": "残留 SolidWorks 视图方向箭头。建议关闭 SetUserPreferenceToggle(195, False)。",
        "doc_read_error": "工程图读取异常。建议先用 OpenDoc6 + options=257 重试 3 次。",
    }

    def _fix_for(key: str) -> str:
        return FIX_HINTS.get(key, "请人工检查并参考 GB/T 4458/14690/131/1182 标准。")

    norm_issues = []
    for it in (result_obj.get("issues") or []):
        if not isinstance(it, dict):
            continue
        key = it.get("key") or it.get("name") or ""
        fix = it.get("fix") or it.get("fix_suggestion") or _fix_for(key)
        sev = it.get("severity") or "warning"
        norm_issues.append({
            "key": key,
            "severity": sev,
            "description": it.get("desc") or it.get("description") or it.get("msg") or "",
            "fix_suggestion": fix,
        })
    result_obj["issues"] = norm_issues
    result_obj["threshold"] = THRESHOLD
    score = int(result_obj.get("score", 0) or 0)
    result_obj["pass"] = bool(score >= THRESHOLD)
    try:
        if "image_path" not in result_obj:
            result_obj["image_path"] = str(png_out)
    except Exception:
        pass
    try:
        if "model" not in result_obj:
            result_obj["model"] = getattr(llm, "vision_model", None) or getattr(llm, "model", None) or "?"
    except Exception:
        pass
    # === end ===

    out_json = drw.with_name(f"{base}_vision.json")
    try:
        with out_json.open("w", encoding="utf-8") as f:
            json.dump(result_obj, f, ensure_ascii=False, indent=2)
        result_obj["vision_json"] = str(out_json)
    except Exception as exc:
        result_obj["error"] = (result_obj.get("error") or "") + f" | 写 vision.json 失败: {exc}"

    return result_obj


def vision_score_with_reference(
    slddrw_path: str,
    qc_json_path: str,
    llm: LLMClient,
    reference_png_path: str | None = None,
) -> dict[str, Any]:
    """v1.2: 生成图 vs 案例图双图对比评分。

    当 reference_png_path 存在时，LLM 同时接收 2 张图（生成图 + 案例图），
    输出 reference_diff 字段；为 None 时退化为单图评分，reference_diff=null。
    原 vision_score() 保持不变以兼容 v1.1 链路。
    """
    drw = Path(slddrw_path)
    base = drw.stem

    # === 1. 渲染生成图 PNG ===
    png_out = drw.with_name(f"{base}_vision_ref.png")
    png_ok = slddrw_to_png(str(drw), str(png_out))

    # === 2. 读取 qc.json ===
    qc_data: dict[str, Any] = {}
    qc_path = Path(qc_json_path)
    if qc_path.exists():
        try:
            with qc_path.open("r", encoding="utf-8") as f:
                qc_data = json.load(f)
        except Exception:
            qc_data = {}

    qc_summary = {
        "pass": qc_data.get("pass"),
        "score_pass_count": qc_data.get("score_pass_count"),
        "issues": qc_data.get("issues", [])[:20],
        "checks_keys": list((qc_data.get("checks") or {}).keys()),
    }

    # === 3. 构建 messages ===
    sys_prompt = (
        "你是资深机械制图审图专家，熟悉中国国标 GB/T 14689 / 14690 / 14691 / "
        "4458.4 / 17452 / 131-2006 / 1182-2008 / 1804-m。\n"
        "下面给出 GB 规范摘要与 SolidWorks 自动 QC 的 JSON 结果，并附上工程图 PNG。\n"
        "请综合判断本张工程图的整体质量并返回 JSON。\n\n"
        + GB_RULES_BRIEF
    )

    has_ref = bool(reference_png_path) and Path(reference_png_path).exists()

    if has_ref:
        user_text = (
            f"零件: {base}\n"
            f"QC 摘要 JSON:\n{json.dumps(qc_summary, ensure_ascii=False, indent=2)}\n\n"
            "附上 2 张图：第 1 张是自动生成的工程图，第 2 张是人工绘制的案例参考图。\n"
            "请对比两张图的结构差异，输出 reference_diff 字段。\n\n"
            "请严格只输出 JSON, 字段如下:\n"
            '{"score": <0-100 整数>,'
            '"issues":[{"key":"...","desc":"...","fix":"..."}, ...],'
            '"summary":"一句话总结",'
            '"reference_diff":{'
            '"similarity":<0-100 整数>,'
            '"structural_diff":"...",'
            '"missing_elements":["..."]'
            "}}\n"
            "score 越高越合规；issues 列出主要问题与修复建议；"
            "reference_diff.similarity 是两张图整体相似度（0-100）；"
            "structural_diff 描述结构差异；missing_elements 列出生成图相对案例图缺失的元素；"
            "不要输出 JSON 以外的任何字符。"
        )
    else:
        user_text = (
            f"零件: {base}\n"
            f"QC 摘要 JSON:\n{json.dumps(qc_summary, ensure_ascii=False, indent=2)}\n"
            "请严格只输出 JSON, 字段如下:\n"
            '{"score": <0-100 整数>,'
            '"issues":[{"key":"...","desc":"...","fix":"..."}, ...],'
            '"summary":"一句话总结",'
            '"reference_diff":null}\n'
            "score 越高越合规；issues 列出主要问题与修复建议；不要输出 JSON 以外的任何字符。"
        )

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_text},
    ]

    # === 4. 调用 LLM ===
    image_paths = [str(png_out)] if png_ok else []
    if has_ref:
        image_paths.append(str(reference_png_path))

    result_obj: dict[str, Any] = {
        "score": 0,
        "issues": [],
        "summary": "",
        "png": str(png_out) if png_ok else "",
        "png_ok": png_ok,
        "raw_text": "",
        "error": "",
        "reference_diff": None,
        "reference_png": str(reference_png_path) if has_ref else None,
    }

    if not png_ok:
        result_obj["error"] = "PNG 渲染失败：未找到 PDF 也无法用 fitz/pdf2image 转换"

    try:
        resp = llm.vision(messages, image_paths=image_paths)
        text = (resp or {}).get("text") or ""
        result_obj["raw_text"] = text
        parsed = _extract_json_block(text)
        if isinstance(parsed, dict):
            score = parsed.get("score")
            try:
                score_int = int(score)
            except Exception:
                score_int = 0
            score_int = max(0, min(100, score_int))
            issues = parsed.get("issues") or []
            if not isinstance(issues, list):
                issues = []
            cleaned_issues = []
            for it in issues:
                if isinstance(it, dict):
                    cleaned_issues.append({
                        "key": str(it.get("key", "")),
                        "desc": str(it.get("desc", "")),
                        "fix": str(it.get("fix", "")),
                    })
                elif isinstance(it, str):
                    cleaned_issues.append({"key": "", "desc": it, "fix": ""})
            summary = str(parsed.get("summary", ""))
            result_obj["score"] = score_int
            result_obj["issues"] = cleaned_issues
            result_obj["summary"] = summary

            # === 5. 解析 reference_diff ===
            ref_diff = parsed.get("reference_diff")
            if isinstance(ref_diff, dict):
                sim = ref_diff.get("similarity")
                try:
                    sim_int = int(sim)
                except Exception:
                    sim_int = 0
                sim_int = max(0, min(100, sim_int))
                missing = ref_diff.get("missing_elements") or []
                if not isinstance(missing, list):
                    missing = []
                missing_list = [str(x) for x in missing]
                result_obj["reference_diff"] = {
                    "similarity": sim_int,
                    "structural_diff": str(ref_diff.get("structural_diff", "")),
                    "missing_elements": missing_list,
                }
            else:
                result_obj["reference_diff"] = None
        else:
            if not result_obj["error"]:
                result_obj["error"] = "LLM 返回无法解析为 JSON"
    except Exception as exc:
        result_obj["error"] = f"LLM 调用异常: {type(exc).__name__}: {exc}"

    # === 6. 字段规范化 + fix_suggestion（与 v1.1 vision_score 一致）===
    THRESHOLD = 60

    FIX_HINTS = {
        "gb_titlebar_complete": "标题栏的 6 个字段（品名、图号、材质、数量、设计、日期）若为空，请在 SLDPRT 的 CustomProperty 中补齐对应键值；或重新使用 templates/gb_a4_landscape.DRWDOT 模板生成。",
        "titlebar_empty": "标题栏内容为空。请确认 13 个 CustomProperty 注入完成且 SLDDRW 链接到模板的 $PRP 占位符。",
        "missing_frame_titleblock": "缺少标准图框/标题栏。请检查模板路径配置 templates/gb_a4_landscape.DRWDOT 是否生效。",
        "has_datum_a": "建议在主视图左侧增加基准 A 标识；可用 InsertDatumTag2 或 InsertNote('△A') 配合形位公差框。",
        "missing_datum": "未识别基准 A。建议人工补充 InsertDatumTag2(\"A\")。",
        "has_ra_note": "建议在右上角添加默认表面粗糙度注释：'其余 √Ra3.2'。",
        "missing_roughness": "粗糙度标注缺失。建议添加 '其余 Ra3.2'。",
        "duplicate_redundant_roughness": "粗糙度标注重复。请删除冗余 NoteBlock，仅保留 1 条。",
        "gb_has_section_view_or_skipped": "未检出剖视图。如该零件结构简单可忽略；如需要请人工确认或运行 templates/macros/auto_section.bas。",
        "section_view_missing": "缺少剖视图。本零件可能不需要；如需要请通过 SW VBA 宏 auto_section.swp 兜底生成。",
        "refdoc_correct": "SolidWorks 2025 + pywin32 平台限制：SaveAs 后 view.ReferencedDocument 未持久化。该项作为警告不阻断交付。",
        "has_tech_note": "技术要求注解未识别。建议补充 1 条多行 Note：技术要求 1./2./3.",
        "missing_all_dimension": "无任何尺寸标注。请运行 RunCommand(826) 自动拉模型尺寸。",
        "view_layout_noncompliant": "视图布局不符合 GB 第一角投影。建议使用 v6 的 T 字布局算法。",
        "residual_view_arrow": "残留 SolidWorks 视图方向箭头。建议关闭 SetUserPreferenceToggle(195, False)。",
        "doc_read_error": "工程图读取异常。建议先用 OpenDoc6 + options=257 重试 3 次。",
    }

    def _fix_for(key: str) -> str:
        return FIX_HINTS.get(key, "请人工检查并参考 GB/T 4458/14690/131/1182 标准。")

    norm_issues = []
    for it in (result_obj.get("issues") or []):
        if not isinstance(it, dict):
            continue
        key = it.get("key") or it.get("name") or ""
        fix = it.get("fix") or it.get("fix_suggestion") or _fix_for(key)
        sev = it.get("severity") or "warning"
        norm_issues.append({
            "key": key,
            "severity": sev,
            "description": it.get("desc") or it.get("description") or it.get("msg") or "",
            "fix_suggestion": fix,
        })
    result_obj["issues"] = norm_issues
    result_obj["threshold"] = THRESHOLD
    score = int(result_obj.get("score", 0) or 0)
    result_obj["pass"] = bool(score >= THRESHOLD)
    result_obj["image_path"] = str(png_out)
    result_obj["model"] = getattr(llm, "vision_model", None) or getattr(llm, "model", None) or "?"

    out_json = drw.with_name(f"{base}_vision_ref.json")
    try:
        with out_json.open("w", encoding="utf-8") as f:
            json.dump(result_obj, f, ensure_ascii=False, indent=2)
        result_obj["vision_json"] = str(out_json)
    except Exception as exc:
        result_obj["error"] = (result_obj.get("error") or "") + f" | 写 vision_ref.json 失败: {exc}"

    return result_obj
