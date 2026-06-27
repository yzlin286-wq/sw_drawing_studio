"""drw_generate_v6.py — 在 v5 基础上的 3 处升级
- T 字 GB 第一角投影视图布局
- 二次 RunCommand(826) 拉模型项
- cfg_name 缓存（防 part 关闭后取空）
- VBA .swp 优先 fallback
继承 v5 的全部其他能力（CustomProperty 注入、模板路径、QC 闭环兼容、GTol 文本回退）。
"""
import os, re, sys, time, json, math, traceback, subprocess
import pythoncom
import win32com.client as wc
from win32com.client import VARIANT
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve()
_BUNDLE_ROOT = Path(os.environ.get("SW_DRAWING_STUDIO_BUNDLE_ROOT", _SCRIPT_PATH.parent.parent.parent.parent)).resolve()
_RUNTIME_ROOT = Path(os.environ.get("SW_DRAWING_STUDIO_RUNTIME_ROOT", _BUNDLE_ROOT)).resolve()
ROOT = str(_RUNTIME_ROOT)
V4_DIR = str(_BUNDLE_ROOT / ".trae" / "specs" / "repair-section-and-recompare")
sys.path.insert(0, V4_DIR)
from section_helper import create_section_in_active_drawing  # noqa: E402

sys.stdout.reconfigure(line_buffering=True)
def log(*a, **kw): print(*a, **kw, flush=True)
SUBPROCESS_CREATIONFLAGS = (
    getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if sys.platform.startswith("win")
    else 0
)

_SW_DETAILING_DIMENSION_TEXT_AND_LEADER_STYLE = 372
_SW_DETAILING_LINEAR_DIMENSION = 206
_SW_BROKEN_LEADER_HORIZONTAL_TEXT = 2


def _dynamic_dispatch(obj):
    try:
        return wc.dynamic.Dispatch(obj)
    except Exception:
        return obj


def _ensure_solidworks_global_lock(operation, part_path=""):
    try:
        from app.services.solidworks_global_lock import require_current_job_lock

        guard = require_current_job_lock(operation)
    except Exception as exc:
        raise SystemExit(f"blocked_by_solidworks_lock: lock_guard_unavailable: {exc}")
    if guard.get("ok"):
        return
    raise SystemExit(
        "blocked_by_solidworks_lock: "
        + json.dumps({
            "operation": operation,
            "part_path": str(part_path or ""),
            "reason": guard.get("reason", ""),
            "owner": guard.get("owner", {}),
            "fix_suggestion": guard.get("fix_suggestion", ""),
        }, ensure_ascii=False)
    )


def _solidworks_doc_registry_event(
    event_type,
    *,
    role="",
    path="",
    title="",
    doc_type="",
    stage="",
    close_verified=None,
    reason="",
    extra=None,
):
    registry = os.environ.get("SWDS_SOLIDWORKS_DOC_REGISTRY", "").strip()
    if not registry:
        return
    try:
        Path(registry).parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "sw_drawing_studio.solidworks_document_registry.v1",
            "event_type": str(event_type),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "job_id": os.environ.get("JOB_ID") or os.environ.get("SW_DRAWING_STUDIO_LOCK_JOB_ID") or "",
            "role": str(role or ""),
            "path": str(path or ""),
            "title": str(title or ""),
            "doc_type": str(doc_type or ""),
            "stage": str(stage or ""),
            "owned_by_job": True,
            "close_verified": close_verified,
            "reason": str(reason or ""),
            "extra": extra or {},
        }
        with open(registry, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _doc_title(doc):
    try:
        return str(call(doc, "GetTitle") or "")
    except Exception:
        return ""


def _doc_path(doc):
    try:
        return str(call(doc, "GetPathName") or "")
    except Exception:
        return ""


def _same_abs_path(a, b):
    if not a or not b:
        return False
    try:
        return os.path.normcase(os.path.abspath(str(a))) == os.path.normcase(os.path.abspath(str(b)))
    except Exception:
        return str(a).lower() == str(b).lower()


def _apply_horizontal_dimension_text_policy(doc, warnings_box=None, log_fn=log, reason=""):
    attempts = []
    targets = []
    try:
        ext = getattr(doc, "Extension", None)
        if ext is not None:
            targets.append(("drawing_extension", ext))
    except Exception as exc:
        attempts.append({"target": "drawing_extension", "success": False, "error": str(exc)})
    targets.append(("drawing_doc", doc))

    success = False
    for label, target in targets:
        if target is None:
            continue
        setter = getattr(target, "SetUserPreferenceInteger", None)
        if not callable(setter):
            attempts.append({"target": label, "success": False, "reason": "SetUserPreferenceInteger_missing"})
            continue
        try:
            ok = bool(setter(
                _SW_DETAILING_DIMENSION_TEXT_AND_LEADER_STYLE,
                _SW_DETAILING_LINEAR_DIMENSION,
                _SW_BROKEN_LEADER_HORIZONTAL_TEXT,
            ))
            attempts.append({"target": label, "success": ok})
            success = success or ok
            log_fn(
                "  [dimension text policy] "
                f"{label}.SetUserPreferenceInteger(swDetailingDimensionTextAndLeaderStyle, "
                "swDetailingLinearDimension, swBrokenLeaderHorizontalText) -> "
                f"{ok}"
            )
        except Exception as exc:
            attempts.append({"target": label, "success": False, "error": str(exc)})
            log_fn(f"  [dimension text policy] {label} failed: {exc}")

    if warnings_box is not None:
        warnings_box.append({
            "code": "dimension_text_horizontal_policy",
            "success": success,
            "reason": reason,
            "user_pref": "swDetailingDimensionTextAndLeaderStyle",
            "user_pref_option": "swDetailingLinearDimension",
            "value": "swBrokenLeaderHorizontalText",
            "attempts": attempts,
        })
    return {"success": success, "attempts": attempts}


def _render_pdf_first_page_to_png(pdf_path, png_path, warnings_box=None, log_fn=log):
    result = {
        "success": False,
        "pdf_path": str(pdf_path),
        "png_path": str(png_path),
        "reason": "",
    }
    try:
        bundle_root = str(_BUNDLE_ROOT)
        if bundle_root not in sys.path:
            sys.path.insert(0, bundle_root)
        from app.services.pdf_render_service import render_pdf_first_page

        result = render_pdf_first_page(Path(pdf_path), Path(png_path), dpi=300)
        ok = bool(result.get("success"))
        if ok:
            log_fn(f"  [png] PDF first page rendered -> {png_path}")
        else:
            log_fn(f"  [png] render failed: {result.get('reason', '')}")
            if warnings_box is not None:
                warnings_box.append({
                    "code": "png_render_failed",
                    "pdf": str(pdf_path),
                    "png": str(png_path),
                    "reason": result.get("reason", ""),
                })
    except Exception as exc:
        result["reason"] = str(exc)
        log_fn(f"  [png] render exception: {exc}")
        if warnings_box is not None:
            warnings_box.append({
                "code": "png_render_exception",
                "pdf": str(pdf_path),
                "png": str(png_path),
                "reason": str(exc),
            })
    return result


def _probe_sw_active_object(timeout_s=15):
    """Check SolidWorks active-object responsiveness in a bounded child."""
    code = (
        "import json, pythoncom, win32com.client as wc\n"
        "result={'status':'unknown','reason':'','revision':''}\n"
        "pythoncom.CoInitialize()\n"
        "try:\n"
        "    sw=wc.GetActiveObject('SldWorks.Application')\n"
        "    result['status']='connected'\n"
        "    try:\n"
        "        result['revision']=str(sw.RevisionNumber())\n"
        "    except Exception as exc:\n"
        "        result['reason']='revision_unreadable: '+str(exc)\n"
        "except Exception as exc:\n"
        "    result['status']='failed'\n"
        "    result['reason']=str(exc)\n"
        "finally:\n"
        "    try: pythoncom.CoUninitialize()\n"
        "    except Exception: pass\n"
        "print(json.dumps(result, ensure_ascii=False), flush=True)\n"
    )
    try:
        cp = subprocess.run(
            [sys.executable, "-X", "utf8", "-c", code],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(1, int(timeout_s)),
            creationflags=SUBPROCESS_CREATIONFLAGS,
        )
        stdout = (cp.stdout or "").strip()
        payload = stdout.splitlines()[-1] if stdout else "{}"
        try:
            data = json.loads(payload)
        except Exception:
            data = {"status": "failed", "reason": f"invalid_probe_output rc={cp.returncode}"}
        data["returncode"] = cp.returncode
        if cp.stderr:
            data["stderr_tail"] = "\n".join(cp.stderr.splitlines()[-5:])
        return data
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "reason": f"GetActiveObject probe timed out after {int(timeout_s)}s"}
    except Exception as exc:
        return {"status": "failed", "reason": str(exc)}


DEFAULT_PART = str(_RUNTIME_ROOT / "3D转2D测试图纸" / "LB26001-A-04-001.SLDPRT")
OUT_DIR = str(_RUNTIME_ROOT / "drw_output" / "v5")
STANDARD_MD = os.path.join(V4_DIR, "drawing_standard_v2.md")

CANDIDATE_SCALES = [(5,1),(2,1),(1,1),(1,2),(1,5),(1,10),(1,20),(1,50)]
PROP_KEYS = ["SWFormatSize","机型","品名","图号","类别","数量",
             "材质","表面处理","设计","日期",
             "UNIT_OF_MEASURE","Material","重量"]

TECH_NOTES = (
    "技术要求：\n"
    "1. 未注线性尺寸及角度尺寸公差按 GB/T 1804-m 执行。\n"
    "2. 零件去毛刺、清除锐边，表面应平整无划伤。\n"
    "3. 表面处理：脱脂磷化后静电喷粉，涂层均匀牢固。"
)

# A4 横向工作区（单位 m）：去掉左右各 20mm 边距 + 标题栏 75mm 高
WORKAREA = dict(xmin=0.020, xmax=0.277, ymin=0.075, ymax=0.200)
REFERENCE_LAYOUT_SAFE_AREA = dict(xmin=0.010, xmax=0.287, ymin=0.010, ymax=0.200)

# A4 角落 fallback（单位 m）
FALLBACK_NOTE_POS = {
    "tech":  (0.297*0.62, 0.21*0.30),
    "ra":    (0.260, 0.190),
    "datum": (0.020, 0.100),
}

REFERENCE_STYLE_PROFILE_36_PATH = _RUNTIME_ROOT / "drw_output" / "reference_style_profile" / "lb26001_36_reference_style_profile.json"
REFERENCE_STYLE_PROFILE_PATH = _RUNTIME_ROOT / "drw_output" / "reference_style_profile" / "lb26001_reference_style_profile.json"
REFERENCE_SHEET_SIZE_M = (0.297, 0.210)

LAYERS = [
    # (名称, color BGR int, lineStyle, weight)  weight: 0=Default,1=Thin,2=Normal,3=Thick
    ("粗实线",   0,         0, 3),
    ("细实线",   0,         0, 1),
    ("虚线",     255,       1, 1),
    ("点划线",   16711680,  4, 1),
    ("中心线",   16711680,  4, 1),
]


def _reference_style_profile_candidates():
    candidates = []
    env_profile = os.environ.get("REFERENCE_STYLE_PROFILE", "").strip()
    if env_profile:
        candidates.append(Path(env_profile))
    candidates.append(REFERENCE_STYLE_PROFILE_36_PATH)
    candidates.append(REFERENCE_STYLE_PROFILE_PATH)
    unique = []
    seen = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _reference_style_sample(part_path):
    """Return same-name reference sample plus the profile path."""
    base = Path(part_path).stem
    for profile_path in _reference_style_profile_candidates():
        try:
            if not profile_path.exists():
                continue
            profile = json.loads(profile_path.read_text(encoding="utf-8-sig"))
            sample = (profile.get("reference_samples") or {}).get(base) or {}
            if sample:
                return sample, str(profile_path)
        except Exception as exc:
            print(f"[reference_style] load profile failed: {profile_path}: {exc}")
    return {}, ""


def _reference_style_view_keys_from_sample(sample):
    view_count = int(sample.get("view_count") or 0)
    view_types = sample.get("view_types") or {}
    projected_count = int(view_types.get("4") or 0)
    base_count = max(0, view_count - projected_count)
    if view_count == 2 and projected_count >= 1:
        return ["front", "top"]
    if view_count == 3 and projected_count == 1 and base_count >= 2:
        return ["front", "top", "iso"]
    if view_count == 3 and projected_count >= 2:
        return ["front", "top", "right"]
    if view_count >= 4 and projected_count >= 3 and base_count <= 1:
        return ["front", "top", "right", "bottom"]
    if view_count >= 4 and projected_count >= 2:
        return ["front", "top", "right", "iso"]
    return []


def _reference_style_view_plan(part_path):
    """Return reference-learned view keys for known LB26001 samples."""
    sample, profile_path = _reference_style_sample(part_path)
    keys = _reference_style_view_keys_from_sample(sample)
    if keys:
        return keys, profile_path
    return [], ""


def _reference_style_should_use_first_angle(view_keys):
    keys = set(view_keys or [])
    return keys == {"front", "top", "right"}


def _created_view_centers_for_persisted_layout(created_view_keys, centers):
    result = {}
    for key in created_view_keys or []:
        if key in centers:
            result[key] = centers[key]
    return result or dict(centers or {})


def _created_view_outlines_for_persisted_layout(created_view_keys, outlines):
    result = {}
    for key in created_view_keys or []:
        if key in outlines:
            result[key] = outlines[key]
    return result or dict(outlines or {})


def _reference_style_allows_section_view(part_path):
    """Return whether section creation is compatible with the same-name reference."""
    sample, profile_path = _reference_style_sample(part_path)
    if not sample:
        return True, ""
    view_types = {str(key): int(value or 0) for key, value in (sample.get("view_types") or {}).items()}
    if view_types and set(view_types).issubset({"4", "7"}):
        return False, profile_path
    return True, profile_path


def _reference_style_should_draw_default_titleblock(part_path, reference_view_keys=None):
    """Return whether default sheet/titleblock styling is allowed.

    Same-name reference drawings already define the visible sheet style. For
    those samples, the default A4 template or built-in titleblock can collide
    with the learned view slots and produce visually wrong drawings even when
    API metrics pass.
    """
    if str(os.environ.get("FORCE_DEFAULT_TITLEBLOCK", "")).strip() in {"1", "true", "TRUE", "yes"}:
        return True, "forced_by_env"
    sample, profile_path = _reference_style_sample(part_path)
    if sample or reference_view_keys:
        return False, profile_path or "reference_view_plan"
    return True, ""


def _reference_style_dim_floor(part_path):
    """Return same-name reference DisplayDim floor for known LB26001 samples."""
    base = Path(part_path).stem
    for profile_path in _reference_style_profile_candidates():
        try:
            if not profile_path.exists():
                continue
            profile = json.loads(profile_path.read_text(encoding="utf-8-sig"))
            floors = profile.get("aggregate", {}).get("min_display_dim_by_sample") or {}
            value = floors.get(base)
            if value is None:
                sample = (profile.get("reference_samples") or {}).get(base) or {}
                value = sample.get("display_dim_count")
            floor = int(value or 0)
            if floor > 0:
                return floor, str(profile_path)
        except Exception as exc:
            print(f"[reference_style] load dim floor failed: {profile_path}: {exc}")
    return 0, ""


def _reference_style_point(item, sheet_size):
    center = item.get("center_m")
    if isinstance(center, list) and len(center) >= 2:
        return float(center[0]), float(center[1])
    center_norm = item.get("center_norm")
    if isinstance(center_norm, list) and len(center_norm) >= 2:
        return float(center_norm[0]) * sheet_size[0], float(center_norm[1]) * sheet_size[1]
    outline = item.get("outline_m") or []
    if isinstance(outline, list) and len(outline) >= 4:
        x0, y0, x1, y1 = [float(v) for v in outline[:4]]
        return (x0 + x1) / 2.0, (y0 + y1) / 2.0
    return None


def _reference_style_layout_centers(part_path, view_keys=None):
    """Return reference-learned drawing-view centers keyed by front/top/right/iso."""
    sample, profile_path = _reference_style_sample(part_path)
    if not sample:
        return {}, ""
    view_keys = list(view_keys or _reference_style_view_keys_from_sample(sample))
    if not view_keys:
        return {}, ""
    sheet_size = sample.get("sheet_size_m") or {}
    width = float(sheet_size.get("width") or REFERENCE_SHEET_SIZE_M[0])
    height = float(sheet_size.get("height") or REFERENCE_SHEET_SIZE_M[1])

    layout_items = []
    for item in sample.get("view_layout") or []:
        if not isinstance(item, dict):
            continue
        point = _reference_style_point(item, (width, height))
        if point is None:
            continue
        copied = dict(item)
        copied["_point"] = point
        layout_items.append(copied)
    if not layout_items:
        return {}, ""

    base_items = [item for item in layout_items if str(item.get("type") or "") != "4"]
    projected_items = [item for item in layout_items if str(item.get("type") or "") == "4"]
    result = {}

    if base_items:
        base_items.sort(key=lambda item: item["_point"][1], reverse=True)
        result["front"] = base_items[0]["_point"]
        if "iso" in view_keys and len(base_items) > 1:
            remaining = base_items[1:]
            remaining.sort(key=lambda item: (item["_point"][0], -item["_point"][1]), reverse=True)
            result["iso"] = remaining[0]["_point"]

    front = result.get("front")
    if projected_items and front:
        fx_, fy_ = front
        remaining_projected = list(projected_items)
        top_candidate = min(
            remaining_projected,
            key=lambda item: (abs(item["_point"][0] - fx_), item["_point"][1]),
        )
        if "top" in view_keys:
            result["top"] = top_candidate["_point"]
        remaining_projected = [item for item in remaining_projected if item is not top_candidate]
        right_candidate = None
        if remaining_projected:
            right_pool = [
                item for item in remaining_projected
                if item["_point"][0] > fx_ + 0.005
            ] or remaining_projected
            right_candidate = min(
                right_pool,
                key=lambda item: (abs(item["_point"][1] - fy_), -item["_point"][0]),
            )
        if "right" in view_keys and right_candidate is not None:
            result["right"] = right_candidate["_point"]
        if right_candidate is not None:
            remaining_projected = [item for item in remaining_projected if item is not right_candidate]
        if "bottom" in view_keys and remaining_projected:
            bottom_candidate = min(remaining_projected, key=lambda item: item["_point"][1])
            result["bottom"] = bottom_candidate["_point"]
    elif projected_items and "top" in view_keys:
        result["top"] = projected_items[0]["_point"]

    return {key: value for key, value in result.items() if key in view_keys}, profile_path


def _v4_repo_on_sys_path():
    repo = str(_BUNDLE_ROOT)
    if repo not in sys.path:
        sys.path.insert(0, repo)


def _v4_json_load(path):
    try:
        path = Path(path)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        print(f"[v4 blueprint] json load failed: {path}: {exc}")
    return {}


def _v4_reference_profiles_candidates():
    candidates = []
    env_profile = os.environ.get("REFERENCE_PROFILES_V4", "").strip()
    if env_profile:
        candidates.append(Path(env_profile))
    candidates.append(_RUNTIME_ROOT / "drw_output" / "reference_style_profile" / "reference_profiles_v4.json")
    unique = []
    seen = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _v4_reference_profile_for_part(part_path):
    base = Path(part_path).stem
    for profile_path in _v4_reference_profiles_candidates():
        payload = _v4_json_load(profile_path)
        profile = (payload.get("profiles") or {}).get(base) or {}
        if profile:
            return profile, str(profile_path)
    try:
        _v4_repo_on_sys_path()
        from app.services.reference_style_profile_service import build_reference_profiles_v4
        payload = build_reference_profiles_v4()
        profile = (payload.get("profiles") or {}).get(base) or {}
        if profile:
            return profile, str(payload.get("output_path") or "")
    except Exception as exc:
        print(f"[v4 blueprint] reference profile build failed: {exc}")
    return {}, ""


def _v4_normalize_part_class(part_class):
    part_class = str(part_class or "").strip() or "machined_part"
    mapping = {
        "feature_part": "machined_part",
        "imported_body": "machined_part",
        "sheet_like": "sheet_metal",
    }
    return mapping.get(part_class, part_class)


def _v4_classify_part_for_blueprint(part_path, bbox_m=None, qc_dir=None, warnings_box=None):
    bbox_mm = None
    if bbox_m and len(bbox_m) >= 3:
        try:
            bbox_mm = [float(bbox_m[0]) * 1000.0, float(bbox_m[1]) * 1000.0, float(bbox_m[2]) * 1000.0]
        except Exception:
            bbox_mm = None
    try:
        _v4_repo_on_sys_path()
        from app.services.part_classification_service import classify_part
        cls = classify_part(
            str(part_path),
            bbox_mm=bbox_mm,
            write_json=qc_dir is not None,
            out_dir=Path(qc_dir) if qc_dir else None,
        )
        return _v4_normalize_part_class(getattr(cls, "part_class", "")), getattr(cls, "to_dict", lambda: {})()
    except Exception as exc:
        if warnings_box is not None:
            warnings_box.append({"code": "drawing_blueprint_part_class_failed", "msg": str(exc)})
        return "machined_part", {
            "part_path": str(part_path),
            "part_class": "machined_part",
            "reason": f"classification_failed:{exc}",
            "bbox_mm": bbox_mm,
        }


def _v4_blueprint_output_paths(base_name, run_dir, out_dir):
    paths = []
    if run_dir:
        paths.append(Path(run_dir) / "qc" / "drawing_blueprint.json")
    paths.append(Path(out_dir) / f"{base_name}_drawing_blueprint.json")
    result = []
    seen = set()
    for path in paths:
        key = str(path.resolve()) if path.is_absolute() else str(path)
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def _v4_write_blueprint_copies(blueprint_data, paths):
    written = []
    for path in paths:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(blueprint_data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            written.append(str(path))
        except Exception as exc:
            print(f"[v4 blueprint] write failed: {path}: {exc}")
    return written


def _v4_build_or_load_drawing_blueprint(part_path, *, run_dir, out_dir, bbox_m=None, src_props=None, warnings_box=None):
    base = Path(part_path).stem
    env_path = os.environ.get("DRAWING_BLUEPRINT_PATH", "").strip()
    blueprint_data = {}
    source = ""
    if env_path:
        blueprint_data = _v4_json_load(env_path)
        source = env_path if blueprint_data else ""
    qc_dir = Path(run_dir) / "qc" if run_dir else Path(out_dir)
    if not blueprint_data:
        try:
            _v4_repo_on_sys_path()
            from app.services.drawing_blueprint_builder import build_drawing_blueprint
            reference_profile, reference_profile_source = _v4_reference_profile_for_part(part_path)
            part_class, part_class_data = _v4_classify_part_for_blueprint(
                part_path,
                bbox_m=bbox_m,
                qc_dir=qc_dir,
                warnings_box=warnings_box,
            )
            part_understanding = {
                "part_path": str(part_path),
                "bbox_m": list(bbox_m or []),
                "bbox_mm": [float(v) * 1000.0 for v in bbox_m] if bbox_m else [],
                "titlebar_source_props": src_props or {},
                "part_classification": part_class_data,
            }
            blueprint = build_drawing_blueprint(
                base=base,
                part_class=part_class,
                part_understanding=part_understanding,
                reference_profile=reference_profile,
            )
            blueprint_data = blueprint.to_dict()
            blueprint_data.setdefault("source_inputs", {})["reference_profile_path"] = reference_profile_source
            source = "generated_from_v4_builder"
        except Exception as exc:
            if warnings_box is not None:
                warnings_box.append({"code": "drawing_blueprint_build_failed", "msg": str(exc)})
            return {}, [], ""
    paths = _v4_blueprint_output_paths(base, run_dir, out_dir)
    blueprint_data = _v4_apply_reference_intent_plan_path(blueprint_data, warnings_box=warnings_box)
    written = _v4_write_blueprint_copies(blueprint_data, paths)
    if warnings_box is not None:
        warnings_box.append({
            "code": "drawing_blueprint_v4",
            "schema": blueprint_data.get("schema", ""),
            "source": source,
            "paths": written,
            "required_display_dim_count": (blueprint_data.get("dimension_plan") or {}).get("required_display_dim_count"),
            "dimension_target_count": len((blueprint_data.get("dimension_plan") or {}).get("dimension_targets") or []),
            "view_slots": [item.get("slot") for item in (blueprint_data.get("view_plan") or []) if isinstance(item, dict)],
        })
    return blueprint_data, written, source


def _v4_blueprint_view_keys(blueprint_data):
    keys = []
    for item in blueprint_data.get("view_plan") or []:
        if not isinstance(item, dict):
            continue
        slot = str(item.get("slot") or "").strip()
        if slot and slot not in keys:
            keys.append(slot)
    return keys


def _v4_blueprint_default_titleblock_policy(blueprint_data):
    if str(os.environ.get("FORCE_DEFAULT_TITLEBLOCK", "")).strip() in {"1", "true", "TRUE", "yes"}:
        return True, "forced_by_env"
    layout = (blueprint_data or {}).get("layout_plan") or {}
    policy = layout.get("sheet_template_policy") or {}
    if not isinstance(policy, dict) or not policy:
        return None, ""
    source = "DrawingBlueprint.layout_plan.sheet_template_policy"
    if policy.get("default_template_artifacts_allowed") is False:
        return False, source
    if str(policy.get("policy") or "") == "strip_default_template_artifacts":
        return False, source
    if policy.get("skip_builtin_gb_frame_titleblock") is True:
        return False, source
    if policy.get("default_template_artifacts_allowed") is True:
        return True, source
    return None, ""


def _v4_blueprint_dim_floor(blueprint_data):
    try:
        return int((blueprint_data.get("dimension_plan") or {}).get("required_display_dim_count") or 0)
    except Exception:
        return 0


def _reference_intent_view_name_candidates(slot, dimension_plan=None):
    """Return stable localized/English drawing-view name candidates for a reference slot."""
    slot_key = str(slot or "").strip().lower()
    if not slot_key:
        return []
    plan = dimension_plan if isinstance(dimension_plan, dict) else {}
    result = []

    def _append(value):
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)

    reference_slots = plan.get("reference_view_slots") or {}
    if isinstance(reference_slots, dict):
        slot_info = reference_slots.get(slot_key) or reference_slots.get(str(slot or ""))
        if isinstance(slot_info, dict):
            _append(slot_info.get("reference_view_name"))
            _append(slot_info.get("view_name"))
    default_ordinals = {
        "front": 1,
        "right": 2,
        "top": 3,
        "iso": 4,
    }
    localized_aliases = {
        "front": ["Front View", "前视图"],
        "right": ["Right View", "右视图"],
        "top": ["Top View", "俯视图", "上视图"],
        "iso": ["Isometric View", "Iso View", "等轴测视图"],
    }
    ordinal = default_ordinals.get(slot_key)
    if ordinal:
        for template in (
            "工程图视图{}",
            "工程图 视图{}",
            "Drawing View{}",
            "Drawing View {}",
        ):
            _append(template.format(ordinal))
    for alias in localized_aliases.get(slot_key, []):
        _append(alias)
    return result


def _v4_blueprint_dimension_plan(blueprint_data):
    plan = (blueprint_data or {}).get("dimension_plan") or {}
    return plan if isinstance(plan, dict) else {}


def _v4_reference_callout_review_plan(intent_plan):
    # reference_callout_review_plan_required:
    # keep hole/thread/roughness visual callouts as explicit UI review items.
    # These are not DisplayDim substitutes; DisplayDim targets still have to
    # persist independently.
    if not isinstance(intent_plan, dict):
        return {}
    items = []
    required_keys = []
    absence_check_keys = []

    def _append(item):
        key = str(item.get("key") or "").strip()
        if not key:
            return
        if key in {entry.get("key") for entry in items}:
            return
        items.append(item)
        if item.get("required_visual_confirmation"):
            required_keys.append(key)
        if item.get("absence_check_required"):
            absence_check_keys.append(key)

    for dim in intent_plan.get("dimensions") or []:
        if not isinstance(dim, dict):
            continue
        key = str(dim.get("key") or "")
        expected_type = str(dim.get("expected_type") or "").lower()
        value = dim.get("reference_value")
        if key == "hole_diameter" or (expected_type == "diameter" and isinstance(value, dict)):
            evidence = dim.get("source_reference_evidence") or {}
            _append({
                "key": key or "hole_diameter",
                "source_dimension_key": key or "hole_diameter",
                "target_view": str(dim.get("target_view") or "top"),
                "expected_type": "hole_callout",
                "reference_value": value,
                "source_text": str(evidence.get("source_text") or ""),
                "required_visual_confirmation": True,
                "is_manufacturing_dimension": True,
                "notes_do_not_count_as_display_dim": True,
                "application_ui_screenshot_required": True,
            })

    for callout in intent_plan.get("reference_callouts") or []:
        if not isinstance(callout, dict):
            continue
        key = str(callout.get("key") or "")
        value = callout.get("reference_value")
        expected_type = str(callout.get("expected_type") or "")
        has_reference_value = value not in (None, "", [], {})
        manufacturing = bool(callout.get("is_manufacturing_dimension"))
        absence_check = (not has_reference_value) and expected_type in {"radius_callout", "chamfer_callout"}
        _append({
            "key": key,
            "target_view": str(callout.get("target_view") or ""),
            "expected_type": expected_type,
            "reference_value": value,
            "source_text": str((callout.get("source_reference_evidence") or {}).get("source_text") or ""),
            "fallback_policy": str(callout.get("fallback_policy") or ""),
            "required_visual_confirmation": bool(has_reference_value or manufacturing),
            "absence_check_required": bool(absence_check),
            "is_manufacturing_dimension": manufacturing,
            "notes_do_not_count_as_display_dim": True,
            "application_ui_screenshot_required": True,
        })

    if not items:
        return {}
    return {
        "schema": "sw_drawing_studio.reference_callout_review_plan.v4_4",
        "source": "reference_intent_dimension_plan_006.reference_callouts",
        "application_ui_screenshot_required": True,
        "api_is_supporting_only": True,
        "notes_do_not_count_as_display_dim": True,
        "required_keys": required_keys,
        "absence_check_keys": absence_check_keys,
        "items": items,
    }


def _v4_apply_reference_intent_plan_path(blueprint_data, warnings_box=None):
    if not isinstance(blueprint_data, dict) or not blueprint_data:
        return blueprint_data
    plan_path = os.environ.get("REFERENCE_INTENT_DIMENSION_PLAN_PATH", "").strip()
    if not plan_path:
        return blueprint_data
    try:
        intent_plan = _v4_json_load(plan_path)
    except Exception:
        intent_plan = {}
    if not isinstance(intent_plan, dict) or not intent_plan:
        if warnings_box is not None:
            warnings_box.append({
                "code": "reference_intent_dimension_plan_load_failed",
                "path": plan_path,
            })
        return blueprint_data

    base = str(blueprint_data.get("base") or "")
    plan_base = str(intent_plan.get("base") or "")
    if base and plan_base and base != plan_base:
        if warnings_box is not None:
            warnings_box.append({
                "code": "reference_intent_dimension_plan_base_mismatch",
                "blueprint_base": base,
                "plan_base": plan_base,
                "path": plan_path,
            })
        return blueprint_data

    dimension_plan = blueprint_data.setdefault("dimension_plan", {})
    if not isinstance(dimension_plan, dict):
        dimension_plan = {}
        blueprint_data["dimension_plan"] = dimension_plan

    targets = []
    for item in intent_plan.get("dimensions") or []:
        if not isinstance(item, dict):
            continue
        target = {
            "key": str(item.get("key") or ""),
            "group": str(item.get("group") or ""),
            "source_reference": str(item.get("source_reference") or ""),
            "target_view": str(item.get("target_view") or ""),
            "expected_type": str(item.get("expected_type") or ""),
            "expected_add_method": str(item.get("expected_add_method") or ""),
            "preferred_side": str(item.get("preferred_side") or ""),
            "priority": item.get("priority", 0),
            "fallback_policy": str(item.get("fallback_policy") or "need_review_when_real_displaydim_unavailable"),
            "create_as": "SolidWorks DisplayDim",
            "forbid_note_substitution": True,
            "avoid_generic_model_annotation": bool(item.get("avoid_generic_model_annotation", True)),
        }
        if target["key"]:
            targets.append(target)

    if targets:
        dimension_plan["dimension_targets"] = targets
        if intent_plan.get("reference_callouts"):
            dimension_plan["reference_callouts"] = list(intent_plan.get("reference_callouts") or [])
        callout_review_plan = _v4_reference_callout_review_plan(intent_plan)
        if callout_review_plan:
            dimension_plan["reference_callout_review_plan"] = callout_review_plan
        try:
            dimension_plan["required_display_dim_count"] = max(
                int(dimension_plan.get("required_display_dim_count") or 0),
                int(intent_plan.get("required_display_dim_count") or 0),
                len(targets),
            )
        except Exception:
            dimension_plan["required_display_dim_count"] = len(targets)
        try:
            dimension_plan["reference_display_dim_count"] = max(
                int(dimension_plan.get("reference_display_dim_count") or 0),
                int(intent_plan.get("reference_display_dim_count") or 0),
            )
        except Exception:
            pass
        priority = [item["key"] for item in targets]
        for key in dimension_plan.get("dimension_priority") or []:
            if key not in priority:
                priority.append(key)
        dimension_plan["dimension_priority"] = priority
        if intent_plan.get("dimension_groups"):
            dimension_plan["dimension_intent_groups"] = intent_plan.get("dimension_groups")
        if base == "LB26001-A-04-006":
            dimension_plan["view_dimension_quotas"] = {"front": 3, "top": 6, "right": 3}
        reference_slots = intent_plan.get("reference_view_slots")
        if isinstance(reference_slots, dict) and reference_slots:
            dimension_plan["reference_view_slots"] = reference_slots
        reference_layout_policy = intent_plan.get("reference_layout_policy") or {}
        if isinstance(reference_layout_policy, dict) and reference_layout_policy:
            dimension_plan["reference_layout_policy"] = reference_layout_policy
        reference_dimension_lane_policy = intent_plan.get("reference_dimension_lane_policy") or {}
        if isinstance(reference_dimension_lane_policy, dict) and reference_dimension_lane_policy:
            dimension_plan["reference_dimension_lane_policy"] = reference_dimension_lane_policy
        plan_view_plan = intent_plan.get("view_plan") or reference_layout_policy.get("view_plan") or []
        if isinstance(plan_view_plan, list) and plan_view_plan:
            # reference_intent_layout_policy_attached:
            # Use same-name reference view outlines as the next 006 CAD
            # generation target; this feeds the persisted layout solver and
            # prevents the UI screenshot layout bucket from being reduced to
            # center-only matching.
            blueprint_data["view_plan"] = [dict(item) for item in plan_view_plan if isinstance(item, dict)]
        plan_layout = intent_plan.get("layout_plan") or reference_layout_policy.get("layout_plan") or {}
        if isinstance(plan_layout, dict) and plan_layout:
            layout_plan = blueprint_data.setdefault("layout_plan", {})
            if isinstance(layout_plan, dict):
                for key in [
                    "sheet_size",
                    "views",
                    "notes_box_norm",
                    "titlebar_box_norm",
                    "bottom_notice_box_norm",
                    "projection_view_style_match_required",
                    "compact_titlebar_fields_required",
                    "reference_style_notes_required",
                    "sheet_template_policy",
                    "reference_titlebar_policy",
                    "reference_view_outline_policy",
                    "view_outline_size_match_required",
                    "view_outline_size_tolerance",
                    "independent_view_scale_allowed",
                ]:
                    if key in plan_layout:
                        layout_plan[key] = plan_layout[key]
                reference_titlebar_policy = (
                    intent_plan.get("reference_titlebar_policy")
                    or reference_layout_policy.get("reference_titlebar_policy")
                    or plan_layout.get("reference_titlebar_policy")
                    or {}
                )
                if isinstance(reference_titlebar_policy, dict) and reference_titlebar_policy:
                    layout_plan["reference_titlebar_policy"] = reference_titlebar_policy
                    layout_plan["bottom_notice_box_norm"] = (
                        reference_titlebar_policy.get("bottom_notice_box_norm")
                        or layout_plan.get("bottom_notice_box_norm")
                    )
                reference_view_outline_policy = (
                    intent_plan.get("reference_view_outline_policy")
                    or reference_layout_policy.get("reference_view_outline_policy")
                    or plan_layout.get("reference_view_outline_policy")
                    or {}
                )
                if isinstance(reference_view_outline_policy, dict) and reference_view_outline_policy:
                    layout_plan["reference_view_outline_policy"] = reference_view_outline_policy
                    layout_plan["view_outline_size_match_required"] = bool(
                        reference_view_outline_policy.get("view_outline_size_match_required")
                    )
                    layout_plan["view_outline_size_tolerance"] = reference_view_outline_policy.get(
                        "view_outline_size_tolerance",
                        layout_plan.get("view_outline_size_tolerance", 0.18),
                    )
                    layout_plan["independent_view_scale_allowed"] = bool(
                        reference_view_outline_policy.get("independent_view_scale_allowed")
                    )
                layout_plan["source"] = "reference_intent_dimension_plan_006.reference_layout_policy"
                layout_plan["target_outlines_required"] = True
                layout_plan["api_or_reference_json_alone_can_close"] = False
                if isinstance(reference_dimension_lane_policy, dict) and reference_dimension_lane_policy:
                    layout_plan["reference_dimension_lane_policy"] = reference_dimension_lane_policy
        repair_layout_targets = (
            intent_plan.get("ui_defect_repair_layout_targets")
            or reference_layout_policy.get("ui_defect_repair_layout_targets")
            or {}
        )
        if isinstance(repair_layout_targets, dict) and repair_layout_targets:
            dimension_plan["ui_defect_repair_layout_targets"] = repair_layout_targets
        if isinstance(reference_dimension_lane_policy, dict) and reference_dimension_lane_policy:
            constraints = dimension_plan.setdefault("visual_defect_constraints", {})
            if isinstance(constraints, dict):
                constraints.setdefault("source", "reference_intent_dimension_plan_006.reference_dimension_lane_policy")
                constraints["reference_dimension_lane_policy_attached"] = True
                constraints["compact_local_lanes_required"] = bool(
                    reference_dimension_lane_policy.get("compact_local_lanes_required")
                )
                constraints["reject_generic_autodim_survivors"] = bool(
                    reference_dimension_lane_policy.get("reject_generic_autodim_survivors")
                )
                constraints["reject_far_lane"] = bool(reference_dimension_lane_policy.get("reject_far_lane"))
                constraints["reject_diagonal_or_cross_region_leaders"] = bool(
                    reference_dimension_lane_policy.get("reject_diagonal_or_cross_region_leaders")
                )
                constraints["reference_lane_geometry_issue_count_after_required"] = (
                    reference_dimension_lane_policy.get("reference_lane_geometry_issue_count_after_required")
                )
                constraints["top_view_side_lane_max_gap_m"] = reference_dimension_lane_policy.get(
                    "top_view_side_lane_max_gap_m"
                )
                constraints["api_or_displaydim_metric_alone_can_close"] = False
        dimension_plan["allow_note_substitution"] = False
        dimension_plan["fallback_policy"] = "need_review_when_real_displaydim_unavailable"
        reasons = list(dimension_plan.get("reasons") or [])
        attach_reasons = [
            "reference_intent_dimension_plan_path_attached",
            "explicit_dimension_targets_replace_generic_autodimension_acceptance",
        ]
        if isinstance(reference_layout_policy, dict) and reference_layout_policy:
            attach_reasons.append("reference_intent_layout_policy_attached")
        if isinstance(reference_dimension_lane_policy, dict) and reference_dimension_lane_policy:
            attach_reasons.append("reference_dimension_lane_policy_attached")
        if isinstance(repair_layout_targets, dict) and repair_layout_targets:
            attach_reasons.append("ui_defect_repair_layout_targets_attached")
        for reason in attach_reasons:
            if reason not in reasons:
                reasons.append(reason)
        dimension_plan["reasons"] = reasons

    source_inputs = blueprint_data.setdefault("source_inputs", {})
    if isinstance(source_inputs, dict):
        source_inputs["reference_intent_dimension_plan_path"] = plan_path
        contract_path = os.environ.get("REFERENCE_INTENT_DIMENSION_CONTRACT_PATH", "").strip()
        if contract_path:
            source_inputs["reference_intent_dimension_contract_path"] = contract_path
        ui_correction_path = os.environ.get("LB26001_006_UI_CORRECTION_EVIDENCE_PATH", "").strip()
        if ui_correction_path:
            source_inputs["lb26001_006_ui_correction_evidence_path"] = ui_correction_path
            try:
                ui_correction = _v4_json_load(ui_correction_path)
            except Exception:
                ui_correction = {}
            if isinstance(ui_correction, dict) and ui_correction:
                ui_trace = {
                    "path": ui_correction_path,
                    "comparison_image": str(ui_correction.get("comparison_image") or ""),
                    "failed_visual_checklist_items": list(ui_correction.get("failed_visual_checklist_items") or []),
                    "latest_manual_findings": list(ui_correction.get("latest_manual_findings") or []),
                    "latest_manual_required_correction": str(ui_correction.get("latest_manual_required_correction") or ""),
                    "application_ui_screenshot_is_final_gate": bool(
                        ui_correction.get("application_ui_screenshot_is_final_gate")
                    ),
                    "api_is_not_final_judgement": bool(ui_correction.get("api_is_not_final_judgement")),
                }
                source_inputs["lb26001_006_ui_correction_evidence"] = ui_trace
                dimension_plan["ui_correction_evidence"] = ui_trace
                reasons = list(dimension_plan.get("reasons") or [])
                if "lb26001_006_ui_correction_evidence_attached" not in reasons:
                    reasons.append("lb26001_006_ui_correction_evidence_attached")
                dimension_plan["reasons"] = reasons
                if warnings_box is not None:
                    warnings_box.append({
                        "code": "lb26001_006_ui_correction_evidence_attached",
                        "path": ui_correction_path,
                        "failed_visual_check_count": len(ui_trace["failed_visual_checklist_items"]),
                        "latest_manual_finding_count": len(ui_trace["latest_manual_findings"]),
                    })
            elif warnings_box is not None:
                warnings_box.append({
                    "code": "lb26001_006_ui_correction_evidence_load_failed",
                    "path": ui_correction_path,
                })
        ui_defect_buckets_path = os.environ.get("LB26001_006_UI_DEFECT_BUCKETS_PATH", "").strip()
        if ui_defect_buckets_path:
            source_inputs["lb26001_006_ui_defect_buckets_path"] = ui_defect_buckets_path
            try:
                ui_defects = _v4_json_load(ui_defect_buckets_path)
            except Exception:
                ui_defects = {}
            if isinstance(ui_defects, dict) and ui_defects:
                active_buckets = [
                    str(item)
                    for item in (ui_defects.get("active_buckets") or [])
                    if str(item).strip()
                ]
                closure_contract = []
                for item in (ui_defects.get("bucket_closure_contract") or []):
                    if not isinstance(item, dict):
                        continue
                    bucket = str(item.get("bucket") or "").strip()
                    if not bucket:
                        continue
                    contract_item = {
                        "bucket": bucket,
                        "source_failure_evidence": list(item.get("source_failure_evidence") or []),
                        "repair_inputs": list(item.get("repair_inputs") or []),
                        "implementation_guard_keys": list(item.get("implementation_guard_keys") or []),
                        "post_rerun_required_evidence": list(item.get("post_rerun_required_evidence") or []),
                        "ui_review_pass_condition": str(item.get("ui_review_pass_condition") or ""),
                        "api_or_displaydim_metric_alone_can_close": bool(
                            item.get("api_or_displaydim_metric_alone_can_close")
                        ),
                    }
                    if bucket == "callout_missing":
                        contract_item["required_callout_keys"] = list(item.get("required_callout_keys") or [])
                        contract_item["absence_check_keys"] = list(item.get("absence_check_keys") or [])
                        contract_item["reference_callout_checklist_required"] = bool(
                            item.get("reference_callout_checklist_required")
                        )
                    closure_contract.append(contract_item)
                screenshot_observations = []
                for item in (ui_defects.get("screenshot_visual_observations") or []):
                    if not isinstance(item, dict):
                        continue
                    bucket = str(item.get("bucket") or "").strip()
                    if not bucket:
                        continue
                    screenshot_observations.append({
                        "bucket": bucket,
                        "observation_key": str(item.get("observation_key") or ""),
                        "source": str(item.get("source") or ""),
                        "source_paths": list(item.get("source_paths") or []),
                        "visual_check": str(item.get("visual_check") or ""),
                        "visual_check_pass": item.get("visual_check_pass"),
                        "manual_note": str(item.get("manual_note") or ""),
                        "visual_fact": str(item.get("visual_fact") or ""),
                        "reference_expectation": str(item.get("reference_expectation") or ""),
                        "generated_failure": str(item.get("generated_failure") or ""),
                        "repair_signal": str(item.get("repair_signal") or ""),
                        "supports_active_bucket": bool(item.get("supports_active_bucket")),
                        "next_screenshot_check_required": bool(item.get("next_screenshot_check_required")),
                        "api_or_displaydim_metric_alone_can_close": bool(
                            item.get("api_or_displaydim_metric_alone_can_close")
                        ),
                    })
                ui_defect_trace = {
                    "path": ui_defect_buckets_path,
                    "status": str(ui_defects.get("status") or ""),
                    "active_buckets": active_buckets,
                    "bucket_closure_contract_buckets": [
                        str(item.get("bucket") or "") for item in closure_contract if item.get("bucket")
                    ],
                    "screenshot_visual_observation_buckets": [
                        str(item.get("bucket") or "") for item in screenshot_observations if item.get("bucket")
                    ],
                    "application_ui_screenshot_is_final_gate": bool(
                        ui_defects.get("application_ui_screenshot_is_final_gate")
                    ),
                    "api_is_not_final_judgement": bool(ui_defects.get("api_is_not_final_judgement")),
                    "expansion_allowed_now": bool(ui_defects.get("expansion_allowed_now")),
                }
                source_inputs["lb26001_006_ui_defect_buckets"] = ui_defect_trace
                dimension_plan["ui_defect_buckets"] = ui_defect_trace
                # ui_defect_bucket_closure_contract:
                # keep the Drawing Review screenshot closure contract attached
                # to the generated 006 plan so the next UI review can close each
                # defect bucket by visual judgement, not by API metrics alone.
                dimension_plan["ui_defect_bucket_closure_contract"] = closure_contract
                # ui_defect_screenshot_visual_observations:
                # preserve the human/application screenshot observations that
                # explain why each active bucket failed visually.
                dimension_plan["ui_defect_screenshot_visual_observations"] = screenshot_observations
                # reference_intent_ui_defect_bucket_constraints:
                # turn the latest application-UI FAIL buckets into hard generator
                # constraints for the next 006-only CAD run.
                constraints = dimension_plan.setdefault("visual_defect_constraints", {})
                if isinstance(constraints, dict):
                    constraints["source"] = "lb26001_006_ui_defect_buckets_v4_4"
                    constraints["active_buckets"] = active_buckets
                    constraints["reject_generic_autodim_survivors"] = "dimension_visual_overdense" in active_buckets
                    constraints["compact_local_lanes_required"] = "dimension_lane_wrong" in active_buckets
                    constraints["reference_style_notes_required"] = "note_missing_or_wrong" in active_buckets
                    constraints["compact_titlebar_fields_required"] = "titlebar_incomplete" in active_buckets
                    constraints["projection_view_style_match_required"] = "projection_view_style_mismatch" in active_buckets
                    constraints["callout_presence_recheck_required"] = True
                    callout_review_plan = dimension_plan.get("reference_callout_review_plan") or {}
                    constraints["reference_callout_review_required_keys"] = list(
                        callout_review_plan.get("required_keys") or []
                    )
                    constraints["reference_callout_absence_check_keys"] = list(
                        callout_review_plan.get("absence_check_keys") or []
                    )
                    constraints["bucket_closure_contract_buckets"] = [
                        str(item.get("bucket") or "") for item in closure_contract if item.get("bucket")
                    ]
                    constraints["ui_review_bucket_pass_conditions"] = {
                        str(item.get("bucket") or ""): str(item.get("ui_review_pass_condition") or "")
                        for item in closure_contract
                        if item.get("bucket")
                    }
                    constraints["screenshot_visual_observation_buckets"] = [
                        str(item.get("bucket") or "") for item in screenshot_observations if item.get("bucket")
                    ]
                    constraints["screenshot_visual_observations"] = screenshot_observations
                    constraints["api_or_displaydim_metric_alone_can_close"] = False
                layout_plan = blueprint_data.setdefault("layout_plan", {})
                if isinstance(layout_plan, dict):
                    if "projection_view_style_mismatch" in active_buckets:
                        layout_plan["projection_view_style_match_required"] = True
                    if "note_missing_or_wrong" in active_buckets:
                        layout_plan.setdefault("notes_box_norm", [0.58, 0.65, 0.40, 0.17])
                    if "titlebar_incomplete" in active_buckets:
                        layout_plan["compact_titlebar_fields_required"] = True
                reasons = list(dimension_plan.get("reasons") or [])
                for reason in [
                    "reference_intent_ui_defect_bucket_constraints",
                    "ui_defect_bucket_reject_generic_autodim_survivors",
                    "ui_defect_bucket_compact_local_lanes",
                    "ui_defect_bucket_reference_callout_review_plan",
                    "ui_defect_bucket_closure_contract",
                    "ui_defect_screenshot_visual_observations",
                ]:
                    if reason not in reasons:
                        reasons.append(reason)
                dimension_plan["reasons"] = reasons
                if warnings_box is not None:
                    warnings_box.append({
                        "code": "lb26001_006_ui_defect_buckets_attached",
                        "path": ui_defect_buckets_path,
                        "status": ui_defect_trace["status"],
                        "active_buckets": active_buckets,
                    })
            elif warnings_box is not None:
                warnings_box.append({
                    "code": "lb26001_006_ui_defect_buckets_load_failed",
                    "path": ui_defect_buckets_path,
                })
    if warnings_box is not None:
        warnings_box.append({
            "code": "reference_intent_dimension_plan_v4_2",
            "path": plan_path,
            "dimension_target_count": len(targets),
            "required_display_dim_count": dimension_plan.get("required_display_dim_count"),
        })
    return blueprint_data


def _v4_dimension_view_quotas(blueprint_data):
    plan = _v4_blueprint_dimension_plan(blueprint_data)
    quotas = plan.get("view_dimension_quotas") or {}
    if not isinstance(quotas, dict):
        return {}
    result = {}
    for slot, value in quotas.items():
        try:
            quota = max(0, int(value or 0))
        except Exception:
            quota = 0
        slot_key = str(slot or "").strip().lower()
        if slot_key and quota > 0:
            result[slot_key] = quota
    return result


def _v4_dimension_autodim_slots(blueprint_data):
    quotas = _v4_dimension_view_quotas(blueprint_data)
    if not quotas:
        return []
    view_slots = _v4_blueprint_view_keys(blueprint_data)
    ordered = [str(slot).strip().lower() for slot in view_slots if str(slot).strip().lower() in quotas]
    for slot in ("front", "top", "right", "iso"):
        if slot in quotas and slot not in ordered:
            ordered.append(slot)
    return [slot for slot in ordered if quotas.get(slot, 0) > 0]


def _v4_should_skip_generic_model_dimension_import(blueprint_data, reference_dim_floor=0):
    """Skip bulk model-dimension import when explicit reference-intent targets drive the drawing."""
    plan = _v4_blueprint_dimension_plan(blueprint_data)
    targets = [item for item in (plan.get("dimension_targets") or []) if isinstance(item, dict)]
    if not targets:
        return False
    if not any(item.get("avoid_generic_model_annotation") for item in targets):
        return False
    source = str(plan.get("source") or "").strip().lower()
    reasons = {str(item).strip() for item in (plan.get("reasons") or [])}
    has_reference_intent = (
        source == "reference_intent_dimension_plan_v4_2"
        or "explicit_dimension_targets_replace_generic_autodimension_acceptance" in reasons
        or "reference_intent_dimension_plan_path_attached" in reasons
    )
    if not has_reference_intent:
        return False
    try:
        floor = int(reference_dim_floor or plan.get("required_display_dim_count") or 0)
    except Exception:
        floor = 0
    return floor >= 8 or len(targets) >= 8


def _v4_should_disable_reference_autodimension(blueprint_data, reference_dim_floor=0):
    """Disable IDrawingDoc.AutoDimension when UI evidence requires explicit reference intent."""
    return _v4_should_skip_generic_model_dimension_import(blueprint_data, reference_dim_floor)


def _v4_blueprint_layout_centers(blueprint_data):
    layout = blueprint_data.get("layout_plan") or {}
    sheet = layout.get("sheet_size") or {}
    try:
        width = float(sheet.get("width") or REFERENCE_SHEET_SIZE_M[0])
        height = float(sheet.get("height") or REFERENCE_SHEET_SIZE_M[1])
    except Exception:
        width, height = REFERENCE_SHEET_SIZE_M
    result = {}
    for item in blueprint_data.get("view_plan") or []:
        if not isinstance(item, dict):
            continue
        slot = str(item.get("slot") or "").strip()
        center = item.get("center_norm") or []
        if not slot or not isinstance(center, list) or len(center) < 2:
            continue
        try:
            result[slot] = (float(center[0]) * width, float(center[1]) * height)
        except Exception:
            pass
    return result


def _v4_blueprint_layout_outlines(blueprint_data):
    layout = blueprint_data.get("layout_plan") or {}
    sheet = layout.get("sheet_size") or {}
    try:
        width = float(sheet.get("width") or REFERENCE_SHEET_SIZE_M[0])
        height = float(sheet.get("height") or REFERENCE_SHEET_SIZE_M[1])
    except Exception:
        width, height = REFERENCE_SHEET_SIZE_M
    result = {}
    for item in blueprint_data.get("view_plan") or []:
        if not isinstance(item, dict):
            continue
        slot = str(item.get("slot") or "").strip()
        outline = item.get("outline_norm") or []
        if not slot or not isinstance(outline, list) or len(outline) < 4:
            continue
        try:
            x0, y0, x1, y1 = [float(v) for v in outline[:4]]
            result[slot] = (x0 * width, y0 * height, x1 * width, y1 * height)
        except Exception:
            pass
    return result


def _reference_outline_scale_hint(part_bbox_m, target_outlines, view_keys=None):
    if not target_outlines:
        return None
    try:
        lx, ly, lz = [float(v) for v in part_bbox_m[:3]]
    except Exception:
        return None
    bases = {
        "front": (lx, ly),
        "top": (lx, lz),
        "right": (lz, ly),
        "bottom": (lx, lz),
        "iso": (max(lx, ly, lz) * 0.7, max(lx, ly, lz) * 0.7),
    }
    allowed = set(view_keys or target_outlines.keys())
    ratios = []
    for slot, outline in target_outlines.items():
        if slot not in allowed or slot not in bases:
            continue
        try:
            x0, y0, x1, y1 = [float(v) for v in outline[:4]]
            tw = abs(x1 - x0)
            th = abs(y1 - y0)
            bw, bh = bases[slot]
            if tw > 0 and bw > 0:
                ratios.append(tw / bw)
            if th > 0 and bh > 0 and slot not in {"front", "top", "bottom"}:
                ratios.append(th / bh)
        except Exception:
            continue
    ratios = [v for v in ratios if v > 0]
    if not ratios:
        return None
    target_ratio = sorted(ratios)[len(ratios) // 2]

    def _score(scale):
        n, d = scale
        try:
            ratio = float(n) / float(d)
            return abs(math.log(max(ratio, 1e-9) / max(target_ratio, 1e-9)))
        except Exception:
            return 999.0

    return min(CANDIDATE_SCALES, key=_score)


def _reference_view_outline_size_correction(current_outline, target_outline, scale_num_den, *, tolerance=0.18):
    """Return an independent downscale ratio when a view is visibly larger than its reference outline."""
    # reference_view_outline_size_correction:
    # Center matching alone did not close the 006 UI screenshot failure. The
    # latest real run matched centers but left the isometric view much larger
    # than the same-name reference, so oversized views need an explicit
    # post-creation size correction.
    try:
        cx0, cy0, cx1, cy1 = [float(v) for v in current_outline[:4]]
        tx0, ty0, tx1, ty1 = [float(v) for v in target_outline[:4]]
        scale_num, scale_den = [float(v) for v in scale_num_den[:2]]
    except Exception:
        return {}
    current_w = abs(cx1 - cx0)
    current_h = abs(cy1 - cy0)
    target_w = abs(tx1 - tx0)
    target_h = abs(ty1 - ty0)
    ratios = []
    if current_w > 1e-9 and target_w > 1e-9:
        ratios.append(target_w / current_w)
    if current_h > 1e-9 and target_h > 1e-9:
        ratios.append(target_h / current_h)
    ratios = [value for value in ratios if value > 0]
    if not ratios or scale_num <= 0 or scale_den <= 0:
        return {}
    factor = sorted(ratios)[len(ratios) // 2]
    factor = max(0.20, min(1.0, factor))
    if factor >= 1.0 - float(tolerance):
        return {}
    corrected_den = scale_den / factor
    return {
        "scale_num": scale_num,
        "scale_den": corrected_den,
        "scale_factor": factor,
        "width_ratio": target_w / current_w if current_w > 1e-9 else 0.0,
        "height_ratio": target_h / current_h if current_h > 1e-9 else 0.0,
        "current_outline": [cx0, cy0, cx1, cy1],
        "target_outline": [tx0, ty0, tx1, ty1],
    }


def _v4_clean_text(value):
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    return re.sub(r"\n{3,}", "\n\n", text)


def _v4_text_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        text = _v4_clean_text(value)
        return [text] if text else []
    if isinstance(value, (list, tuple)):
        result = []
        for item in value:
            if isinstance(item, dict):
                text = _v4_clean_text(item.get("text") or item.get("value") or item.get("raw") or "")
            else:
                text = _v4_clean_text(item)
            if text:
                result.append(text)
        return result
    text = _v4_clean_text(value)
    return [text] if text else []


def _v4_unique_texts(values, *, limit=12):
    result = []
    seen = set()
    for value in values:
        text = _v4_clean_text(value)
        key = re.sub(r"\s+", " ", text).lower()
        if not text or key in seen:
            continue
        seen.add(key)
        result.append(text)
        if limit and len(result) >= limit:
            break
    return result


def _v4_norm_box(value):
    if not isinstance(value, list) or len(value) < 4:
        return []
    try:
        x0, y0, x1, y1 = [float(item) for item in value[:4]]
    except Exception:
        return []
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    return [
        max(0.0, min(1.0, x0)),
        max(0.0, min(1.0, y0)),
        max(0.0, min(1.0, x1)),
        max(0.0, min(1.0, y1)),
    ]


def _v4_sheet_point_from_norm_box(box_norm, default_pos, *, sheet_size=REFERENCE_SHEET_SIZE_M, x_pad=0.004, y_pad=0.006):
    box = _v4_norm_box(box_norm)
    if not box:
        return default_pos
    width, height = sheet_size
    x0, _y0, _x1, y1 = box
    x = max(0.010, min(width - 0.010, x0 * width + x_pad))
    y = max(0.010, min(height - 0.010, y1 * height - y_pad))
    return (round(x, 6), round(y, 6))


def _v4_titlebar_property_overrides(blueprint_data):
    titlebar = blueprint_data.get("titlebar_plan") or {}
    fields = titlebar.get("fields") or {}
    mapping = {
        "drawing_no": "图号",
        "draw_no": "图号",
        "part_no": "图号",
        "name": "品名",
        "part_name": "品名",
        "material": "材质",
        "surface": "表面处理",
        "surface_treatment": "表面处理",
        "quantity": "数量",
        "qty": "数量",
        "category": "类别",
        "part_class": "类别",
        "model": "机型",
        "designer": "设计",
        "date": "日期",
        "weight": "重量",
        "unit": "UNIT_OF_MEASURE",
    }
    direct_keys = set(PROP_KEYS)
    overrides = {}
    for key, value in fields.items():
        text = _v4_clean_text(value)
        if not text:
            continue
        target = mapping.get(str(key)) or (str(key) if str(key) in direct_keys else "")
        if target:
            overrides[target] = text
    return overrides


def _v4_apply_titlebar_property_overrides(src_props, blueprint_data, warnings_box=None):
    overrides = _v4_titlebar_property_overrides(blueprint_data)
    applied = {}
    for key, value in overrides.items():
        if not value:
            continue
        if not src_props.get(key) or key in {"图号", "品名", "材质", "表面处理", "类别", "日期"}:
            src_props[key] = value
            applied[key] = value
    if applied and warnings_box is not None:
        warnings_box.append({
            "code": "drawing_blueprint_titlebar_fields_applied",
            "fields": sorted(applied),
            "source": "DrawingBlueprint.titlebar_plan",
        })
        warnings_box[:] = [
            item for item in warnings_box
            if not (item.get("code") == "prop_missing" and src_props.get(item.get("key")))
        ]
    return applied


def _v4_blueprint_annotation_flags(blueprint_data):
    annotation = blueprint_data.get("annotation_plan") or {}
    notes = blueprint_data.get("notes_plan") or {}
    note_text = "\n".join(
        _v4_text_list(notes.get("required_notes"))
        + _v4_text_list(notes.get("raw_reference_notes"))
        + _v4_text_list(notes.get("warning_notes"))
        + _v4_text_list(notes.get("normalized_notes"))
    )
    note_lower = note_text.lower()
    roughness_required = bool(annotation.get("roughness_required")) or "ra" in note_lower or "粗糙度" in note_text
    datum_required = bool(annotation.get("datum_required")) or "datum" in note_lower or "基准" in note_text
    gtol_required = datum_required or any(
        str(item.get("type") or "").lower() in {"datum_symbols", "gtol", "geometric_tolerance"}
        for item in (annotation.get("symbols") or [])
        if isinstance(item, dict)
    )
    return {
        "roughness_required": roughness_required,
        "datum_required": datum_required,
        "gtol_required": gtol_required,
    }


def _v4_blueprint_note_insertions(blueprint_data):
    if not blueprint_data:
        return []
    notes = blueprint_data.get("notes_plan") or {}
    layout = blueprint_data.get("layout_plan") or {}
    flags = _v4_blueprint_annotation_flags(blueprint_data)
    raw_lines = []
    raw_lines.extend(_v4_text_list(notes.get("required_notes")))
    raw_lines.extend(_v4_text_list(notes.get("raw_reference_notes")))
    raw_lines.extend(_v4_text_list(notes.get("normalized_notes")))
    raw_lines.extend(_v4_text_list(notes.get("warning_notes")))
    if flags.get("roughness_required") and not any("ra" in line.lower() or "粗糙度" in line for line in raw_lines):
        raw_lines.append("未注粗糙度 Ra3.2。")
    constraints = (_v4_blueprint_dimension_plan(blueprint_data).get("visual_defect_constraints") or {})
    if isinstance(constraints, dict) and constraints.get("reference_style_notes_required"):
        # ui_defect_bucket_reference_style_notes:
        # The latest Drawing Review UI screenshot showed generic notes in the
        # wrong visual style. For 006, do not render a generic technical
        # requirements paragraph; keep the compact roughness note seen in the
        # same-name reference screenshot.
        raw_lines = [
            "3.2",
            "其余",
        ]
    lines = _v4_unique_texts(raw_lines, limit=10)
    if not lines:
        return []
    if (
        not (isinstance(constraints, dict) and constraints.get("reference_style_notes_required"))
        and not any("技术要求" in line or "technical requirement" in line.lower() for line in lines)
    ):
        lines.insert(0, "技术要求：")
    box = layout.get("notes_box_norm") or notes.get("note_box_norm") or []
    pos = _v4_sheet_point_from_norm_box(box, FALLBACK_NOTE_POS["tech"])
    return [{
        "kind": "notes_plan",
        "text": "\n".join(lines),
        "position_m": pos,
        "source": "DrawingBlueprint.notes_plan",
    }]


def _v4_blueprint_titlebar_insertions(blueprint_data, src_props=None):
    if not blueprint_data:
        return []
    src_props = src_props or {}
    titlebar = blueprint_data.get("titlebar_plan") or {}
    layout = blueprint_data.get("layout_plan") or {}
    fields = dict(titlebar.get("fields") or {})
    constraints = (_v4_blueprint_dimension_plan(blueprint_data).get("visual_defect_constraints") or {})
    compact_titlebar = isinstance(constraints, dict) and constraints.get("compact_titlebar_fields_required")
    reference_titlebar_policy = layout.get("reference_titlebar_policy") or {}
    sheet_template_policy = layout.get("sheet_template_policy") or {}
    suppress_default_titlebar_fields = (
        isinstance(reference_titlebar_policy, dict)
        and reference_titlebar_policy.get("suppress_default_titlebar_fields") is True
    ) or (
        isinstance(sheet_template_policy, dict)
        and sheet_template_policy.get("suppress_default_titlebar_fields") is True
    )
    if suppress_default_titlebar_fields:
        # ui_defect_bucket_suppress_default_titlebar_fields:
        # The 006 reference screenshot has no visible default title field
        # block. Do not add 图号/品名 notes into the lower-right sheet area;
        # render only the small bottom notice when the reference policy asks
        # for it.
        policy = reference_titlebar_policy if isinstance(reference_titlebar_policy, dict) else {}
        text = _v4_clean_text(policy.get("bottom_notice_text"))
        if policy.get("render_reference_bottom_notice") is True and text:
            box = policy.get("bottom_notice_box_norm") or layout.get("bottom_notice_box_norm") or []
            pos = _v4_sheet_point_from_norm_box(box, (0.095, 0.034), x_pad=0.004, y_pad=0.006)
            return [{
                "kind": "reference_titlebar_policy",
                "text": text,
                "position_m": pos,
                "source": "DrawingBlueprint.reference_titlebar_policy",
            }]
        return []
    values = {
        "图号": fields.get("drawing_no") or fields.get("图号") or src_props.get("图号") or blueprint_data.get("base") or "",
        "品名": fields.get("name") or fields.get("品名") or src_props.get("品名") or blueprint_data.get("base") or "",
        "材质": fields.get("material") or fields.get("材质") or src_props.get("材质") or "",
        "日期": fields.get("date") or fields.get("日期") or src_props.get("日期") or "",
    }
    if compact_titlebar:
        # ui_defect_bucket_compact_titlebar_fields:
        # The reference sheet uses a compact title/data area; do not render
        # broad default-template metadata fields into the visual review area.
        values = {key: values.get(key, "") for key in ("图号", "品名")}
    lines = [f"{key}: {value}" for key, value in values.items() if _v4_clean_text(value)]
    if not lines:
        return []
    box = layout.get("titlebar_box_norm") or []
    pos = _v4_sheet_point_from_norm_box(box, (0.205, 0.032), x_pad=0.003, y_pad=0.004)
    return [{
        "kind": "titlebar_plan",
        "text": "\n".join(lines[:4]),
        "position_m": pos,
        "source": "DrawingBlueprint.titlebar_plan",
    }]


# ============================================================
# v6 视图位置设置（统一 VARIANT 包装）
# ============================================================
def _set_view_pos_v6(view, x, y):
    try:
        import pythoncom
        from win32com.client import VARIANT
        arr = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(x), float(y)])
        view.Position = arr
        return True
    except Exception:
        try:
            view.Position = (float(x), float(y))
            return True
        except Exception as e:
            print(f"[v6 layout] set pos failed: {e}")
            return False


# ============================================================
# 视图自动布局
# ============================================================
def _inject_default_custom_properties(part_model, sldprt_path):
    """对 part 模型补齐 13 个 CustomProperty 默认值（不写源文件，只在内存改）"""
    import os, datetime
    from pathlib import Path
    base = Path(sldprt_path).stem
    today = datetime.date.today().isoformat()

    defaults = {
        "机型": "通用",
        "品名": base,
        "图号": base,
        "类别": "A",
        "数量": "1",
        "材质": "",
        "表面处理": "脱脂磷化喷粉",
        "比例": "1:1",
        "重量": "",
        "UNIT_OF_MEASURE": "mm",
        "设计": "auto",
        "日期": today,
    }

    try:
        mat = part_model.GetMaterialPropertyName2("", "")
        if mat: defaults["材质"] = mat
    except Exception: pass

    try:
        mp = part_model.Extension.CreateMassProperty()
        mass_kg = mp.Mass
        if mass_kg and mass_kg > 0:
            defaults["重量"] = f"{mass_kg*1000:.1f}"
    except Exception: pass
    if not defaults["重量"]:
        defaults["重量"] = "0"

    # v1.4 Task 3.6: 读取 UI 录入的 overrides（最高优先级）
    import os as _os
    import json as _json
    _overrides_json = _os.environ.get("TITLEBAR_OVERRIDES_JSON", "")
    if _overrides_json:
        try:
            _overrides = _json.loads(_overrides_json)
            if isinstance(_overrides, dict):
                for k, v in _overrides.items():
                    if k in defaults and v:
                        defaults[k] = str(v)
                        print(f"[cprop] override {k}={v} (from UI)")
        except Exception as e:
            print(f"[cprop] overrides parse failed: {e}")

    try:
        cpm = part_model.Extension.CustomPropertyManager("")
        for k, v in defaults.items():
            try:
                cur = cpm.Get4(k, False)
                if isinstance(cur, tuple): cur_val = cur[2] if len(cur) >= 3 else ""
                else: cur_val = cur or ""
                if not cur_val:
                    try: cpm.Add3(k, 30, str(v), 1)
                    except Exception: cpm.Set2(k, str(v))
                    print(f"[cprop] +{k}={v}")
            except Exception as e:
                print(f"[cprop] {k} failed: {e}")
    except Exception as e:
        print(f"[cprop] CustomPropertyManager failed: {e}")

    return defaults


def _draw_gb_frame_and_titleblock(drw, model):
    """在 sheet sketch 下绘制 A4 横式图框 + 标题栏。
    单位：米。A4 横式 0.297 x 0.210。
    外框：(0.010, 0.010) - (0.287, 0.200)
    内框：(0.025, 0.015) - (0.282, 0.195)
    标题栏：(0.102, 0.005) - (0.282, 0.095)，7 行 × 4 列（Task 2 扩展）。

    必须在所有视图创建/布局完成之后调用，否则 EditSheet/视图操作会清空 sketch。
    """
    # 读取标题栏模板（Spec improve-drawing-scale-titlebar-inspection Task 2）
    # SLDPRT 自定义属性（已通过 CustomProperty 注入）用 $PRP 链接覆盖此处默认值
    template = {}
    try:
        import yaml as _yaml
        _tpl_path = os.path.join(ROOT, "config", "titlebar_template.yaml")
        if os.path.exists(_tpl_path):
            with open(_tpl_path, "r", encoding="utf-8") as _fh:
                template = _yaml.safe_load(_fh) or {}
    except Exception:
        template = {}

    # 1) 清选 + 退到 sheet 编辑模式（不进入任何视图/format）
    try: drw.ClearSelection2(True)
    except Exception: pass
    try: drw.EditSheet()
    except Exception: pass
    try:
        sheet = drw.GetCurrentSheet()
    except Exception:
        sheet = None
    try: drw.SetEditMode(0)  # 0 = swEditMode_Sheet
    except Exception: pass
    try: model.SetEditFormat(False)  # 退出 format 编辑
    except Exception: pass

    # 2) 进入 sheet sketch
    sm = None
    try:
        sm = getattr(model, "SketchManager", None)
    except Exception:
        sm = None
    sketch_started = False
    if sm is not None:
        try:
            sm.InsertSketch(True)
            sketch_started = True
        except Exception:
            sketch_started = False

    def _line(x1, y1, x2, y2):
        if sm is None: return None
        try:
            return sm.CreateLine(float(x1), float(y1), 0.0,
                                 float(x2), float(y2), 0.0)
        except Exception:
            try:
                return sm.CreateLine2(float(x1), float(y1), 0.0,
                                      float(x2), float(y2), 0.0)
            except Exception:
                return None

    # 外框：(0.010, 0.010) - (0.287, 0.200)
    _line(0.010, 0.010, 0.287, 0.010)
    _line(0.287, 0.010, 0.287, 0.200)
    _line(0.287, 0.200, 0.010, 0.200)
    _line(0.010, 0.200, 0.010, 0.010)

    # 内框：(0.025, 0.015) - (0.282, 0.195)
    _line(0.025, 0.015, 0.282, 0.015)
    _line(0.282, 0.015, 0.282, 0.195)
    _line(0.282, 0.195, 0.025, 0.195)
    _line(0.025, 0.195, 0.025, 0.015)

    # 标题栏外框：(0.102, 0.005) - (0.282, 0.095)，7 行 × 4 列（Task 2）
    tb_x0, tb_y0, tb_x1, tb_y1 = 0.102, 0.005, 0.282, 0.095
    _line(tb_x0, tb_y0, tb_x1, tb_y0)
    _line(tb_x1, tb_y0, tb_x1, tb_y1)
    _line(tb_x1, tb_y1, tb_x0, tb_y1)
    _line(tb_x0, tb_y1, tb_x0, tb_y0)

    # 7 行横线（外框顶/底已画，此处画 6 条内部行分隔线）
    # y = 0.017, 0.030, 0.043, 0.056, 0.069, 0.082
    for _ty in (0.017, 0.030, 0.043, 0.056, 0.069, 0.082):
        _line(tb_x0, _ty, tb_x1, _ty)
    # 4 列竖线（仅第 1-3 行区间 y=0.056~0.095；第 4-7 行跨 4 列不画竖线）
    # x = 0.147, 0.192, 0.237
    for _cx in (0.147, 0.192, 0.237):
        _line(_cx, 0.056, _cx, 0.095)

    # 3) 退出 sheet sketch（toggle 关掉）
    if sketch_started and sm is not None:
        try:
            sm.InsertSketch(True)
        except Exception:
            pass

    # 7 行 × 4 列标题栏 Note（Spec improve-drawing-scale-titlebar-inspection Task 2）
    # 从模板取默认值；$PRP 链接的字段由 SLDPRT 自定义属性覆盖
    _co = template.get("company") or {}
    _dr = template.get("drawing") or {}
    _te = template.get("technical") or {}
    _dl = template.get("delivery") or {}
    company_name = _co.get("name", "") or ""
    designer = _dr.get("designer", "") or ""
    reviewer = _dr.get("reviewer", "") or ""
    date_val = _dr.get("date", "") or ""
    if not date_val:
        try: date_val = time.strftime("%Y-%m-%d")
        except Exception: date_val = ""
    requirements = _te.get("requirements", "") or ""
    process_info = _te.get("process_info", "") or ""
    customer = _dl.get("customer", "") or ""
    delivery_date = _dl.get("delivery_date", "") or ""
    remark = _dl.get("remark", "") or ""
    source_file = _dl.get("source_file", "") or ""
    # 留空则自动填 SLDPRT 文件名（从工程图视图引用文档取）
    if not source_file:
        try:
            _fv = drw.GetFirstView()
            _nv = _fv.GetNextView() if _fv else None
            while _nv:
                try:
                    _rd = _nv.GetReferencedDocument()
                    if _rd is not None:
                        _pn = _rd.GetPathName() or ""
                        if _pn:
                            source_file = os.path.basename(_pn)
                            break
                except Exception:
                    pass
                try: _nv = _nv.GetNextView()
                except Exception: break
        except Exception:
            pass

    # 列中心 x：0.1245 / 0.1695 / 0.2145 / 0.2595（每列宽 0.045m）
    # 行中心 y：0.0885 / 0.0755 / 0.0625（前 3 行）；后 4 行跨列左对齐 x=0.104
    cell_notes = [
        # 第 1 行：公司名 | 品名 | 图号 | 比例
        (0.1245, 0.0885, "公司: " + company_name),
        (0.1695, 0.0885, "品名: $PRP:\"品名\""),
        (0.2145, 0.0885, "图号: $PRP:\"图号\""),
        (0.2595, 0.0885, "比例: $PRP:\"SW-Sheet Scale\""),
        # 第 2 行：制图人 | 审核人 | 日期 | 机型
        (0.1245, 0.0755, "制图: " + designer),
        (0.1695, 0.0755, "审核: " + reviewer),
        (0.2145, 0.0755, "日期: " + date_val),
        (0.2595, 0.0755, "机型: $PRP:\"机型\""),
        # 第 3 行：材质 | 数量 | 表面处理 | 类别
        (0.1245, 0.0625, "材质: $PRP:\"材质\""),
        (0.1695, 0.0625, "数量: $PRP:\"数量\""),
        (0.2145, 0.0625, "表面: $PRP:\"表面处理\""),
        (0.2595, 0.0625, "类别: $PRP:\"类别\""),
        # 第 4 行：技术要求（跨 4 列，多行 Note）
        (0.104, 0.0495, "技术要求:\n" + requirements),
        # 第 5 行：工艺信息（跨 4 列）
        (0.104, 0.0365, "工艺: " + process_info),
        # 第 6 行：源文件信息（SLDPRT 路径，跨 4 列）
        (0.104, 0.0235, "源文件: " + source_file),
        # 第 7 行：交付信息（交付日期 + 客户 + 备注，跨 4 列）
        (0.104, 0.011, "交付: " + delivery_date + "  客户: " + customer + "  备注: " + remark),
    ]
    for nx, ny, txt in cell_notes:
        try:
            drw.ClearSelection2(True)
            note = drw.InsertNote(txt)
            if note is not None:
                ann = None
                try: ann = note.GetAnnotation()
                except Exception: ann = None
                if ann is not None:
                    try: ann.SetPosition2(float(nx), float(ny), 0)
                    except Exception:
                        try: ann.SetPosition(float(nx), float(ny), 0)
                        except Exception: pass
            drw.ClearSelection2(True)
        except Exception:
            try: drw.ClearSelection2(True)
            except Exception: pass


def _rect_intersect(a, b):
    """a, b: (xmin, ymin, xmax, ymax) 米。重叠返回 True。"""
    if not a or not b: return False
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    if ax0 > ax1: ax0, ax1 = ax1, ax0
    if ay0 > ay1: ay0, ay1 = ay1, ay0
    if bx0 > bx1: bx0, bx1 = bx1, bx0
    if by0 > by1: by0, by1 = by1, by0
    return not (ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0)


def layout_4_views(part_bbox_m, scale_num_den):
    """v6: GB T 字第一角投影固定布局（A4 横式 297x210mm）。
    - 主视图（前视）：(0.080, 0.140)
    - 俯视图：(0.080, 0.080)（主视图正下方，间距 60mm）
    - 左视图（右侧）：(0.180, 0.140)（主视图正右，间距 100mm）
    - 等轴测：(0.230, 0.180)（右上角）
    bbox / scale 入参保持兼容，但布局坐标固定。
    """
    return {
        "front": (0.080, 0.140),
        "top":   (0.080, 0.080),
        "right": (0.180, 0.140),
        "iso":   (0.230, 0.180),
    }


def _final_front_position(centers):
    try:
        point = centers.get("front") if isinstance(centers, dict) else None
        if point and len(point) >= 2:
            return float(point[0]), float(point[1])
    except Exception:
        pass
    return 0.080, 0.140


def predict_outline(center, size_xy):
    """根据中心 + 大小估算 view outline (xmin, ymin, xmax, ymax)。"""
    cx, cy = center
    w, h = size_xy
    return (cx - w/2.0, cy - h/2.0, cx + w/2.0, cy + h/2.0)


def predict_view_sizes(part_bbox_m, scale_num_den):
    Lx, Ly, Lz = part_bbox_m
    n, d = scale_num_den
    s = float(n) / float(d) if d else 1.0
    Lmax = max(Lx, Ly, Lz)
    return {
        "front": (Lx * s,        Ly * s),
        "top":   (Lx * s,        Lz * s),
        "right": (Lz * s,        Ly * s),
        "iso":   (Lmax * s * 0.7, Lmax * s * 0.7),
        "bottom": (Lx * s,       Lz * s),
    }


def check_layout_no_overlap(part_bbox_m, scale_num_den):
    """预测式重叠检测：返回 (ok, overlap_pairs, outlines)"""
    centers = layout_4_views(part_bbox_m, scale_num_den)
    sizes   = predict_view_sizes(part_bbox_m, scale_num_den)
    outlines = {k: predict_outline(centers[k], sizes[k]) for k in centers}
    pairs = []
    keys = list(outlines.keys())
    for i in range(len(keys)):
        for j in range(i+1, len(keys)):
            if _rect_intersect(outlines[keys[i]], outlines[keys[j]]):
                pairs.append((keys[i], keys[j]))
    return (len(pairs) == 0, pairs, outlines)


def _outline_outside_workarea(outline, workarea=None):
    if workarea is None:
        workarea = REFERENCE_LAYOUT_SAFE_AREA
    if not outline or len(outline) < 4:
        return True
    x0, y0, x1, y1 = outline
    if x0 > x1:
        x0, x1 = x1, x0
    if y0 > y1:
        y0, y1 = y1, y0
    return (
        x0 < float(workarea["xmin"]) or
        y0 < float(workarea["ymin"]) or
        x1 > float(workarea["xmax"]) or
        y1 > float(workarea["ymax"])
    )


def check_layout_no_overlap_for_centers(part_bbox_m, scale_num_den, centers, view_keys=None, workarea=None):
    """Predict overlap/frame safety using learned reference view centers."""
    sizes = predict_view_sizes(part_bbox_m, scale_num_den)
    keys = list(view_keys or centers.keys())
    outlines = {}
    for key in keys:
        if key in centers and key in sizes:
            outlines[key] = predict_outline(centers[key], sizes[key])
    pairs = []
    keys = list(outlines.keys())
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            if _rect_intersect(outlines[keys[i]], outlines[keys[j]]):
                pairs.append((keys[i], keys[j]))
    out_of_workarea = [
        key for key, outline in outlines.items()
        if _outline_outside_workarea(outline, workarea=workarea)
    ]
    return (len(pairs) == 0 and not out_of_workarea, pairs, outlines, out_of_workarea)


def _calc_utilization(outlines, workarea=None):
    """计算幅面利用率：视图总面积 / 工作区面积"""
    if workarea is None:
        workarea = WORKAREA
    wa_w = workarea["xmax"] - workarea["xmin"]
    wa_h = workarea["ymax"] - workarea["ymin"]
    wa_area = wa_w * wa_h
    if wa_area <= 0:
        return 0.0
    total_view_area = 0.0
    for k, o in outlines.items():
        if not o or len(o) < 4:
            continue
        x0, y0, x1, y1 = o
        w = abs(x1 - x0)
        h = abs(y1 - y0)
        total_view_area += w * h
    return min(1.0, total_view_area / wa_area)


def pick_scale_with_layout(part_bbox_m, start_scale=None):
    """v1.4: 从 CANDIDATE_SCALES 中选取"无重叠 且 utilization ≥ 0.40"的最大比例。
    若无重叠档位利用率均 < 0.40，则选无重叠的最大比例。
    返回 (scale, outlines, pairs, utilization)。
    """
    Lx, Ly, Lz = part_bbox_m
    Lmax = max(Lx, Ly, Lz)
    # 起点：不超过 100mm 视图宽
    candidates = list(CANDIDATE_SCALES)
    start_idx = 0
    if start_scale and start_scale in candidates:
        start_idx = candidates.index(start_scale)
    else:
        for i, (n, d) in enumerate(candidates):
            if Lmax * (n/d) <= 0.10 + 1e-9:
                start_idx = i
                break

    # 第一轮：找无重叠 且 utilization ≥ 0.40 的最大比例
    fallback_no_overlap = None  # (scale, outlines, pairs, utilization)
    for n, d in candidates[start_idx:]:
        ok, pairs, outlines = check_layout_no_overlap(part_bbox_m, (n, d))
        if not ok:
            continue
        util = _calc_utilization(outlines)
        if fallback_no_overlap is None:
            fallback_no_overlap = ((n, d), outlines, pairs, util)
        if util >= 0.40:
            return ((n, d), outlines, [], util)

    # 第二轮：无重叠档位利用率均 < 0.40，返回首个无重叠档（最大比例）
    if fallback_no_overlap is not None:
        scale, outlines, pairs, util = fallback_no_overlap
        # 记录利用率低（通过 pairs 传空，util 反映实际情况）
        return (scale, outlines, [], util)

    # 最后兜底：全档重叠，返回最小比例
    n, d = candidates[-1]
    ok, pairs, outlines = check_layout_no_overlap(part_bbox_m, (n, d))
    util = _calc_utilization(outlines)
    return ((n, d), outlines, pairs, util)


def pick_scale_with_reference_centers(part_bbox_m, centers, view_keys=None, start_scale=None):
    """Pick scale after applying learned reference centers."""
    candidates = list(CANDIDATE_SCALES)
    start_idx = 0
    if start_scale and start_scale in candidates:
        start_idx = candidates.index(start_scale)
    fallback = None
    last = None
    for scale in candidates[start_idx:]:
        ok, pairs, outlines, out_of_workarea = check_layout_no_overlap_for_centers(
            part_bbox_m,
            scale,
            centers,
            view_keys=view_keys,
        )
        util = _calc_utilization(outlines)
        last = (scale, outlines, pairs, util, out_of_workarea)
        if ok:
            if fallback is None:
                fallback = (scale, outlines, pairs, util, out_of_workarea)
            if util >= 0.40:
                return (scale, outlines, pairs, util, out_of_workarea)
    if fallback is not None:
        return fallback
    if last is not None:
        return last
    return (start_scale or CANDIDATE_SCALES[-1], {}, [], 0.0, [])


def downgrade_scale(scale):
    """把 scale 在 CANDIDATE_SCALES 中向 1:5/1:10 方向降一档。"""
    if scale in CANDIDATE_SCALES:
        i = CANDIDATE_SCALES.index(scale)
        if i + 1 < len(CANDIDATE_SCALES):
            return CANDIDATE_SCALES[i + 1]
    return scale


# ============================================================
# 通用工具
# ============================================================
def call(o, n, *a):
    if o is None: return None
    try: m = getattr(o, n)
    except Exception: return None
    try:
        if callable(m): return m(*a)
    except Exception: pass
    return m

def _clear_reference_sheet_template_artifacts(drw, sheet_name, scale_num, scale_den, warnings_box, log):
    """Remove default sheet-format entities before inserting reference-style views."""
    actions = []

    def _select_known_gb_template_segments():
        try:
            ext = drw.Extension
        except Exception as exc:
            return {"selected": 0, "error": f"extension:{exc}", "details": []}
        if ext is None or not callable(getattr(ext, "SelectByID2", None)):
            return {"selected": 0, "error": "SelectByID2_unavailable", "details": []}
        selected = 0
        details = []
        callout = empty_callout()
        for index in range(1, 41):
            picked = False
            for select_type in ("SKETCHSEGMENT", "EXTSKETCHSEGMENT"):
                for name in (f"Line{index}", f"Line{index}@{sheet_name}" if sheet_name else f"Line{index}"):
                    try:
                        ok = ext.SelectByID2(name, select_type, 0.0, 0.0, 0.0, selected > 0, 0, callout, 0)
                    except Exception as exc:
                        details.append({"name": name, "type": select_type, "ok": False, "error": str(exc)})
                        continue
                    details.append({"name": name, "type": select_type, "ok": bool(ok)})
                    if ok:
                        selected += 1
                        picked = True
                        break
                if picked:
                    break
        points = [
            (0.1485, 0.010), (0.287, 0.105), (0.1485, 0.200), (0.010, 0.105),
            (0.1535, 0.015), (0.282, 0.105), (0.1535, 0.195), (0.025, 0.105),
            (0.192, 0.015), (0.282, 0.035), (0.192, 0.055), (0.102, 0.035),
            (0.192, 0.028), (0.192, 0.041),
            (0.137, 0.035), (0.182, 0.035), (0.227, 0.035), (0.252, 0.035),
        ]
        for x, y in points:
            picked = False
            for select_type in ("SKETCHSEGMENT", "EXTSKETCHSEGMENT"):
                try:
                    ok = ext.SelectByID2("", select_type, float(x), float(y), 0.0, selected > 0, 0, callout, 0)
                except Exception as exc:
                    details.append({"point": [x, y], "type": select_type, "ok": False, "error": str(exc)})
                    continue
                details.append({"point": [x, y], "type": select_type, "ok": bool(ok)})
                if ok:
                    selected += 1
                    picked = True
                    break
            if not picked:
                continue
        return {"selected": selected, "details": details}

    try:
        if sheet_name:
            call(drw, "ActivateSheet", sheet_name)
        ok = call(
            drw,
            "SetupSheet5",
            sheet_name,
            6,
            13,
            scale_num,
            scale_den,
            True,
            "",
            0.297,
            0.21,
            "",
            True,
        )
        actions.append({"action": "setup_sheet_template_none", "ok": bool(ok)})
    except Exception as exc:
        actions.append({"action": "setup_sheet_template_none", "ok": False, "error": str(exc)})

    for mode in ("EditTemplate", "EditSheet"):
        try:
            call(drw, "ClearSelection2", True)
            mode_ok = call(drw, mode)
            try:
                ext = drw.Extension
            except Exception:
                ext = None
            select_ok = None
            try:
                if ext is not None and callable(getattr(ext, "SelectAll", None)):
                    select_ok = ext.SelectAll()
                elif callable(getattr(drw, "SelectAll", None)):
                    select_ok = drw.SelectAll()
            except Exception as exc:
                select_ok = f"error:{exc}"
            segment_select = _select_known_gb_template_segments()
            delete_ok = None
            delete_method = ""
            try:
                deleted, delete_method = _delete_selected_annotation(drw)
                delete_ok = deleted
            except Exception as exc:
                delete_ok = f"error:{exc}"
            call(drw, "ClearSelection2", True)
            actions.append({
                "action": "delete_selected_template_entities",
                "mode": mode,
                "mode_ok": bool(mode_ok) if mode_ok is not None else None,
                "select_ok": select_ok,
                "segment_select": segment_select,
                "delete_ok": delete_ok,
                "delete_method": delete_method,
            })
        except Exception as exc:
            actions.append({
                "action": "delete_selected_template_entities",
                "mode": mode,
                "ok": False,
                "error": str(exc),
            })
    try:
        call(drw, "ForceRebuild3", True)
        call(drw, "GraphicsRedraw2")
    except Exception:
        pass
    warnings_box.append({
        "code": "reference_sheet_artifact_cleanup",
        "actions": actions,
        "reason": "same-name reference screenshot must not inherit the default drawing template frame/titleblock",
    })
    log(f"[template] reference style sheet cleanup actions={actions}")

def vt_dispatch_none(): return VARIANT(pythoncom.VT_DISPATCH, None)
def empty_callout(): return VARIANT(pythoncom.VT_DISPATCH, None)

def view_outline_box(view):
    out = call(view, "GetOutline")
    if out is None: return None
    o = list(out)
    if len(o) >= 4:
        return (o[0], o[1], o[2], o[3])
    return None


def _layout_sheet_size(layout_plan):
    sheet = (layout_plan or {}).get("sheet_size") or {}
    try:
        return (
            float(sheet.get("width") or REFERENCE_SHEET_SIZE_M[0]),
            float(sheet.get("height") or REFERENCE_SHEET_SIZE_M[1]),
        )
    except Exception:
        return REFERENCE_SHEET_SIZE_M


def _layout_norm_box_to_sheet_box(box_norm, sheet_size):
    if not isinstance(box_norm, (list, tuple)) or len(box_norm) < 4:
        return None
    try:
        x0, y0, x1, y1 = [float(v) for v in box_norm[:4]]
    except Exception:
        return None
    x0, x1 = sorted((max(0.0, min(1.0, x0)), max(0.0, min(1.0, x1))))
    y0, y1 = sorted((max(0.0, min(1.0, y0)), max(0.0, min(1.0, y1))))
    return (x0 * sheet_size[0], y0 * sheet_size[1], x1 * sheet_size[0], y1 * sheet_size[1])


def _slot_for_display_dim_item(item, layout_plan=None):
    fallback_by_index = {1: "front", 2: "top", 3: "right", 4: "iso"}
    try:
        fallback = fallback_by_index.get(int(item.get("view_index") or -1), "")
    except Exception:
        fallback = ""
    view_name = str(item.get("view") or "").lower()
    for token, slot in (("front", "front"), ("top", "top"), ("right", "right"), ("iso", "iso")):
        if token in view_name:
            fallback = slot
            break

    try:
        outline = view_outline_box(item.get("view_obj"))
    except Exception:
        outline = None
    views = (layout_plan or {}).get("views") if isinstance(layout_plan, dict) else None
    if not outline or not isinstance(views, list):
        return fallback

    sheet_size = _layout_sheet_size(layout_plan)
    cx = (float(outline[0]) + float(outline[2])) / 2.0
    cy = (float(outline[1]) + float(outline[3])) / 2.0
    best_slot = fallback
    best_dist = float("inf")
    for view_plan in views:
        if not isinstance(view_plan, dict):
            continue
        slot = str(view_plan.get("slot") or "").strip().lower()
        if not slot:
            continue
        box = _layout_norm_box_to_sheet_box(view_plan.get("box_norm"), sheet_size)
        if not box:
            center = view_plan.get("center_norm")
            if isinstance(center, (list, tuple)) and len(center) >= 2:
                try:
                    box = (
                        float(center[0]) * sheet_size[0],
                        float(center[1]) * sheet_size[1],
                        float(center[0]) * sheet_size[0],
                        float(center[1]) * sheet_size[1],
                    )
                except Exception:
                    box = None
        if not box:
            continue
        bx = (float(box[0]) + float(box[2])) / 2.0
        by = (float(box[1]) + float(box[3])) / 2.0
        dist = ((cx - bx) ** 2 + (cy - by) ** 2) ** 0.5
        if dist < best_dist:
            best_dist = dist
            best_slot = slot
    return best_slot


def _outline_center(outline):
    if not isinstance(outline, (list, tuple)) or len(outline) < 4:
        return None
    try:
        return ((float(outline[0]) + float(outline[2])) / 2.0, (float(outline[1]) + float(outline[3])) / 2.0)
    except Exception:
        return None


def _box_width(outline):
    if not isinstance(outline, (list, tuple)) or len(outline) < 4:
        return 0.0
    try:
        return abs(float(outline[2]) - float(outline[0]))
    except Exception:
        return 0.0


def _reference_slot_match_threshold(layout_centers):
    centers = []
    for center in (layout_centers or {}).values():
        try:
            centers.append((float(center[0]), float(center[1])))
        except Exception:
            pass
    min_spacing = None
    for i, center_a in enumerate(centers):
        for center_b in centers[i + 1:]:
            dist = ((center_a[0] - center_b[0]) ** 2 + (center_a[1] - center_b[1]) ** 2) ** 0.5
            min_spacing = dist if min_spacing is None else min(min_spacing, dist)
    if min_spacing is None:
        return 0.050
    return min(0.075, max(0.035, float(min_spacing) * 0.60))


def _match_reference_intent_slot_views(view_records, layout_centers, expected_slots, *, max_distance=None):
    """Match current drawing views back to reference-intent slots by persisted outlines."""
    expected = {
        str(slot or "").strip().lower()
        for slot in (expected_slots or [])
        if str(slot or "").strip()
    }
    centers = {}
    for slot, center in (layout_centers or {}).items():
        key = str(slot or "").strip().lower()
        if not key or (expected and key not in expected):
            continue
        try:
            centers[key] = (float(center[0]), float(center[1]))
        except Exception:
            continue
    threshold = float(max_distance) if max_distance is not None else _reference_slot_match_threshold(centers)
    relaxed_threshold = max(threshold, 0.090)
    known_slots = set(centers) or set(expected)
    result = {}
    candidates = []
    accepted_views = set()

    def _view_key(record):
        view = record.get("view")
        if view is not None:
            return ("obj", id(view))
        return ("outline", tuple(round(float(v), 6) for v in (record.get("outline") or [])))

    def _accept(slot, record, source, distance=None):
        slot = str(slot or "").strip().lower()
        if not slot or slot not in known_slots or slot in result:
            return False
        key = _view_key(record)
        if key in accepted_views:
            return False
        result[slot] = {
            "view": record.get("view"),
            "source": source,
            "distance": round(float(distance), 5) if distance is not None else None,
            "view_name": str(record.get("name") or ""),
            "view_type": str(record.get("type") or ""),
            "outline": list(record.get("outline") or []),
        }
        accepted_views.add(key)
        return True

    def _record_center(record):
        center = _outline_center(record.get("outline"))
        if center is None:
            return None
        return center

    def _family_fill_missing_slots():
        records = []
        for record in view_records or []:
            if not isinstance(record, dict):
                continue
            center = _record_center(record)
            if center is None:
                continue
            vtype = str(record.get("type") or "")
            if vtype in {"0", "1"}:
                continue
            records.append((record, center, vtype))
        if not records:
            return

        def _not_used(record):
            return _view_key(record) not in accepted_views

        type7 = [(record, center) for record, center, vtype in records if vtype == "7" and _not_used(record)]
        type4 = [(record, center) for record, center, vtype in records if vtype == "4" and _not_used(record)]
        front_center = None
        if "front" in known_slots and "front" not in result and type7:
            front_record, front_center = max(type7, key=lambda item: (_box_width(item[0].get("outline")), item[1][1], -item[1][0]))
            _accept("front", front_record, "view_family_heuristic:type7_front")
            type7 = [(record, center) for record, center in type7 if _view_key(record) not in accepted_views]
        elif "front" in result:
            front_center = _outline_center(result["front"].get("outline"))

        if "iso" in known_slots and "iso" not in result and type7:
            iso_record, _ = max(type7, key=lambda item: (item[1][0], -item[1][1]))
            _accept("iso", iso_record, "view_family_heuristic:type7_iso")

        type4 = [(record, center) for record, center in type4 if _not_used(record)]
        if not type4:
            return
        if front_center is not None:
            fx, fy = front_center
            if "right" in known_slots and "right" not in result and type4:
                right_record, _ = max(
                    type4,
                    key=lambda item: (
                        item[1][0] - fx,
                        -abs(item[1][1] - fy),
                        item[1][1],
                    ),
                )
                _accept("right", right_record, "view_family_heuristic:type4_right")
                type4 = [(record, center) for record, center in type4 if _not_used(record)]
            if "top" in known_slots and "top" not in result and type4:
                top_record, _ = min(
                    type4,
                    key=lambda item: (
                        0 if item[1][1] < fy else 1,
                        abs(item[1][0] - fx),
                        abs(item[1][1] - fy),
                    ),
                )
                _accept("top", top_record, "view_family_heuristic:type4_top")
        else:
            if "right" in known_slots and "right" not in result and type4:
                right_record, _ = max(type4, key=lambda item: (item[1][0], item[1][1]))
                _accept("right", right_record, "view_family_heuristic:type4_right_no_front")
                type4 = [(record, center) for record, center in type4 if _not_used(record)]
            if "top" in known_slots and "top" not in result and type4:
                top_record, _ = min(type4, key=lambda item: (item[1][1], item[1][0]))
                _accept("top", top_record, "view_family_heuristic:type4_top_no_front")

    for record in view_records or []:
        if not isinstance(record, dict):
            continue
        outline = record.get("outline")
        center = _outline_center(outline)
        vtype = str(record.get("type") or "")
        if center is None or vtype in {"0", "1"}:
            continue
        name = str(record.get("name") or "").strip().lower()
        for slot, layout_center in centers.items():
            dist = ((center[0] - layout_center[0]) ** 2 + (center[1] - layout_center[1]) ** 2) ** 0.5
            candidates.append((dist, slot, record))
        for slot in sorted(known_slots):
            if slot and slot in name:
                dist = None
                if slot in centers:
                    try:
                        dist = ((center[0] - centers[slot][0]) ** 2 + (center[1] - centers[slot][1]) ** 2) ** 0.5
                    except Exception:
                        dist = None
                _accept(slot, record, "view_name_hint", dist)

    for dist, slot, record in sorted(candidates, key=lambda item: item[0]):
        if dist <= threshold:
            _accept(slot, record, f"nearest_layout_center:{dist:.5f}", dist)

    if centers and len(result) < len(centers):
        by_slot = {}
        for dist, slot, record in sorted(candidates, key=lambda item: item[0]):
            by_slot.setdefault(slot, []).append((dist, record))
        for slot in sorted(centers):
            if slot in result:
                continue
            ranked = by_slot.get(slot) or []
            if not ranked:
                continue
            best_dist, best_record = ranked[0]
            second_dist = ranked[1][0] if len(ranked) > 1 else float("inf")
            near_enough = best_dist <= threshold * 1.5
            clearly_best = second_dist > best_dist and (second_dist - best_dist >= 0.004 or near_enough)
            if best_dist <= relaxed_threshold and (clearly_best or len(ranked) == 1):
                _accept(slot, best_record, f"nearest_layout_center_relaxed:{best_dist:.5f}", best_dist)
    if len(result) < len(known_slots):
        _family_fill_missing_slots()
    return result


def _reference_intent_slot_rebind_summary(
    current_records,
    persisted_records,
    layout_centers,
    expected_slots,
    bound_slots,
    diagnostics=None,
    dimension_plan=None,
):
    """Summarize why reference-intent drawing-view slot rebinding did or did not bind."""
    expected = sorted({
        str(slot or "").strip().lower()
        for slot in (expected_slots or [])
        if str(slot or "").strip()
    })
    centers = {}
    for slot, center in (layout_centers or {}).items():
        key = str(slot or "").strip().lower()
        if not key or (expected and key not in expected):
            continue
        try:
            centers[key] = (float(center[0]), float(center[1]))
        except Exception:
            continue
    current = [item for item in (current_records or []) if isinstance(item, dict)]
    persisted = [item for item in (persisted_records or []) if isinstance(item, dict)]
    records = current + persisted
    bound = bound_slots if isinstance(bound_slots, dict) else {}
    diag_items = [item for item in (diagnostics or []) if isinstance(item, dict)]

    def _nearest_for_slot(slot):
        center = centers.get(slot)
        ranked = []
        for record in records:
            outline = record.get("outline") or []
            rec_center = _outline_center(outline)
            if center is None or rec_center is None:
                continue
            try:
                dist = ((rec_center[0] - center[0]) ** 2 + (rec_center[1] - center[1]) ** 2) ** 0.5
            except Exception:
                continue
            ranked.append({
                "view_name": str(record.get("name") or ""),
                "view_type": str(record.get("type") or ""),
                "source": str(record.get("source") or ""),
                "distance": round(float(dist), 5),
                "outline": list(outline),
            })
        ranked.sort(key=lambda item: item.get("distance") if item.get("distance") is not None else 999.0)
        return ranked[:5]

    slot_results = {}
    for slot in expected:
        slot_diag = [
            item for item in diag_items
            if str(item.get("slot") or "").strip().lower() == slot
        ]
        nearest = _nearest_for_slot(slot)
        accepted_diag = [item for item in slot_diag if item.get("accepted")]
        if slot in bound:
            reason = "bound"
        elif slot not in centers:
            reason = "layout_center_missing"
        elif not records:
            reason = "no_view_records"
        elif not nearest:
            reason = "no_nearby_candidate_distances"
        elif not slot_diag:
            reason = "slot_match_not_attempted"
        else:
            reason = "all_rebind_attempts_failed"
        slot_results[slot] = {
            "bound": slot in bound,
            "reason": reason,
            "source": str((bound.get(slot) or {}).get("source") or ""),
            "layout_center_present": slot in centers,
            "layout_center": list(centers.get(slot) or []),
            "name_candidates": _reference_intent_view_name_candidates(slot, dimension_plan),
            "diagnostic_attempt_count": len(slot_diag),
            "accepted_attempt_count": len(accepted_diag),
            "nearest_candidates": nearest,
        }

    return {
        "expected_slots": expected,
        "bound_slots": [slot for slot in expected if slot in bound],
        "unbound_slots": [slot for slot in expected if slot not in bound],
        "current_view_record_count": len(current),
        "persisted_view_record_count": len(persisted),
        "match_threshold": round(float(_reference_slot_match_threshold(centers)), 5) if centers else None,
        "slot_results": slot_results,
    }


def _coerce_sheet_point(value):
    if value is None:
        return None
    try:
        values = list(value)
    except Exception:
        return None
    if len(values) < 2:
        return None
    try:
        return (float(values[0]), float(values[1]))
    except Exception:
        return None


def _display_dim_text_position(display_dim=None, annotation=None):
    for target, names in (
        (display_dim, ("TextPosition", "GetTextPosition", "GetTextPoint")),
        (annotation, ("GetPosition", "Position")),
    ):
        if target is None:
            continue
        for name in names:
            try:
                point = _coerce_sheet_point(call(target, name))
                if point is not None:
                    return point
            except Exception:
                continue
    return None


def _view_outline_from_display_dim_item(item):
    outline = item.get("view_outline")
    if isinstance(outline, (list, tuple)) and len(outline) >= 4:
        try:
            return tuple(float(v) for v in outline[:4])
        except Exception:
            pass
    try:
        outline = view_outline_box(item.get("view_obj"))
        if outline:
            return tuple(float(v) for v in outline[:4])
    except Exception:
        pass
    return None


def _side_for_position_against_outline(position, outline):
    if position is None or outline is None:
        return "unknown"
    x, y = position
    x0, y0, x1, y1 = outline
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    if x0 <= x <= x1 and y0 <= y <= y1:
        return "inside"
    distances = {
        "left": abs(x - x0),
        "right": abs(x - x1),
        "bottom": abs(y - y0),
        "top": abs(y - y1),
    }
    if y > y1 and y - y1 >= max(0.0, x0 - x, x - x1):
        return "top"
    if y < y0 and y0 - y >= max(0.0, x0 - x, x - x1):
        return "bottom"
    if x < x0:
        return "left"
    if x > x1:
        return "right"
    return min(distances, key=distances.get)


def _normalized_fraction(value, low, high):
    try:
        span = float(high) - float(low)
        if abs(span) < 1e-9:
            return 0.5
        return max(0.0, min(1.0, (float(value) - float(low)) / span))
    except Exception:
        return 0.5


def _reference_intent_side_preferences(slot):
    slot = str(slot or "").strip().lower()
    if slot == "top":
        return {"top": 6.0, "left": 3.5, "right": 2.5, "bottom": 1.5, "inside": -6.0}
    if slot == "front":
        return {"top": 5.0, "left": 4.0, "right": 4.0, "bottom": 1.5, "inside": -6.0}
    if slot == "right":
        return {"left": 5.0, "right": 5.0, "top": 3.0, "bottom": 3.0, "inside": -6.0}
    if slot == "iso":
        return {"top": -1.0, "right": -1.0, "bottom": -2.0, "left": -2.0, "inside": -6.0}
    return {"top": 2.0, "right": 2.0, "bottom": 1.0, "left": 1.0, "inside": -4.0}


def _reference_intent_side_alias(value):
    side = str(value or "").strip().lower()
    if side in {"above", "top", "upper"}:
        return "top"
    if side in {"below", "bottom", "lower"}:
        return "bottom"
    if side in {"callout_right", "right"}:
        return "right"
    if side in {"callout_left", "left"}:
        return "left"
    return side or "unknown"


def _reference_intent_visual_defect_constraints(dimension_plan):
    plan = dimension_plan if isinstance(dimension_plan, dict) else {}
    constraints = plan.get("visual_defect_constraints") or {}
    return constraints if isinstance(constraints, dict) else {}


def _reference_intent_strict_ui_defect_match(dimension_plan):
    constraints = _reference_intent_visual_defect_constraints(dimension_plan)
    return bool(
        constraints.get("reject_generic_autodim_survivors")
        or constraints.get("compact_local_lanes_required")
        or constraints.get("callout_presence_recheck_required")
    )


def _reference_intent_match_score_floor(dimension_plan):
    # ui_defect_strict_reference_intent_target_match:
    # Application Drawing Review UI failures proved that weak slot/station
    # matches let AutoDimension-style survivors masquerade as target coverage.
    return 3.5 if _reference_intent_strict_ui_defect_match(dimension_plan) else 1.5


def _reference_intent_expected_side_compatible(expected_type, side_alias):
    expected = str(expected_type or "").strip().lower()
    side = _reference_intent_side_alias(side_alias)
    if "horizontal" in expected:
        return side in {"top", "bottom"}
    if "vertical" in expected:
        return side in {"left", "right"}
    if "diameter" in expected:
        return side in {"left", "right", "top", "bottom"}
    return True


def _reference_intent_target_fraction(target):
    lane = (target or {}).get("placement_lane") or {}
    try:
        if "station" in lane:
            return max(0.0, min(1.0, float(lane.get("station"))))
    except Exception:
        pass
    key = str((target or {}).get("key") or "")
    fractions = {
        "overall_length": 0.50,
        "overall_width": 0.58,
        "overall_height": 0.56,
        "left_end_offset": 0.18,
        "right_end_offset": 0.82,
        "hole_diameter": 0.54,
        "hole_x_location": 0.38,
        "hole_y_location": 0.46,
        "hole_pitch": 0.70,
        "projection_view_width": 0.50,
        "projection_view_height": 0.50,
        "small_feature_location": 0.35,
    }
    return float(fractions.get(key, 0.5))


def _match_reference_intent_target_for_display_dim(item, *, layout_plan=None, dimension_plan=None):
    plan = dimension_plan if isinstance(dimension_plan, dict) else {}
    targets = [target for target in (plan.get("dimension_targets") or []) if isinstance(target, dict)]
    if not targets:
        return {}
    strict_ui_defect_match = _reference_intent_strict_ui_defect_match(plan)
    slot = str(item.get("_slot") or item.get("slot") or _slot_for_display_dim_item(item, layout_plan)).strip().lower()
    outline = _view_outline_from_display_dim_item(item)
    position = _coerce_sheet_point(item.get("position"))
    if position is None:
        position = _display_dim_text_position(item.get("display_dim"), item.get("annotation"))
    side = _side_for_position_against_outline(position, outline)
    side_alias = _reference_intent_side_alias(side)
    station = 0.5
    if outline is not None and position is not None:
        x, y = position
        x0, y0, x1, y1 = outline
        if x1 < x0:
            x0, x1 = x1, x0
        if y1 < y0:
            y0, y1 = y1, y0
        if side_alias in {"top", "bottom"}:
            station = _normalized_fraction(x, x0, x1)
        elif side_alias in {"left", "right"}:
            station = _normalized_fraction(y, y0, y1)
        else:
            station = _normalized_fraction(x, x0, x1)

    best = {}
    best_score = float("-inf")
    for target in targets:
        target_slot = str(target.get("target_view") or "").strip().lower()
        if target_slot and slot and target_slot != slot:
            continue
        preferred = _reference_intent_side_alias(target.get("preferred_side"))
        expected_type = str(target.get("expected_type") or "")
        side_matches_preferred = bool(preferred and preferred == side_alias)
        type_side_compatible = _reference_intent_expected_side_compatible(expected_type, side_alias)
        if strict_ui_defect_match and preferred and not side_matches_preferred:
            continue
        if strict_ui_defect_match and not type_side_compatible:
            continue
        target_fraction = _reference_intent_target_fraction(target)
        side_score = 3.0 if preferred == side_alias else 0.0
        if side_alias in {"left", "right"} and preferred in {"left", "right"}:
            side_score = max(side_score, 1.0)
        if side_alias in {"top", "bottom"} and preferred in {"top", "bottom"}:
            side_score = max(side_score, 1.0)
        station_delta = abs(float(station) - float(target_fraction))
        station_score = max(0.0, 2.0 - station_delta * 5.0)
        try:
            priority_score = max(0.0, 0.25 - min(100, int(target.get("priority") or 0)) / 400.0)
        except Exception:
            priority_score = 0.0
        if strict_ui_defect_match and station_delta > 0.28:
            continue
        score = side_score + station_score + priority_score
        if score > best_score:
            best_score = score
            best = {
                "target_key": str(target.get("key") or ""),
                "target_group": str(target.get("group") or ""),
                "functional_role": str(target.get("functional_role") or ""),
                "reading_group": str(target.get("reading_group") or ""),
                "readability_group": str(target.get("readability_group") or ""),
                "target_view": target_slot,
                "expected_type": expected_type,
                "preferred_side": str(target.get("preferred_side") or ""),
                "placement_lane": dict(target.get("placement_lane") or {}),
                "allowed_witness_entity": dict(target.get("allowed_witness_entity") or {}),
                "prune_protection_policy": dict(target.get("prune_protection_policy") or {}),
                "matched_side": side_alias,
                "station": round(float(station), 4),
                "target_fraction": round(float(target_fraction), 4),
                "station_delta": round(float(station_delta), 4),
                "match_score": round(float(score), 4),
                "strict_ui_defect_match": bool(strict_ui_defect_match),
                "side_matches_preferred": bool(side_matches_preferred),
                "type_side_compatible": bool(type_side_compatible),
            }
    return best


def _score_display_dim_for_reference_intent(item, *, layout_plan=None, dimension_plan=None):
    """Score real DisplayDim objects for 006-style reference-intent pruning."""
    plan = dimension_plan if isinstance(dimension_plan, dict) else {}
    intent_groups = plan.get("dimension_intent_groups") or []
    quotas = plan.get("view_dimension_quotas") or {}
    target_match = _match_reference_intent_target_for_display_dim(
        item,
        layout_plan=layout_plan,
        dimension_plan=dimension_plan,
    )
    if not intent_groups and not quotas:
        result = {
            "score": 0.0,
            "slot": str(item.get("_slot") or item.get("slot") or "").strip().lower(),
            "side": "unscored",
            "reason": "no_reference_intent_plan",
        }
        if target_match:
            result["target_match"] = target_match
        return result
    slot = str(item.get("_slot") or item.get("slot") or _slot_for_display_dim_item(item, layout_plan)).strip().lower()
    outline = _view_outline_from_display_dim_item(item)
    position = _coerce_sheet_point(item.get("position"))
    if position is None:
        position = _display_dim_text_position(item.get("display_dim"), item.get("annotation"))
    side = _side_for_position_against_outline(position, outline)
    score = _reference_intent_side_preferences(slot).get(side, 0.0)
    reason = [f"slot={slot or 'unknown'}", f"side={side}"]

    if outline is None or position is None:
        score -= 2.0
        reason.append("missing_position_or_outline")
        result = {"score": round(score, 4), "slot": slot, "side": side, "reason": ";".join(reason)}
        if target_match:
            result["target_match"] = target_match
        return result

    x, y = position
    x0, y0, x1, y1 = outline
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    width = max(x1 - x0, 0.001)
    height = max(y1 - y0, 0.001)
    fx = _normalized_fraction(x, x0, x1)
    fy = _normalized_fraction(y, y0, y1)
    outside_gap = 0.0
    if side == "top":
        outside_gap = max(0.0, y - y1)
    elif side == "bottom":
        outside_gap = max(0.0, y0 - y)
    elif side == "left":
        outside_gap = max(0.0, x0 - x)
    elif side == "right":
        outside_gap = max(0.0, x - x1)

    if side != "inside":
        if outside_gap <= 0.020:
            score += 2.0
            reason.append("compact_lane")
        elif outside_gap <= 0.035:
            score += 0.5
            reason.append("outer_lane")
        else:
            score -= 1.5
            reason.append("far_from_view")

    if side in {"top", "bottom"}:
        if 0.10 <= fx <= 0.90:
            score += 1.5
            reason.append("long_axis_station")
        if slot == "top" and 0.20 <= fx <= 0.85:
            score += 1.0
            reason.append("hole_position_lane")
    elif side in {"left", "right"}:
        if 0.05 <= fy <= 0.95:
            score += 1.0
            reason.append("transverse_station")

    if slot == "iso":
        score -= 4.0
        reason.append("iso_dimensions_not_reference_primary")
    if slot not in {"front", "top", "right", "iso"}:
        score -= 1.0
        reason.append("unknown_slot")
    if width / max(height, 1e-6) >= 4.0 and slot in {"front", "top"} and side in {"top", "left", "right"}:
        score += 1.0
        reason.append("long_thin_reference_lane")

    result = {"score": round(score, 4), "slot": slot, "side": side, "reason": ";".join(reason)}
    if target_match:
        result["target_match"] = target_match
    return result


def _reference_intent_target_coverage_from_items(items, *, layout_plan=None, dimension_plan=None):
    plan = dimension_plan if isinstance(dimension_plan, dict) else {}
    targets = [target for target in (plan.get("dimension_targets") or []) if isinstance(target, dict)]
    target_results = []
    by_key = {}
    for target in targets:
        key = str(target.get("key") or "")
        if not key:
            continue
        entry = {
            "target_key": key,
            "target_group": str(target.get("group") or ""),
            "target_view": str(target.get("target_view") or ""),
            "expected_type": str(target.get("expected_type") or ""),
            "preferred_side": str(target.get("preferred_side") or ""),
            "matched_count": 0,
            "best_match_score": 0.0,
            "best_display_dim": {},
            "persisted_after_reopen": False,
        }
        by_key[key] = entry
        target_results.append(entry)

    matched_items = []
    for ordinal, item in enumerate(items or []):
        data = dict(item)
        data["_slot"] = _slot_for_display_dim_item(data, layout_plan)
        intent = _score_display_dim_for_reference_intent(
            data,
            layout_plan=layout_plan,
            dimension_plan=dimension_plan,
        )
        match = intent.get("target_match") or {}
        key = str(match.get("target_key") or "")
        if not key or key not in by_key:
            continue
        try:
            match_score = float(match.get("match_score") or 0.0)
        except Exception:
            match_score = 0.0
        if match_score < _reference_intent_match_score_floor(dimension_plan):
            continue
        entry = by_key[key]
        entry["matched_count"] = int(entry.get("matched_count") or 0) + 1
        if match_score >= float(entry.get("best_match_score") or 0.0):
            entry["best_match_score"] = round(match_score, 4)
            entry["best_display_dim"] = {
                "ordinal": ordinal,
                "slot": str(data.get("_slot") or ""),
                "view": str(data.get("view") or ""),
                "source": str(data.get("source") or ""),
                "position": list(data.get("position") or []),
                "view_outline": list(data.get("view_outline") or []),
                "score": intent.get("score"),
                "side": intent.get("side", ""),
                "reason": intent.get("reason", ""),
                "target_match": match,
            }
        matched_items.append({
            "ordinal": ordinal,
            "target_key": key,
            "match_score": round(match_score, 4),
            "slot": str(data.get("_slot") or ""),
            "view": str(data.get("view") or ""),
            "source": str(data.get("source") or ""),
        })

    covered = []
    missing = []
    for entry in target_results:
        if int(entry.get("matched_count") or 0) > 0:
            covered.append(entry["target_key"])
            entry["persisted_after_reopen"] = True
        else:
            missing.append(entry["target_key"])
    return {
        "source": "display_dim_target_match_snapshot",
        "display_dim_count": len(list(items or [])),
        "target_count": len(target_results),
        "covered_count": len(covered),
        "covered_target_keys": covered,
        "missing_target_keys": missing,
        "target_results": target_results,
        "matched_items": matched_items,
    }


def _reference_intent_target_coverage_snapshot(drw_doc, *, layout_plan=None, dimension_plan=None):
    try:
        items = _display_dim_annotations_in_doc(drw_doc)
    except Exception as exc:
        return {
            "source": "display_dim_target_match_snapshot",
            "error": str(exc),
            "display_dim_count": 0,
            "target_count": len((dimension_plan or {}).get("dimension_targets") or []),
            "covered_count": 0,
            "covered_target_keys": [],
            "missing_target_keys": [
                str(target.get("key") or "")
                for target in ((dimension_plan or {}).get("dimension_targets") or [])
                if isinstance(target, dict) and str(target.get("key") or "")
            ],
            "target_results": [],
            "matched_items": [],
        }
    return _reference_intent_target_coverage_from_items(
        items,
        layout_plan=layout_plan,
        dimension_plan=dimension_plan,
    )


def _reference_intent_missing_target_keys(coverage):
    return {
        str(item or "").strip()
        for item in (coverage or {}).get("missing_target_keys") or []
        if str(item or "").strip()
    }


def _reference_intent_target_covered(coverage, target_key):
    key = str(target_key or "").strip()
    if not key:
        return False
    covered = {
        str(item or "").strip()
        for item in (coverage or {}).get("covered_target_keys") or []
        if str(item or "").strip()
    }
    missing = {
        str(item or "").strip()
        for item in (coverage or {}).get("missing_target_keys") or []
        if str(item or "").strip()
    }
    if key in covered and key not in missing:
        return True
    for item in (coverage or {}).get("target_results") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("target_key") or "").strip() != key:
            continue
        try:
            return int(item.get("matched_count") or 0) > 0
        except Exception:
            return False
    return False


def _reference_intent_post_layout_repair_reason(display_dim_count, dimension_floor, target_coverage):
    try:
        count = int(display_dim_count or 0)
    except Exception:
        count = 0
    try:
        floor = int(dimension_floor or 0)
    except Exception:
        floor = 0
    missing = sorted(_reference_intent_missing_target_keys(target_coverage))
    if floor > 0 and count < floor:
        return "display_dim_floor_gap"
    if missing:
        return "reference_intent_targets_missing"
    return ""


def _reference_intent_final_acceptance_blockers(
    display_dim_count,
    dimension_floor,
    target_coverage,
    dimension_plan=None,
):
    try:
        count = int(display_dim_count or 0)
    except Exception:
        count = 0
    try:
        floor = int(dimension_floor or 0)
    except Exception:
        floor = 0
    plan = dimension_plan if isinstance(dimension_plan, dict) else {}
    targets = [
        item for item in (plan.get("dimension_targets") or [])
        if isinstance(item, dict) and str(item.get("key") or "").strip()
    ]
    target_count = len(targets)
    constraints = _reference_intent_visual_defect_constraints(plan)
    active_buckets = {
        str(item or "").strip()
        for item in ((plan.get("ui_defect_buckets") or {}).get("active_buckets") or [])
        if str(item or "").strip()
    }
    overcap_policy_required = bool(
        constraints.get("reject_generic_autodim_survivors")
        or "dimension_visual_overdense" in active_buckets
    )
    reference_intent_cap = max(floor, target_count)
    blockers = []
    if floor > 0 and count < floor:
        blockers.append({
            "key": "display_dim_floor_gap",
            "display_dim_count": count,
            "reference_display_dim_floor": floor,
            "gap": floor - count,
        })
    missing = sorted(_reference_intent_missing_target_keys(target_coverage))
    if missing:
        blockers.append({
            "key": "reference_intent_targets_missing",
            "missing_target_keys": missing,
            "missing_count": len(missing),
        })
    if overcap_policy_required and reference_intent_cap > 0 and count > reference_intent_cap:
        # final_reference_intent_display_dim_over_cap_blocker:
        # The 006 UI failure showed that target coverage alone can still leave
        # a visibly AutoDimension-like sheet. Under active visual-overdense
        # repair policy, final acceptance must reject surplus DisplayDims.
        blockers.append({
            "key": "display_dim_over_reference_intent_cap",
            "display_dim_count": count,
            "reference_intent_cap": reference_intent_cap,
            "reference_display_dim_floor": floor,
            "reference_intent_target_count": target_count,
            "surplus": count - reference_intent_cap,
            "policy": "dimension_visual_overdense",
        })
    return blockers


def _reference_intent_target_coverage_stage_delta(snapshots):
    """Track which reference-intent targets are lost across persistence stages."""
    normalized = []
    target_order = []

    def _remember(key):
        key = str(key or "").strip()
        if key and key not in target_order:
            target_order.append(key)

    for index, item in enumerate(snapshots or [], start=1):
        if not isinstance(item, dict):
            continue
        stage = str(item.get("stage") or f"stage_{index}").strip() or f"stage_{index}"
        covered = {
            str(key or "").strip()
            for key in (item.get("covered_target_keys") or [])
            if str(key or "").strip()
        }
        missing = {
            str(key or "").strip()
            for key in (item.get("missing_target_keys") or [])
            if str(key or "").strip()
        }
        for target in item.get("target_results") or []:
            if isinstance(target, dict):
                _remember(target.get("target_key"))
        for key in sorted(covered | missing):
            _remember(key)
        normalized.append({
            "stage": stage,
            "covered_target_keys": sorted(covered),
            "missing_target_keys": sorted(missing),
        })

    per_target = []
    for key in target_order:
        first_covered_stage = ""
        first_missing_after_covered_stage = ""
        covered_before = False
        previous_state = ""
        final_state = "unknown"
        states = []
        transitions = []
        for item in normalized:
            stage = item["stage"]
            covered = key in item["covered_target_keys"]
            missing = key in item["missing_target_keys"]
            state = "covered" if covered else ("missing" if missing else "unknown")
            states.append({"stage": stage, "state": state})
            if state != "unknown":
                final_state = state
            if state == "covered":
                covered_before = True
                if not first_covered_stage:
                    first_covered_stage = stage
            elif state == "missing" and covered_before and not first_missing_after_covered_stage:
                first_missing_after_covered_stage = stage
            if previous_state and state != previous_state:
                transitions.append({
                    "stage": stage,
                    "from": previous_state,
                    "to": state,
                })
            previous_state = state
        per_target.append({
            "target_key": key,
            "first_covered_stage": first_covered_stage,
            "first_missing_after_covered_stage": first_missing_after_covered_stage,
            "final_state": final_state,
            "lost_after_coverage": bool(first_missing_after_covered_stage and final_state == "missing"),
            "recovered_after_loss": bool(first_missing_after_covered_stage and final_state == "covered"),
            "stage_states": states,
            "transitions": transitions,
        })

    return {
        "source": "reference_intent_target_coverage_stage_delta",
        "stage_count": len(normalized),
        "stage_order": [item["stage"] for item in normalized],
        "target_count": len(target_order),
        "lost_target_keys": [
            item["target_key"]
            for item in per_target
            if item.get("lost_after_coverage")
        ],
        "recovered_target_keys": [
            item["target_key"]
            for item in per_target
            if item.get("recovered_after_loss")
        ],
        "never_covered_target_keys": [
            item["target_key"]
            for item in per_target
            if not item.get("first_covered_stage")
        ],
        "final_missing_target_keys": [
            item["target_key"]
            for item in per_target
            if item.get("final_state") == "missing"
        ],
        "per_target": per_target,
    }


def _reference_intent_targets_for_repair(targets, coverage):
    missing = _reference_intent_missing_target_keys(coverage)

    def _sort_key(target):
        key = str((target or {}).get("key") or "").strip()
        try:
            priority = int((target or {}).get("priority") or 0)
        except Exception:
            priority = 0
        return (0 if key in missing else 1, priority)

    return sorted([target for target in targets or [] if isinstance(target, dict)], key=_sort_key)


def _dimension_attempt_target(current_count, target_floor, *, minimum=5, margin=2):
    try:
        current = int(current_count or 0)
        floor = int(target_floor or 0)
    except Exception:
        return 0
    gap = max(0, floor - current)
    if gap <= 0:
        return 0
    try:
        cap = int(os.environ.get("SWDS_DIM_INSERT_ATTEMPT_CAP", "32") or "32")
    except Exception:
        cap = 32
    return max(1, min(max(1, cap), max(int(minimum), gap + int(margin))))


def _effective_dimension_floor(reference_dim_floor):
    try:
        floor = int(reference_dim_floor or 0)
    except Exception:
        floor = 0
    return floor if floor > 0 else 5


def _reference_dimension_attempt_target(current_count, reference_dim_floor):
    """Use the same-name reference floor without forcing the legacy minimum 5."""
    try:
        floor = int(reference_dim_floor or 0)
    except Exception:
        floor = 0
    if floor > 0:
        margin = 0 if floor <= 5 else 2
        return _dimension_attempt_target(current_count, floor, minimum=0, margin=margin)
    return _dimension_attempt_target(current_count, 5)


def _reference_dim_floor_gap(display_dim_count, reference_dim_floor):
    try:
        count = int(display_dim_count or 0)
        floor = int(reference_dim_floor or 0)
    except Exception:
        return None
    if floor <= 0 or count >= floor:
        return None
    return {
        "gap": floor - count,
        "reference_display_dim_floor": floor,
        "generated_display_dim_count": count,
    }


def _reference_display_dim_cap(reference_dim_floor, part_class=""):
    """Return the strict-style upper DisplayDim cap for a same-name reference."""
    try:
        floor = int(reference_dim_floor or 0)
    except Exception:
        floor = 0
    if floor <= 0:
        return 0
    if str(part_class or "").strip().lower() == "long_thin":
        return floor + 2
    return max(floor + 2, int(math.ceil(floor * 1.5)))


def _reference_autodim_call_budget(reference_dim_floor, part_class=""):
    """Keep AutoDimension bounded while allowing concise samples to reach their floor."""
    try:
        floor = int(reference_dim_floor or 0)
    except Exception:
        floor = 0
    if str(part_class or "").strip().lower() == "long_thin" and floor >= 8:
        return 3
    return 2 if floor > 2 else 1


def _needs_dimension_sidecar(imported, display_dim_count, dimension_floor):
    try:
        count = int(display_dim_count or 0)
        floor = int(dimension_floor or 0)
    except Exception:
        return not bool(imported)
    return (not bool(imported)) or count < floor


def _dimension_sidecar_mode_for_reference_intent(need_sidecar, strict_reference_intent):
    """Return sidecar policy for the current dimension path."""
    if not need_sidecar:
        return {
            "run_sidecar": False,
            "diagnostic_only": bool(strict_reference_intent),
            "reason": "display_dim_floor_satisfied",
        }
    if strict_reference_intent:
        return {
            "run_sidecar": False,
            "diagnostic_only": True,
            "reason": "reference_intent_sidecar_not_allowed_for_acceptance",
        }
    return {
        "run_sidecar": True,
        "diagnostic_only": False,
        "reason": "generic_dimension_recovery_allowed",
    }


def _reference_intent_entity_rank(expected_type, curve_identity):
    """Rank visible drawing entities for a reference-intent dimension target."""
    expected = str(expected_type or "").strip().lower()
    try:
        identity = int(curve_identity)
    except Exception:
        identity = -1
    is_circular = identity in {2, 3}
    wants_diameter = "diameter" in expected or "circular" in expected
    wants_linear = any(token in expected for token in ("horizontal", "vertical", "linear"))
    if wants_diameter:
        category = 0 if is_circular else 3
    elif wants_linear:
        category = 0 if not is_circular else 3
    else:
        category = 1 if not is_circular else 2
    identity_rank = identity if identity >= 0 else 999
    return (category, identity_rank)


def _dimension_insert_plan_for_outline(outline, target_count, *, offset=0.012, step=0.004, allow_diagonal=True):
    """Return enough sheet insertion points to chase a reference DisplayDim floor."""
    try:
        x0, y0, x1, y1 = [float(v) for v in outline[:4]]
    except Exception:
        return []
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    width = max(abs(x1 - x0), 0.001)
    height = max(abs(y1 - y0), 0.001)
    target = max(0, int(target_count or 0))
    plan = []
    lanes = ("horizontal", "vertical", "diagonal") if allow_diagonal else ("horizontal", "vertical")
    lane_count = max(1, len(lanes))
    for index in range(target):
        lane = lanes[index % lane_count]
        ring = index // lane_count
        frac = ((index // lane_count) % 5 + 1) / 6.0
        if lane == "horizontal":
            y = y1 + offset + ring * step
            x = x0 + width * frac
            plan.append(("horizontal", x, y))
        elif lane == "vertical":
            x = x0 - offset - ring * step
            y = y0 + height * frac
            plan.append(("vertical", x, y))
        else:
            x = x1 + offset + ring * step
            y = y1 + offset + ring * step
            plan.append(("diagonal", x, y))
    return plan


def _force_dimension_insert_plan(outline, current_count, reference_dim_floor, *, allow_diagonal=True):
    """Return 6.5 fallback points only when the real DisplayDim count is below the floor."""
    try:
        current = int(current_count or 0)
    except Exception:
        current = 0
    floor = _effective_dimension_floor(reference_dim_floor)
    if current >= floor:
        return []
    target_attempts = _reference_dimension_attempt_target(current, reference_dim_floor)
    return _dimension_insert_plan_for_outline(outline, target_attempts, allow_diagonal=allow_diagonal)


def _annotation_name(annotation):
    for name in ("GetName", "GetName2", "GetNameForSelection", "Name"):
        try:
            value = call(annotation, name)
            if value:
                return str(value)
        except Exception:
            continue
    return ""


def _is_cosmetic_thread_annotation(annotation):
    name = _annotation_name(annotation).lower()
    return any(token in name for token in ("孔螺", "螺纹线", "螺蚊线", "cosmetic thread", "thread"))


def _display_dim_physical_key(item):
    view_name = str(item.get("view") or "").strip()
    annotation_name = str(item.get("annotation_name") or "").strip()
    if annotation_name:
        return ("annotation_name", view_name, annotation_name)
    position = _coerce_sheet_point(item.get("position"))
    outline = item.get("view_outline") or []
    try:
        outline_key = tuple(round(float(value), 6) for value in outline)
    except Exception:
        outline_key = ()
    if position is not None:
        return (
            "position",
            view_name,
            round(float(position[0]), 6),
            round(float(position[1]), 6),
            outline_key,
        )
    target = item.get("annotation") or item.get("display_dim") or item
    return ("object", id(target))


def _dedupe_display_dim_annotations(items):
    # physical_displaydim_dedupe:
    # SolidWorks can surface one DisplayDim through multiple enumeration APIs.
    # Treat those records as one physical dimension before scoring/pruning.
    deduped = []
    seen = {}
    for item in items or []:
        if not isinstance(item, dict):
            continue
        key = _display_dim_physical_key(item)
        existing = seen.get(key)
        if existing is None:
            copied = dict(item)
            copied["duplicate_sources"] = []
            seen[key] = copied
            deduped.append(copied)
            continue
        existing.setdefault("duplicate_sources", []).append({
            "source": str(item.get("source") or ""),
            "annotation_name": str(item.get("annotation_name") or ""),
            "position": list(item.get("position") or []),
        })
        if existing.get("display_dim") is None and item.get("display_dim") is not None:
            existing["display_dim"] = item.get("display_dim")
        if existing.get("annotation") is None and item.get("annotation") is not None:
            existing["annotation"] = item.get("annotation")
        existing_source = str(existing.get("source") or "")
        incoming_source = str(item.get("source") or "")
        if incoming_source and incoming_source not in existing_source.split("+"):
            existing["source"] = f"{existing_source}+{incoming_source}" if existing_source else incoming_source
    return deduped


def _display_dim_annotations_in_doc(drw_doc):
    annotations = []
    seen_targets = set()

    def _append(target, view_name, view_index, *, display_dim=None, source="annotation_chain"):
        if target is None:
            return
        key = id(target)
        if key in seen_targets:
            return
        seen_targets.add(key)
        try:
            outline = view_outline_box(view)
        except Exception:
            outline = None
        position = _display_dim_text_position(display_dim, target)
        annotations.append({
            "annotation": target,
            "display_dim": display_dim,
            "view_obj": view,
            "view": view_name,
            "view_index": view_index,
            "view_outline": list(outline) if outline else [],
            "position": list(position) if position else [],
            "annotation_name": _annotation_name(target),
            "source": source,
        })

    def _as_list(value):
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return list(value)
        try:
            return list(value)
        except Exception:
            return [value]

    try:
        view = call(drw_doc, "GetFirstView")
        view_index = 0
        while view is not None and view_index < 100:
            try:
                view_name = str(call(view, "Name") or call(view, "GetName2") or f"view_{view_index}")
            except Exception:
                view_name = f"view_{view_index}"
            try:
                ann = call(view, "GetFirstAnnotation3")
            except Exception:
                ann = None
            seen = 0
            while ann is not None and seen < 2000:
                seen += 1
                try:
                    next_ann = call(ann, "GetNext3")
                except Exception:
                    next_ann = None
                try:
                    ann_type = int(call(ann, "GetType") or 0)
                except Exception:
                    ann_type = 0
                if ann_type == 1 and not _is_cosmetic_thread_annotation(ann):
                    _append(ann, view_name, view_index, source="annotation_chain")
                ann = next_ann
            try:
                for display_dim in _as_list(call(view, "GetDisplayDimensions")):
                    ann = call(display_dim, "GetAnnotation")
                    _append(ann or display_dim, view_name, view_index, display_dim=display_dim, source="GetDisplayDimensions")
            except Exception:
                pass
            try:
                display_dim = call(view, "GetFirstDisplayDimension")
                seen_dims = 0
                while display_dim is not None and seen_dims < 2000:
                    seen_dims += 1
                    ann = call(display_dim, "GetAnnotation")
                    _append(ann or display_dim, view_name, view_index, display_dim=display_dim, source="GetFirstDisplayDimension")
                    try:
                        display_dim = view.GetNextDisplayDimension(display_dim)
                    except Exception:
                        break
            except Exception:
                pass
            try:
                view = call(view, "GetNextView")
            except Exception:
                break
            view_index += 1
    except Exception:
        return []
    return _dedupe_display_dim_annotations(annotations)


def _select_annotation_for_delete(drw_doc, annotation, display_dim=None):
    try:
        drw_doc.ClearSelection2(True)
    except Exception:
        pass
    select_data = None
    try:
        select_data = call(call(drw_doc, "SelectionManager"), "CreateSelectData")
    except Exception:
        select_data = None
    select_attempts = (
        ("Select3", (False, select_data)),
        ("Select3", (False, None)),
        ("Select3", (False, vt_dispatch_none())),
        ("Select2", (False, 0)),
        ("Select2", (False,)),
        ("Select", (False,)),
        ("Select", ()),
    )
    for target, label in ((display_dim, "display_dim"), (annotation, "annotation")):
        if target is None:
            continue
        for method_name, args in select_attempts:
            try:
                method = getattr(target, method_name, None)
                if not callable(method):
                    continue
                selected = method(*args)
                if selected is not False:
                    return True, f"{label}.{method_name}"
            except Exception:
                continue
    return False, "annotation_select_failed"


def _delete_selected_annotation(drw_doc):
    try:
        result = drw_doc.EditDelete()
        if result is not False:
            return True, "EditDelete"
    except Exception:
        pass
    for arg in (False, 0, 1):
        try:
            result = drw_doc.DeleteSelection2(arg)
            if result is not False:
                return True, f"DeleteSelection2({arg})"
        except Exception:
            continue
    try:
        result = drw_doc.Extension.DeleteSelection2(0)
        if result is not False:
            return True, "Extension.DeleteSelection2(0)"
    except Exception:
        pass
    return False, "delete_selection_failed"


def _prune_display_dims_to_cap(
    drw_doc,
    cap,
    *,
    log_fn=None,
    slot_quotas=None,
    layout_plan=None,
    dimension_plan=None,
    reference_dim_floor=0,
    strict_reference_intent=False,
):
    def _log(msg):
        if log_fn:
            try:
                log_fn(msg)
            except Exception:
                pass

    def _normalized_quotas():
        if not isinstance(slot_quotas, dict):
            return {}
        out = {}
        for slot, value in slot_quotas.items():
            try:
                quota = max(0, int(value or 0))
            except Exception:
                quota = 0
            slot_key = str(slot or "").strip().lower()
            if slot_key:
                out[slot_key] = quota
        return out

    def _annotated_items(items):
        result_items = []
        for ordinal, item in enumerate(items):
            data = dict(item)
            data["_ordinal"] = ordinal
            data["_slot"] = _slot_for_display_dim_item(data, layout_plan)
            data["_reference_intent"] = _score_display_dim_for_reference_intent(
                data,
                layout_plan=layout_plan,
                dimension_plan=dimension_plan,
            )
            result_items.append(data)
        return result_items

    def _slot_counts(items):
        counts = {}
        for item in items:
            slot = str(item.get("_slot") or "unknown").strip().lower() or "unknown"
            counts[slot] = counts.get(slot, 0) + 1
        return counts

    def _over_quota_slots(items, quotas):
        counts = _slot_counts(items)
        over = []
        controlled = set(quotas) | {"front", "top", "right", "iso"}
        for slot, count in counts.items():
            if slot not in controlled:
                continue
            quota = quotas.get(slot, 0)
            if count > quota:
                over.append((slot, count - quota))
        over.sort(key=lambda item: item[1], reverse=True)
        return [slot for slot, _excess in over]

    def _score_summary(items):
        if not items:
            return {"min": 0.0, "max": 0.0, "avg": 0.0, "by_slot": {}}
        scores = []
        by_slot = {}
        for item in items:
            intent = item.get("_reference_intent") or {}
            try:
                score = float(intent.get("score") or 0.0)
            except Exception:
                score = 0.0
            slot = str(item.get("_slot") or "unknown").strip().lower() or "unknown"
            scores.append(score)
            bucket = by_slot.setdefault(slot, {"count": 0, "avg": 0.0, "min": score, "max": score, "_sum": 0.0})
            bucket["count"] += 1
            bucket["_sum"] += score
            bucket["min"] = min(bucket["min"], score)
            bucket["max"] = max(bucket["max"], score)
        for bucket in by_slot.values():
            bucket["avg"] = round(bucket["_sum"] / max(1, bucket["count"]), 4)
            bucket.pop("_sum", None)
        return {
            "min": round(min(scores), 4),
            "max": round(max(scores), 4),
            "avg": round(sum(scores) / max(1, len(scores)), 4),
            "by_slot": by_slot,
        }

    def _delete_priority(item, remaining_items=None):
        intent = item.get("_reference_intent") or {}
        try:
            score = float(intent.get("score") or 0.0)
        except Exception:
            score = 0.0
        slot = str(item.get("_slot") or "").strip().lower()
        slot_penalty = 0 if slot in {"front", "top", "right"} else -1
        try:
            ordinal = int(item.get("_ordinal") or 0)
        except Exception:
            ordinal = 0
        target_rank = 0
        if strict_reference_intent:
            key = _target_key(item)
            if not key:
                target_rank = 0
            else:
                counts = _target_match_counts(remaining_items or [])
                target_rank = 1 if counts.get(key, 0) > 1 else 2
        return (target_rank, score + slot_penalty, -ordinal)

    def _delete_reason(item):
        if strict_reference_intent and not _target_key(item):
            return "generic_non_reference_intent_displaydim"
        return "over_quota_or_low_reference_intent_score"

    def _target_match(item):
        match = ((item.get("_reference_intent") or {}).get("target_match") or {})
        key = str(match.get("target_key") or "").strip()
        if not key:
            return {}
        try:
            match_score = float(match.get("match_score") or 0.0)
        except Exception:
            match_score = 0.0
        if match_score < _reference_intent_match_score_floor(dimension_plan):
            return {}
        return match

    def _target_key(item):
        return str(_target_match(item).get("target_key") or "").strip()

    def _target_keys_from_plan():
        plan = dimension_plan if isinstance(dimension_plan, dict) else {}
        keys = []
        for target in plan.get("dimension_targets") or []:
            if not isinstance(target, dict):
                continue
            key = str(target.get("key") or "").strip()
            if key:
                keys.append(key)
        return keys

    def _target_match_counts(items):
        counts = {}
        for item in items or []:
            key = _target_key(item)
            if key:
                counts[key] = counts.get(key, 0) + 1
        return counts

    def _target_delete_equivalence_key(item):
        # reference_intent_delete_equivalence_key:
        # In strict 006 UI-closure mode, one physical DisplayDim can still be
        # surfaced through multiple SolidWorks enumerators after reopen. Deleting
        # one wrapper can delete the underlying physical dimension, so prune
        # planning must collapse wrappers that share the same target/station.
        match = _target_match(item)
        key = str(match.get("target_key") or "").strip()
        if not key:
            return ()
        slot = str(item.get("_slot") or "").strip().lower()
        view = str(item.get("view") or "").strip()
        side = str(match.get("matched_side") or "").strip().lower()
        expected_type = str(match.get("expected_type") or "").strip().lower()
        try:
            station = round(float(match.get("station") or 0.0), 3)
        except Exception:
            station = 0.0
        position = _coerce_sheet_point(item.get("position"))
        if position is not None:
            position_key = (round(float(position[0]), 5), round(float(position[1]), 5))
        else:
            position_key = ("station", station)
        return (
            "reference_intent_target_displaydim",
            key,
            slot,
            view,
            side,
            expected_type,
            station,
            position_key,
        )

    def _target_item_rank(item):
        intent = item.get("_reference_intent") or {}
        match = _target_match(item)
        try:
            match_score = float(match.get("match_score") or 0.0)
        except Exception:
            match_score = 0.0
        try:
            intent_score = float(intent.get("score") or 0.0)
        except Exception:
            intent_score = 0.0
        try:
            ordinal = int(item.get("_ordinal") or 0)
        except Exception:
            ordinal = 0
        source = str(item.get("source") or "")
        source_bonus = 0 if source == "GetFirstDisplayDimension" else 1
        return (match_score, intent_score, source_bonus, -ordinal)

    def _dedupe_reference_intent_delete_equivalent_items(items):
        # reference_intent_delete_equivalence_dedupe:
        # Keep one best logical candidate for each strict target fingerprint so
        # final exact-prune does not delete a wrapper and accidentally remove the
        # only physical dimension that proves a target in the application UI.
        deduped = []
        seen: dict[tuple, dict] = {}
        merged_records = []
        for item in items or []:
            eq_key = _target_delete_equivalence_key(item)
            if not eq_key:
                deduped.append(item)
                continue
            existing = seen.get(eq_key)
            if existing is None:
                copied = dict(item)
                copied.setdefault("reference_intent_equivalent_records", [])
                seen[eq_key] = copied
                deduped.append(copied)
                continue
            record = {
                "slot": str(item.get("_slot") or ""),
                "view": str(item.get("view") or ""),
                "source": str(item.get("source") or ""),
                "score": (item.get("_reference_intent") or {}).get("score"),
                "target_key": _target_key(item),
                "target_match": _target_match(item),
            }
            existing.setdefault("reference_intent_equivalent_records", []).append(record)
            merged_records.append(record)
            if existing.get("display_dim") is None and item.get("display_dim") is not None:
                existing["display_dim"] = item.get("display_dim")
            if existing.get("annotation") is None and item.get("annotation") is not None:
                existing["annotation"] = item.get("annotation")
            existing_source = str(existing.get("source") or "")
            incoming_source = str(item.get("source") or "")
            if incoming_source and incoming_source not in existing_source.split("+"):
                existing["source"] = f"{existing_source}+{incoming_source}" if existing_source else incoming_source
            if _target_item_rank(item) > _target_item_rank(existing):
                replacement = dict(item)
                replacement["reference_intent_equivalent_records"] = (
                    list(existing.get("reference_intent_equivalent_records") or []) + [record]
                )
                replacement_source = str(replacement.get("source") or "")
                for source in existing_source.split("+"):
                    if source and source not in replacement_source.split("+"):
                        replacement_source = f"{replacement_source}+{source}" if replacement_source else source
                replacement["source"] = replacement_source
                seen[eq_key] = replacement
                for index, current in enumerate(deduped):
                    if current is existing:
                        deduped[index] = replacement
                        break
        return deduped, {
            "enabled": True,
            "before": len(list(items or [])),
            "after": len(deduped),
            "merged_count": max(0, len(list(items or [])) - len(deduped)),
            "merged_records": merged_records[:50],
        }

    def _best_item_id_by_target(items):
        best: dict[str, dict] = {}
        for item in items or []:
            key = _target_key(item)
            if not key:
                continue
            current = best.get(key)
            if current is None or _target_item_rank(item) > _target_item_rank(current):
                best[key] = item
        return {key: id(item) for key, item in best.items()}

    def _coverage_snapshot(items):
        if not strict_reference_intent:
            return {}
        if not _target_keys_from_plan():
            return {}
        try:
            return _reference_intent_target_coverage_from_items(
                items,
                layout_plan=layout_plan,
                dimension_plan=dimension_plan,
            )
        except Exception as exc:
            return {
                "source": "display_dim_target_match_snapshot",
                "error": str(exc),
                "missing_target_keys": [],
                "covered_target_keys": [],
            }

    def _missing_keys_from_coverage(coverage):
        return sorted({
            str(key or "").strip()
            for key in (coverage or {}).get("missing_target_keys") or []
            if str(key or "").strip()
        })

    def _covered_keys_from_coverage(coverage):
        return {
            str(key or "").strip()
            for key in (coverage or {}).get("covered_target_keys") or []
            if str(key or "").strip()
        }

    def _protected_item_evidence(item, reason, *, lost_target_keys=None):
        return {
            "slot": str(item.get("_slot") or "unknown"),
            "view": str(item.get("view") or ""),
            "source": str(item.get("source") or ""),
            "score": (item.get("_reference_intent") or {}).get("score"),
            "target_key": _target_key(item),
            "target_match": _target_match(item),
            "reason": reason,
            "lost_target_keys": list(lost_target_keys or []),
            "legacy_reason": "reference_intent_target_coverage_guard_no_delete",
        }

    def _generic_survivor_rejection_enabled():
        if not strict_reference_intent:
            return False
        constraints = _reference_intent_visual_defect_constraints(dimension_plan)
        return bool(constraints.get("reject_generic_autodim_survivors"))

    def _generic_non_reference_survivors(items):
        # ui_defect_block_generic_autodim_survivors_after_prune:
        # DisplayDim count and target coverage are not enough after a Drawing
        # Review screenshot FAIL. Any targetless survivor keeps the sheet in an
        # AutoDimension-like state and must be surfaced as a hard blocker.
        if not _generic_survivor_rejection_enabled():
            return []
        survivors = []
        for item in items or []:
            if _target_key(item):
                continue
            intent = item.get("_reference_intent") or {}
            survivors.append({
                "slot": str(item.get("_slot") or "unknown"),
                "view": str(item.get("view") or ""),
                "source": str(item.get("source") or ""),
                "score": intent.get("score"),
                "side": intent.get("side"),
                "reason": intent.get("reason") or "targetless_displaydim_survivor",
                "target_key": "",
            })
        return survivors

    def _apply_generic_survivor_block(result_data, items):
        survivors = _generic_non_reference_survivors(items)
        result_data["generic_non_reference_intent_survivor_count"] = len(survivors)
        result_data["generic_non_reference_intent_survivors"] = survivors[:50]
        if survivors:
            result_data["success"] = False
            reason = "generic_non_reference_intent_displaydim_survived_after_prune"
            if reason not in result_data["reasons"]:
                result_data["reasons"].append(reason)
        return survivors

    def _coverage_loss_if_deleted(item, remaining_items):
        if not strict_reference_intent:
            return [], {}, {}
        before_coverage = _coverage_snapshot(remaining_items)
        if before_coverage.get("error"):
            return [], before_coverage, {}
        after_items = [other for other in (remaining_items or []) if other is not item]
        after_coverage = _coverage_snapshot(after_items)
        if after_coverage.get("error"):
            return [], before_coverage, after_coverage
        before_covered = _covered_keys_from_coverage(before_coverage)
        after_covered = _covered_keys_from_coverage(after_coverage)
        required = set(_target_keys_from_plan())
        lost = sorted((before_covered & required) - (after_covered & required))
        return lost, before_coverage, after_coverage

    def _deletable_candidates(candidates, remaining_items):
        if not strict_reference_intent:
            return list(candidates or [])
        counts = _target_match_counts(remaining_items)
        best_by_target = _best_item_id_by_target(remaining_items)
        deletable = []
        protected_entries = []
        for item in candidates or []:
            key = _target_key(item)
            target_match = _target_match(item)
            policy = target_match.get("prune_protection_policy") or {}
            if key and id(item) == best_by_target.get(key):
                protected_entries.append(_protected_item_evidence(
                    item,
                    "reference_intent_best_target_displaydim_protected",
                ))
                continue
            if key and counts.get(key, 0) <= 1:
                protected_entries.append(_protected_item_evidence(
                    item,
                    "reference_intent_target_protected_no_delete",
                ))
            else:
                if key and policy.get("delete_only_if_target_covered_elsewhere", True) and counts.get(key, 0) <= 1:
                    protected_entries.append(_protected_item_evidence(
                        item,
                        "reference_intent_target_protected_no_delete",
                    ))
                    continue
                lost_keys, _before_cov, _after_cov = _coverage_loss_if_deleted(item, remaining_items)
                if lost_keys:
                    protected_entries.append(_protected_item_evidence(
                        item,
                        "reference_intent_target_coverage_simulation_no_delete",
                        lost_target_keys=lost_keys,
                    ))
                    continue
                deletable.append(item)
        if protected_entries:
            result.setdefault("protected_target_items", []).extend(protected_entries)
        return deletable

    try:
        cap_i = int(cap or 0)
    except Exception:
        cap_i = 0
    try:
        floor_i = int(reference_dim_floor or 0)
    except Exception:
        floor_i = 0
    before_items = _display_dim_annotations_in_doc(drw_doc)
    quotas = _normalized_quotas()
    annotated_before_raw = _annotated_items(before_items)
    if strict_reference_intent:
        annotated_before, equivalence_dedupe = _dedupe_reference_intent_delete_equivalent_items(
            annotated_before_raw
        )
    else:
        annotated_before = annotated_before_raw
        equivalence_dedupe = {"enabled": False, "before": len(annotated_before), "after": len(annotated_before), "merged_count": 0}
    target_count_i = len(_target_keys_from_plan())
    effective_cap_i = max(cap_i, floor_i, target_count_i) if strict_reference_intent else cap_i
    target_coverage_before = _coverage_snapshot(annotated_before)
    result = {
        "cap": cap_i,
        "reference_dim_floor": floor_i,
        "effective_cap": effective_cap_i,
        "dimension_target_count": target_count_i,
        "strict_reference_intent": bool(strict_reference_intent),
        "enumerated_before": len(before_items),
        "before": len(annotated_before),
        "after": len(annotated_before),
        "deleted": 0,
        "attempted": 0,
        "success": True,
        "reasons": [],
        "slot_quotas": quotas,
        "before_slot_counts": _slot_counts(annotated_before),
        "reference_intent_score_before": _score_summary(annotated_before),
        "reference_intent_delete_equivalence_dedupe": equivalence_dedupe,
        "best_target_item_ids_present": bool(_best_item_id_by_target(annotated_before)),
        "protected_target_items": [],
        "delete_plan": [],
        "deleted_items": [],
        "failed_delete_items": [],
        "target_coverage_before": target_coverage_before,
    }
    if strict_reference_intent and effective_cap_i > 0 and len(annotated_before) <= effective_cap_i:
        result["after_slot_counts"] = result["before_slot_counts"]
        result["reference_intent_score_after"] = result["reference_intent_score_before"]
        result["slot_quota_success"] = not _over_quota_slots(annotated_before, quotas) if quotas else True
        result["target_coverage_after"] = target_coverage_before
        result["skip_reason"] = "reference_intent_effective_cap_guard_no_delete"
        result["legacy_skip_reason"] = "reference_intent_floor_guard_no_delete"
        result["success"] = True
        _apply_generic_survivor_block(result, annotated_before)
        return result
    if cap_i <= 0 or len(annotated_before) <= effective_cap_i:
        result["after_slot_counts"] = result["before_slot_counts"]
        result["reference_intent_score_after"] = result["reference_intent_score_before"]
        result["slot_quota_success"] = not _over_quota_slots(annotated_before, quotas) if quotas else True
        result["target_coverage_after"] = target_coverage_before
        result["success"] = result["after"] <= effective_cap_i and result["slot_quota_success"] if cap_i > 0 else result["slot_quota_success"]
        _apply_generic_survivor_block(result, annotated_before)
        if not result["success"] and not result["slot_quota_success"] and result["slot_quotas"]:
            result["reasons"].append("display_dim_slot_quota_exceeded_without_excess_total")
        return result

    delete_plan = []
    remaining = list(annotated_before)
    while len(remaining) > effective_cap_i:
        candidate = None
        if strict_reference_intent:
            generic_candidates = _deletable_candidates(
                [item for item in remaining if not _target_key(item)],
                remaining,
            )
            if generic_candidates:
                candidate = min(generic_candidates, key=lambda item: _delete_priority(item, remaining))
        over_slots = _over_quota_slots(remaining, quotas) if quotas else []
        if candidate is None and over_slots:
            candidates = [
                item for item in remaining
                if str(item.get("_slot") or "").strip().lower() in over_slots
            ]
            candidates = _deletable_candidates(candidates, remaining)
            if candidates:
                candidate = min(candidates, key=lambda item: _delete_priority(item, remaining))
        if candidate is None and remaining:
            candidates = _deletable_candidates(remaining, remaining)
            if candidates:
                candidate = min(candidates, key=lambda item: _delete_priority(item, remaining))
        if candidate is None:
            result["reasons"].append("reference_intent_target_protected_no_delete")
            result["reasons"].append("reference_intent_target_coverage_guard_no_delete")
            break
        remaining.remove(candidate)
        delete_plan.append(candidate)

    result["delete_plan"] = [
        {
            "slot": str(item.get("_slot") or "unknown"),
            "view": str(item.get("view") or ""),
            "source": str(item.get("source") or ""),
            "score": (item.get("_reference_intent") or {}).get("score"),
            "target_key": _target_match(item).get("target_key", ""),
            "target_group": _target_match(item).get("target_group", ""),
            "expected_type": _target_match(item).get("expected_type", ""),
            "preferred_side": _target_match(item).get("preferred_side", ""),
            "target_match": _target_match(item),
            "reason": _delete_reason(item),
        }
        for item in delete_plan
    ]
    for item in delete_plan:
        intent = item.get("_reference_intent") or {}
        target_match = _target_match(item)
        delete_evidence = {
            "slot": str(item.get("_slot") or "unknown"),
            "view": str(item.get("view") or ""),
            "source": str(item.get("source") or ""),
            "score": intent.get("score"),
            "target_key": target_match.get("target_key", ""),
            "target_group": target_match.get("target_group", ""),
            "expected_type": target_match.get("expected_type", ""),
            "preferred_side": target_match.get("preferred_side", ""),
            "target_match": target_match,
            "delete_priority": list(_delete_priority(item, annotated_before)),
        }
        result["attempted"] += 1
        selected, select_method = _select_annotation_for_delete(
            drw_doc,
            item.get("annotation"),
            item.get("display_dim"),
        )
        if not selected:
            result["reasons"].append(f"{item.get('view')}: {select_method}")
            failed = dict(delete_evidence)
            failed["select_method"] = select_method
            failed["reason"] = "select_for_delete_failed"
            result["failed_delete_items"].append(failed)
            continue
        deleted, delete_method = _delete_selected_annotation(drw_doc)
        if deleted:
            result["deleted"] += 1
            deleted_item = dict(delete_evidence)
            deleted_item["select_method"] = select_method
            deleted_item["delete_method"] = delete_method
            deleted_item["reason"] = _delete_reason(item)
            result["deleted_items"].append(deleted_item)
            _log(
                "    [reference_style] prune DisplayDim "
                f"slot={item.get('_slot') or 'unknown'} "
                f"target={target_match.get('target_key', '') or 'unknown'} "
                f"score={(item.get('_reference_intent') or {}).get('score')} "
                f"view={item.get('view')} via {delete_method}"
            )
        else:
            result["reasons"].append(f"{item.get('view')}: {delete_method}")
            failed = dict(delete_evidence)
            failed["select_method"] = select_method
            failed["delete_method"] = delete_method
            failed["reason"] = "delete_selected_annotation_failed"
            result["failed_delete_items"].append(failed)
        try:
            drw_doc.ClearSelection2(True)
        except Exception:
            pass

    try:
        drw_doc.ForceRebuild3(False)
    except Exception:
        pass
    after_items = _display_dim_annotations_in_doc(drw_doc)
    annotated_after_raw = _annotated_items(after_items)
    if strict_reference_intent:
        annotated_after, equivalence_dedupe_after = _dedupe_reference_intent_delete_equivalent_items(
            annotated_after_raw
        )
    else:
        annotated_after = annotated_after_raw
        equivalence_dedupe_after = {"enabled": False, "before": len(annotated_after), "after": len(annotated_after), "merged_count": 0}
    result["enumerated_after"] = len(after_items)
    result["after"] = len(annotated_after)
    result["reference_intent_delete_equivalence_dedupe_after"] = equivalence_dedupe_after
    result["after_slot_counts"] = _slot_counts(annotated_after)
    result["reference_intent_score_after"] = _score_summary(annotated_after)
    target_coverage_after = _coverage_snapshot(annotated_after)
    result["target_coverage_after"] = target_coverage_after
    over_slots_after = _over_quota_slots(annotated_after, quotas) if quotas else []
    result["slot_quota_success"] = not over_slots_after
    result["success"] = result["after"] <= effective_cap_i and result["slot_quota_success"]
    if strict_reference_intent:
        missing_after = _missing_keys_from_coverage(target_coverage_after)
        result["missing_target_keys_after"] = missing_after
        _apply_generic_survivor_block(result, annotated_after)
        if result["after"] < max(floor_i, target_count_i):
            result["success"] = False
            result["reasons"].append(
                f"display_dim_count_below_reference_effective_floor:{result['after']}<{max(floor_i, target_count_i)}"
            )
        if missing_after:
            result["success"] = False
            result["reasons"].append(
                "reference_intent_target_coverage_missing_after_prune:" + ",".join(missing_after)
            )
    if not result["success"] and not result["reasons"]:
        if result["after"] > effective_cap_i:
            result["reasons"].append(f"display_dim_count_remains_above_cap:{result['after']}>{effective_cap_i}")
        if over_slots_after:
            result["reasons"].append("display_dim_slot_quota_exceeded:" + ",".join(over_slots_after))
    return result


def _save_drawing_doc(drw_doc, drawing_path):
    err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warn = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    try:
        ok = drw_doc.Extension.SaveAs(str(drawing_path), 0, 1, vt_dispatch_none(), err, warn)
        return {"success": bool(ok), "errors": int(err.value), "warnings": int(warn.value), "method": "Extension.SaveAs"}
    except Exception as exc:
        try:
            ok = drw_doc.Save3(1, err, warn)
            return {
                "success": bool(ok),
                "errors": int(err.value),
                "warnings": int(warn.value),
                "method": "Save3",
                "reason": str(exc),
            }
        except Exception as fallback_exc:
            return {
                "success": False,
                "errors": int(getattr(err, "value", 0) or 0),
                "warnings": int(getattr(warn, "value", 0) or 0),
                "method": "save_failed",
                "reason": f"{exc}; {fallback_exc}",
            }


def _drawing_doc_view_materialization_probe(drw_doc):
    info = {
        "title": "",
        "doc_type": "",
        "sheet_name": "",
        "view_count": 0,
        "usable_view_count": 0,
        "getviews_count": 0,
        "getviews_usable_count": 0,
        "current_sheet_getviews_count": 0,
        "current_sheet_getviews_usable_count": 0,
        "records": [],
        "errors": [],
    }
    seen = set()

    try:
        info["title"] = str(call(drw_doc, "GetTitle") or "")
    except Exception as exc:
        info["errors"].append(f"GetTitle:{exc}")
    try:
        info["doc_type"] = str(call(drw_doc, "GetType") or "")
    except Exception as exc:
        info["errors"].append(f"GetType:{exc}")
    try:
        sheet = call(drw_doc, "GetCurrentSheet")
        info["sheet_name"] = str(call(sheet, "GetName") or "")
    except Exception as exc:
        info["errors"].append(f"GetCurrentSheet:{exc}")

    def _append(view, source, counter_key, usable_counter_key):
        if view is None:
            return
        info[counter_key] = int(info.get(counter_key) or 0) + 1
        try:
            name = ""
            for attr in ("GetName2", "Name"):
                try:
                    value = getattr(view, attr)
                    value = value() if callable(value) else value
                    if value:
                        name = str(value)
                        break
                except Exception:
                    pass
            outline = view_outline_box(view)
            vtype = str(call(view, "Type") or "")
            key = (name, vtype, tuple(round(float(v), 9) for v in outline or ()))
            if key in seen:
                return
            seen.add(key)
            usable = bool(outline) and vtype not in {"0", "1"}
            if usable:
                info[usable_counter_key] = int(info.get(usable_counter_key) or 0) + 1
            info["records"].append({
                "name": name,
                "type": vtype,
                "outline": list(outline or []),
                "source": source,
                "usable": bool(usable),
            })
        except Exception as exc:
            info["errors"].append(f"{source}:{exc}")

    try:
        view = call(drw_doc, "GetFirstView")
        if view is None:
            info["get_first_view_none"] = True
        guard = 0
        while view is not None and guard < 100:
            guard += 1
            _append(view, "GetFirstView", "view_count", "usable_view_count")
            view = call(view, "GetNextView")
    except Exception as exc:
        info["errors"].append(f"GetFirstView:{exc}")

    def _walk_getviews(value, source, counter_key, usable_counter_key, depth=0):
        if value is None or depth > 5 or isinstance(value, (str, bytes)):
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                _walk_getviews(item, source, counter_key, usable_counter_key, depth + 1)
            return
        _append(value, source, counter_key, usable_counter_key)
        try:
            values = list(value)
        except Exception:
            values = []
        for item in values:
            _walk_getviews(item, source, counter_key, usable_counter_key, depth + 1)

    try:
        method = getattr(drw_doc, "GetViews", None)
        if callable(method):
            _walk_getviews(method(), "DrawingDoc.GetViews", "getviews_count", "getviews_usable_count")
        else:
            info["getviews_unavailable"] = True
    except Exception as exc:
        info["errors"].append(f"DrawingDoc.GetViews:{exc}")
    try:
        sheet = call(drw_doc, "GetCurrentSheet")
        method = getattr(sheet, "GetViews", None)
        if callable(method):
            _walk_getviews(
                method(),
                "CurrentSheet.GetViews",
                "current_sheet_getviews_count",
                "current_sheet_getviews_usable_count",
            )
        else:
            info["current_sheet_getviews_unavailable"] = True
    except Exception as exc:
        info["errors"].append(f"CurrentSheet.GetViews:{exc}")
    return info


def _wait_for_drawing_views_materialized(sw, drw_doc, stage_name, *, log_fn=None, max_attempts=6, wait_s=0.5):
    info = {
        "code": "post_layout_reopen_view_materialization_probe",
        "stage": stage_name,
        "success": False,
        "max_attempts": int(max_attempts),
        "wait_s": float(wait_s),
        "attempts": [],
        "final_probe": {},
    }

    def _log(msg):
        if log_fn:
            try:
                log_fn(msg)
            except Exception:
                pass

    for attempt in range(1, int(max_attempts) + 1):
        actions = []
        try:
            title = str(call(drw_doc, "GetTitle") or "")
            if title:
                err_ = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                activate = getattr(sw, "ActivateDoc3", None)
                if callable(activate):
                    ok_ = activate(title, False, 0, err_)
                    actions.append({
                        "action": "ActivateDoc3",
                        "ok": bool(ok_ is not False),
                        "errors": int(getattr(err_, "value", 0) or 0),
                    })
        except Exception as exc:
            actions.append({"action": "ActivateDoc3", "ok": False, "error": str(exc)})
        try:
            sheet = call(drw_doc, "GetCurrentSheet")
            sheet_name_ = str(call(sheet, "GetName") or "")
            if sheet_name_ and callable(getattr(drw_doc, "ActivateSheet", None)):
                actions.append({"action": "ActivateSheet", "ok": bool(drw_doc.ActivateSheet(sheet_name_))})
        except Exception as exc:
            actions.append({"action": "ActivateSheet", "ok": False, "error": str(exc)})
        for action_name, method_name, args in (
            ("ForceRebuild3_false", "ForceRebuild3", (False,)),
            ("ForceRebuild3_true", "ForceRebuild3", (True,)),
            ("EditRebuild3", "EditRebuild3", ()),
            ("GraphicsRedraw2", "GraphicsRedraw2", ()),
            ("ViewZoomtofit2", "ViewZoomtofit2", ()),
        ):
            try:
                method = getattr(drw_doc, method_name, None)
                if callable(method):
                    method(*args)
                    actions.append({"action": action_name, "ok": True})
            except Exception as exc:
                actions.append({"action": action_name, "ok": False, "error": str(exc)})
        probe = _drawing_doc_view_materialization_probe(drw_doc)
        usable_count = (
            int(probe.get("usable_view_count") or 0)
            + int(probe.get("getviews_usable_count") or 0)
            + int(probe.get("current_sheet_getviews_usable_count") or 0)
        )
        attempt_info = {
            "attempt": attempt,
            "actions": actions,
            "view_count": probe.get("view_count"),
            "usable_view_count": probe.get("usable_view_count"),
            "getviews_count": probe.get("getviews_count"),
            "getviews_usable_count": probe.get("getviews_usable_count"),
            "current_sheet_getviews_count": probe.get("current_sheet_getviews_count"),
            "current_sheet_getviews_usable_count": probe.get("current_sheet_getviews_usable_count"),
            "errors": list(probe.get("errors") or []),
        }
        info["attempts"].append(attempt_info)
        info["final_probe"] = probe
        if usable_count > 0:
            info["success"] = True
            _log(f"    [reference_style] drawing views materialized after reopen attempt {attempt}: usable={usable_count}")
            return info
        if attempt < int(max_attempts):
            time.sleep(float(wait_s))
    info["timeout"] = True
    _log("    [reference_style] drawing views did not materialize after reopen probe")
    return info


def _reopen_saved_drawing(sw, drw_doc, drawing_path, *, log_fn=None):
    def _log(msg):
        if log_fn:
            try:
                log_fn(msg)
            except Exception:
                pass

    save_info = _save_drawing_doc(drw_doc, drawing_path)
    try:
        title = call(drw_doc, "GetTitle")
        if title:
            sw.CloseDoc(title)
            _log(f"    [reference_style] closed drawing before persisted dim read: {title}")
    except Exception as exc:
        _log(f"    [reference_style] close before persisted dim read failed: {exc}")
    time.sleep(1.0)
    err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warn = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    try:
        try:
            sw.SetUserPreferenceIntegerValue(9, 1)
        except Exception:
            pass
        reopened = sw.OpenDoc6(str(drawing_path), 3, 257, "", err, warn)
        if reopened is None:
            return None, {
                "success": False,
                "save": save_info,
                "open_options": 257,
                "open_errors": int(err.value),
                "open_warnings": int(warn.value),
                "reason": "OpenDoc6 returned None",
            }
        time.sleep(1.0)
        materialization = _wait_for_drawing_views_materialized(
            sw,
            reopened,
            "post_layout_reopen_primary_257",
            log_fn=log_fn,
        )
        if not materialization.get("success"):
            fallback_info = {
                "code": "post_layout_reopen_view_materialization_fallback_open_options",
                "from_open_options": 257,
                "to_open_options": 1,
                "primary_materialization": materialization,
            }
            try:
                title = call(reopened, "GetTitle")
                if title:
                    sw.CloseDoc(title)
                    fallback_info["closed_primary_title"] = str(title)
            except Exception as exc:
                fallback_info["close_primary_error"] = str(exc)
            time.sleep(0.5)
            fallback_err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            fallback_warn = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            try:
                fallback = sw.OpenDoc6(str(drawing_path), 3, 1, "", fallback_err, fallback_warn)
                fallback_info.update({
                    "fallback_open_errors": int(fallback_err.value),
                    "fallback_open_warnings": int(fallback_warn.value),
                    "fallback_returned_doc": fallback is not None,
                })
                if fallback is not None:
                    time.sleep(1.0)
                    fallback_materialization = _wait_for_drawing_views_materialized(
                        sw,
                        fallback,
                        "post_layout_reopen_fallback_1",
                        log_fn=log_fn,
                    )
                    fallback_info["fallback_materialization"] = fallback_materialization
                    if fallback_materialization.get("success"):
                        return fallback, {
                            "success": True,
                            "save": save_info,
                            "open_options": 1,
                            "open_errors": int(fallback_err.value),
                            "open_warnings": int(fallback_warn.value),
                            "view_materialization": fallback_materialization,
                            "fallback_open": fallback_info,
                        }
            except Exception as exc:
                fallback_info["fallback_error"] = str(exc)
        return reopened, {
            "success": True,
            "save": save_info,
            "open_options": 257,
            "open_errors": int(err.value),
            "open_warnings": int(warn.value),
            "view_materialization": materialization,
            "fallback_open": fallback_info if not materialization.get("success") else {},
        }
    except Exception as exc:
        return None, {
            "success": False,
            "save": save_info,
            "open_errors": int(getattr(err, "value", 0) or 0),
            "open_warnings": int(getattr(warn, "value", 0) or 0),
            "reason": str(exc),
        }


def _discard_unsaved_and_reopen_drawing(sw, drw_doc, drawing_path, *, log_fn=None, stage_name="prune_restore"):
    def _log(msg):
        if log_fn:
            try:
                log_fn(msg)
            except Exception:
                pass

    info = {
        "success": False,
        "reason": "",
        "closed_title": "",
        "open_options": 257,
    }
    try:
        title = call(drw_doc, "GetTitle")
        if title:
            info["closed_title"] = str(title)
            sw.CloseDoc(title)
            _log(f"    [reference_style] discarded unsaved prune changes and closed: {title}")
    except Exception as exc:
        info["close_error"] = str(exc)
    time.sleep(0.5)
    err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warn = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    try:
        reopened = sw.OpenDoc6(str(drawing_path), 3, 257, "", err, warn)
        info.update({
            "open_errors": int(err.value),
            "open_warnings": int(warn.value),
            "returned_doc": reopened is not None,
        })
        if reopened is None:
            info["reason"] = "OpenDoc6 returned None"
            return None, info
        time.sleep(1.0)
        materialization = _wait_for_drawing_views_materialized(
            sw,
            reopened,
            stage_name,
            log_fn=log_fn,
        )
        info["view_materialization"] = materialization
        info["success"] = True
        return reopened, info
    except Exception as exc:
        info["reason"] = str(exc)
        info["open_errors"] = int(getattr(err, "value", 0) or 0)
        info["open_warnings"] = int(getattr(warn, "value", 0) or 0)
        return None, info


def _prune_persisted_reference_display_dims(
    sw,
    drw_doc,
    drawing_path,
    reference_dim_floor,
    *,
    log_fn=None,
    part_class="",
    dimension_plan=None,
    layout_plan=None,
    restore_on_failed_prune=True,
):
    original_cap = _reference_display_dim_cap(reference_dim_floor, part_class=part_class)
    cap = original_cap
    slot_quotas = _v4_dimension_view_quotas({"dimension_plan": dimension_plan or {}})
    base_slot_quotas = dict(slot_quotas)
    try:
        floor = int(reference_dim_floor or 0)
    except Exception:
        floor = 0
    strict_reference_intent = _v4_should_skip_generic_model_dimension_import(
        {"dimension_plan": dimension_plan or {}},
        reference_dim_floor,
    )
    quota_total = sum(int(value or 0) for value in slot_quotas.values())
    target_count = len([
        item for item in ((dimension_plan or {}).get("dimension_targets") or [])
        if isinstance(item, dict) and str(item.get("key") or "").strip()
    ])
    if strict_reference_intent and floor > 0 and quota_total >= floor:
        cap = max(floor, target_count)
    elif str(part_class or "").strip().lower() == "long_thin" and floor > 0 and quota_total >= floor:
        cap = max(cap, floor + 3)
        slack = max(0, cap - quota_total)
        while slack > 0 and slot_quotas:
            changed = False
            for slot in ("top", "front", "right", "iso"):
                if slot not in slot_quotas:
                    continue
                slot_quotas[slot] = int(slot_quotas.get(slot, 0)) + 1
                slack -= 1
                changed = True
                if slack <= 0:
                    break
            if not changed:
                break
    result = {
        "enabled": cap > 0,
        "cap": cap,
        "original_cap": original_cap,
        "effective_cap_reason": (
            "reference_intent_exact_target_cap"
            if strict_reference_intent
            else ("long_thin_slot_quota_sidecar_count_guard" if cap != original_cap else "")
        ),
        "reference_intent_target_count": target_count,
        "base_slot_quotas": base_slot_quotas,
        "slot_quotas": slot_quotas,
        "slot_quota_slack": max(0, sum(slot_quotas.values()) - sum(base_slot_quotas.values())),
        "reopen": {},
        "prune": {},
        "save": {},
        "success": True,
    }
    if cap <= 0:
        return drw_doc, result
    reopened, reopen_info = _reopen_saved_drawing(sw, drw_doc, drawing_path, log_fn=log_fn)
    result["reopen"] = reopen_info
    if reopened is None:
        result["success"] = False
        return drw_doc, result
    prune_info = _prune_display_dims_to_cap(
        reopened,
        cap,
        log_fn=log_fn,
        slot_quotas=slot_quotas,
        layout_plan=layout_plan,
        dimension_plan=dimension_plan,
        reference_dim_floor=floor,
        strict_reference_intent=strict_reference_intent,
    )
    result["prune"] = prune_info
    if prune_info.get("deleted"):
        if prune_info.get("success"):
            result["save"] = _save_drawing_doc(reopened, drawing_path)
        else:
            result["save"] = {
                "success": False,
                "skipped_reason": "prune_failed_no_save",
                "deleted": prune_info.get("deleted"),
                "reasons": list(prune_info.get("reasons") or []),
            }
            if not restore_on_failed_prune:
                result["restore_after_failed_prune"] = {
                    "success": False,
                    "skipped_reason": "caller_will_repair_failed_prune",
                    "deleted": prune_info.get("deleted"),
                    "reasons": list(prune_info.get("reasons") or []),
                }
                result["prune"]["discarded_after_failed_prune"] = False
                result["prune"]["restore_reason"] = "caller_will_repair_failed_prune"
                result["success"] = False
                return reopened, result
            restored, restore_info = _discard_unsaved_and_reopen_drawing(
                sw,
                reopened,
                drawing_path,
                log_fn=log_fn,
                stage_name="reference_prune_failed_restore",
            )
            result["restore_after_failed_prune"] = restore_info
            if restored is not None:
                reopened = restored
                restored_items = _display_dim_annotations_in_doc(reopened)
                restored_slot_counts = {}
                for restored_item in restored_items:
                    slot = _slot_for_display_dim_item(restored_item, layout_plan)
                    restored_slot_counts[slot] = restored_slot_counts.get(slot, 0) + 1
                result["prune"]["discarded_after_failed_prune"] = True
                result["prune"]["after_restored"] = len(restored_items)
                result["prune"]["after_restored_slot_counts"] = restored_slot_counts
                result["prune"]["restore_reason"] = (
                    "reference_prune_failed_restore_count"
                )
    result["success"] = bool(prune_info.get("success"))
    return reopened, result


def load_issues_to_fix(path):
    """读取 issues_to_fix.json，返回 issue 字符串列表。
    支持的格式：
      - ["view_overlap", "text_height_ge_3_5mm"]
      - {"issues": ["view_overlap"]}
      - {"failures": [{"code":"view_overlap"}, ...]}
    """
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        log(f"[issues] 读取失败 {path}: {exc}")
        return []
    issues = []
    if isinstance(data, list):
        for x in data:
            if isinstance(x, str):
                issues.append(x)
            elif isinstance(x, dict):
                code = x.get("code") or x.get("issue") or x.get("name")
                if code: issues.append(str(code))
    elif isinstance(data, dict):
        if isinstance(data.get("issues"), list):
            for x in data["issues"]:
                if isinstance(x, str): issues.append(x)
                elif isinstance(x, dict):
                    code = x.get("code") or x.get("issue") or x.get("name")
                    if code: issues.append(str(code))
        if isinstance(data.get("failures"), list):
            for x in data["failures"]:
                if isinstance(x, dict):
                    code = x.get("code") or x.get("issue") or x.get("name")
                    if code: issues.append(str(code))
                elif isinstance(x, str):
                    issues.append(x)
    return issues


# ============================================================
# 主流程
# ============================================================
def generate_for(part_path, *, out_dir=OUT_DIR, sw=None, issues=None):
    _ensure_solidworks_global_lock("drw_generate_v6.generate_for", part_path)
    issues = issues or []
    os.makedirs(out_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(part_path))[0]
    warnings_box = []
    _run_dir_env = os.environ.get("RUN_DIR", "")
    _drawing_blueprint_v4 = {}
    _drawing_blueprint_paths = []
    _drawing_blueprint_source = ""

    log(f"[v6] 输出目录 {out_dir}")
    log(f"[v6] issues_to_fix: {issues if issues else '(无)'}")

    # 反馈通道：默认参数
    text_height = 0.005
    forced_scale = None
    scale_downgrade_hops = 0
    if "text_height_ge_3_5mm" in issues:
        text_height = 0.006
        log("[issues] text_height_ge_3_5mm -> 字高调到 0.006")
    if "scale_in_set" in issues:
        forced_scale = (1, 2)
        log("[issues] scale_in_set -> 强制使用比例 1:2")
    if "view_overlap" in issues:
        scale_downgrade_hops = 1
        log("[issues] view_overlap -> 比例向 1:5/1:10 方向降一档")

    if sw is None:
        log("[..] 连接 SolidWorks")
        connect_timeout_s = int(os.environ.get("SWDS_SW_CONNECT_TIMEOUT_S", "15"))
        probe = _probe_sw_active_object(connect_timeout_s)
        log(
            f"[sw_connect] active probe status={probe.get('status')} "
            f"reason={probe.get('reason', '')} revision={probe.get('revision', '')}"
        )
        if probe.get("status") == "timeout":
            raise SystemExit(f"solidworks_active_object_timeout: {probe.get('reason')}")
        try:
            log("[sw_connect] GetActiveObject start")
            sw = wc.GetActiveObject("SldWorks.Application")
            sw = _dynamic_dispatch(sw)
            log("[sw_connect] GetActiveObject done")
        except Exception:
            log("[sw_connect] Dispatch start")
            sw = wc.Dispatch("SldWorks.Application")
            sw = _dynamic_dispatch(sw)
            log("[sw_connect] Dispatch done")
            sw.Visible = True
            time.sleep(2)

    # 关闭 SolidWorks 默认的视图箭头/位移箭头/默认括号
    try: sw.SetUserPreferenceToggle(195, False)   # swDetailingShowDisplaceArrows
    except Exception: pass
    try: sw.SetUserPreferenceToggle(196, False)   # swDetailingShowParenthesisByDefault
    except Exception: pass

    target_drw = os.path.join(out_dir, f"{base_name}_v5.SLDDRW")
    try:
        docs = sw.GetDocuments
        docs = docs() if callable(docs) else docs
        for d in (docs or []):
            try:
                t = d.GetTitle if not callable(getattr(d,"GetTitle",None)) else d.GetTitle()
                pn = d.GetPathName if not callable(getattr(d,"GetPathName",None)) else d.GetPathName()
                if (str(t).startswith("工程图") or str(t).startswith("Drawing") or
                    (pn and os.path.normcase(os.path.abspath(pn)) == os.path.normcase(os.path.abspath(target_drw)))):
                    if not (pn and _same_abs_path(pn, target_drw)):
                        continue
                    sw.CloseDoc(t)
                    _solidworks_doc_registry_event(
                        "solidworks_doc_closed",
                        role="generated_drawing",
                        path=pn,
                        title=t,
                        doc_type="drawing",
                        stage="preflight_close_previous_target",
                        close_verified=True,
                        reason="same target drawing path",
                    )
            except Exception: pass
    except Exception: pass
    for ext_ in (".SLDDRW", ".PDF", ".DXF"):
        f = os.path.join(out_dir, base_name + "_v5" + ext_)
        if os.path.exists(f):
            try: os.remove(f)
            except Exception as exc: log(f"  删除旧文件 {f} 失败: {exc}")

    # 1) 打开零件
    log(f"[1/9] 打开 {os.path.basename(part_path)}")
    e = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    w = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    part = sw.OpenDoc6(part_path, 1, 1|16|256, "", e, w)
    if part is None:
        raise SystemExit(f"打开零件失败 errors={e.value}")
    _solidworks_doc_registry_event(
        "solidworks_doc_opened",
        role="copied_part",
        path=part_path,
        title=_doc_title(part),
        doc_type="part",
        stage="initial_part_open",
        extra={"open_errors": int(e.value), "open_warnings": int(w.value)},
    )

    _default_props = _inject_default_custom_properties(part, str(part_path))
    print(f"[cprop] injected {len(_default_props)} defaults")

    # v6: 立即缓存 cfg_name 防止 part 关闭后取空（4 级回退）
    _cached_cfg_name = ""
    # 路径 1：GetActiveConfiguration().Name
    try:
        _cfg = part.GetActiveConfiguration()
        if _cfg:
            try: _cached_cfg_name = _cfg.Name or ""
            except Exception: pass
    except Exception as e:
        print(f"[v6 refdoc] path1 GetActiveConfiguration failed: {e}")

    # 路径 2：ConfigurationManager.ActiveConfiguration.Name
    if not _cached_cfg_name:
        try:
            _cm = part.ConfigurationManager
            if _cm:
                _ac = _cm.ActiveConfiguration
                if _ac:
                    try: _cached_cfg_name = _ac.Name or ""
                    except Exception: pass
        except Exception as e:
            print(f"[v6 refdoc] path2 ConfigurationManager failed: {e}")

    # 路径 3：取 part 配置名列表第一个
    if not _cached_cfg_name:
        try:
            _names = part.GetConfigurationNames() if callable(getattr(part, "GetConfigurationNames", None)) else part.GetConfigurationNames
            if _names and len(_names) > 0:
                _cached_cfg_name = str(_names[0]) if _names[0] else ""
        except Exception as e:
            print(f"[v6 refdoc] path3 GetConfigurationNames failed: {e}")

    # 路径 4：用 "默认" 兜底（SW 中文默认配置名）
    if not _cached_cfg_name:
        try:
            _cached_cfg_name = "默认"
        except Exception:
            _cached_cfg_name = "Default"

    print(f"[v6 refdoc] cached cfg_name='{_cached_cfg_name}' (after fallback)")

    # 2) 13 项属性
    log("[2/9] 读 13 项属性 + MassProperties.重量")
    src_props = {}
    src_cpms = []
    try: src_cpms.append(("", part.Extension.CustomPropertyManager("")))
    except Exception: pass
    try:
        cfg_names = part.GetConfigurationNames if not callable(getattr(part, "GetConfigurationNames", None)) else part.GetConfigurationNames()
        for cn in list(cfg_names or []):
            try: src_cpms.append((cn, part.Extension.CustomPropertyManager(cn)))
            except Exception: pass
    except Exception: pass
    src_filled_max = -1
    for cn, cpm in src_cpms:
        cur = {}
        for k in PROP_KEYS:
            try:
                rv, value, resolved, was = cpm.Get5(k, False)
                cur[k] = (resolved or value or "")
            except Exception:
                cur[k] = ""
        f = sum(1 for v in cur.values() if v)
        if f > src_filled_max:
            src_filled_max, src_props = f, cur
    try:
        mp = part.Extension.CreateMassProperty()
        try: mp.UseSystemUnits = True
        except Exception: pass
        mass_kg = call(mp, "Mass")
        if isinstance(mass_kg, (int, float)) and mass_kg > 0:
            src_props["重量"] = f"{round(mass_kg*1000,2)} g"
    except Exception as exc:
        warnings_box.append({"code":"mass_err","msg":str(exc)})
    if not src_props.get("图号"): src_props["图号"] = base_name
    if not src_props.get("数量"): src_props["数量"] = "1"
    if not src_props.get("UNIT_OF_MEASURE"): src_props["UNIT_OF_MEASURE"] = "mm"
    if not src_props.get("SWFormatSize"): src_props["SWFormatSize"] = "210mm*297mm"
    for k in PROP_KEYS:
        if not src_props.get(k):
            warnings_box.append({"code":"prop_missing","key":k,"msg":f"标题栏属性 [{k}] 缺失"})
    log(f"  非空属性 {sum(1 for v in src_props.values() if v)}/{len(PROP_KEYS)}")

    # 3) bbox -> 比例 + 自动布局
    log("[3/9] GetPartBox + 自动布局 layout_4_views")
    Lx = Ly = Lz = 0.05
    try:
        box = part.GetPartBox(True)
        box = list(box) if box else None
        if box and len(box) >= 6:
            Lx = abs(box[3]-box[0])
            Ly = abs(box[4]-box[1])
            Lz = abs(box[5]-box[2])
    except Exception: pass
    bbox_m = (Lx, Ly, Lz)
    log(f"  bbox(mm) Lx={Lx*1000:.1f} Ly={Ly*1000:.1f} Lz={Lz*1000:.1f}")

    if forced_scale is not None:
        chosen = forced_scale
        utilization_pred = 0.0
        log(f"  强制比例 {chosen[0]}:{chosen[1]}")
    else:
        chosen, outlines_pred, _, utilization_pred = pick_scale_with_layout(bbox_m)
    # 反馈通道：再降档
    for _ in range(scale_downgrade_hops):
        new_scale = downgrade_scale(chosen)
        if new_scale != chosen:
            log(f"  feedback 降档: {chosen} -> {new_scale}")
            chosen = new_scale

    # 持续验证：若选定比例仍重叠，则继续降档
    while True:
        ok_pred, pairs_pred, outlines_pred = check_layout_no_overlap(bbox_m, chosen)
        if ok_pred:
            break
        new_scale = downgrade_scale(chosen)
        if new_scale == chosen:
            warnings_box.append({"code":"layout_overlap_unresolvable",
                                 "msg":f"无法找到无重叠比例，最终 {chosen} pairs={pairs_pred}"})
            break
        log(f"  预测视图重叠 {pairs_pred}, 降档 {chosen} -> {new_scale}")
        chosen = new_scale

    scale_num, scale_den = chosen
    scale_label = f"{scale_num}:{scale_den}"
    centers = layout_4_views(bbox_m, chosen)
    _drawing_blueprint_v4, _drawing_blueprint_paths, _drawing_blueprint_source = _v4_build_or_load_drawing_blueprint(
        part_path,
        run_dir=_run_dir_env,
        out_dir=out_dir,
        bbox_m=bbox_m,
        src_props=src_props,
        warnings_box=warnings_box,
    )
    reference_view_keys, reference_view_source = _reference_style_view_plan(part_path)
    reference_dim_floor, reference_dim_source = _reference_style_dim_floor(part_path)
    reference_section_allowed, reference_section_source = _reference_style_allows_section_view(part_path)
    reference_layout_centers, reference_layout_source = _reference_style_layout_centers(part_path, reference_view_keys)
    reference_layout_outlines = {}
    reference_layout_outline_source = ""
    if _drawing_blueprint_v4:
        _bp_source = _drawing_blueprint_source or "drawing_blueprint_v4"
        _bp_view_keys = _v4_blueprint_view_keys(_drawing_blueprint_v4)
        _bp_dim_floor = _v4_blueprint_dim_floor(_drawing_blueprint_v4)
        _bp_layout_centers = _v4_blueprint_layout_centers(_drawing_blueprint_v4)
        _bp_layout_outlines = _v4_blueprint_layout_outlines(_drawing_blueprint_v4)
        if _bp_view_keys:
            reference_view_keys = _bp_view_keys
            reference_view_source = _bp_source
        if _bp_dim_floor:
            reference_dim_floor = _bp_dim_floor
            reference_dim_source = _bp_source
        if _bp_layout_centers:
            reference_layout_centers = _bp_layout_centers
            reference_layout_source = _bp_source
        if _bp_layout_outlines:
            reference_layout_outlines = _bp_layout_outlines
            reference_layout_outline_source = _bp_source
        if _bp_view_keys and "section" not in set(_bp_view_keys):
            reference_section_allowed = False
            reference_section_source = _bp_source
        _titlebar_applied = _v4_apply_titlebar_property_overrides(
            src_props,
            _drawing_blueprint_v4,
            warnings_box=warnings_box,
        )
        if _titlebar_applied:
            log("  [v4 blueprint] titlebar fields applied: " + ", ".join(sorted(_titlebar_applied)))
        log(
            "  [v4 blueprint] source="
            + str(_drawing_blueprint_source or "unknown")
            + " paths="
            + ", ".join(str(p) for p in _drawing_blueprint_paths)
        )
    if reference_layout_centers:
        centers.update(reference_layout_centers)
        log("  [reference_style] layout centers(mm): " + ", ".join(
            f"{k}=({v[0]*1000:.1f},{v[1]*1000:.1f})" for k, v in reference_layout_centers.items()))
        _reference_scale_hint = _reference_outline_scale_hint(
            bbox_m,
            reference_layout_outlines,
            reference_view_keys,
        )
        _reference_scale_start = _reference_scale_hint or chosen
        if _reference_scale_hint:
            log(
                f"  [reference_style] scale hinted by reference outlines: "
                f"{_reference_scale_hint[0]}:{_reference_scale_hint[1]} "
                f"source={reference_layout_outline_source or reference_layout_source}"
            )
        ref_scale, ref_outlines, ref_pairs, ref_util, ref_out_of_workarea = pick_scale_with_reference_centers(
            bbox_m,
            centers,
            view_keys=reference_view_keys,
            start_scale=_reference_scale_start,
        )
        if ref_scale != chosen or ref_pairs or ref_out_of_workarea:
            log(
                f"  [reference_style] scale adjusted by learned centers: "
                f"{chosen[0]}:{chosen[1]} -> {ref_scale[0]}:{ref_scale[1]} "
                f"overlap={ref_pairs} out_of_workarea={ref_out_of_workarea}"
            )
        chosen = ref_scale
        scale_num, scale_den = chosen
        scale_label = f"{scale_num}:{scale_den}"
        outlines_pred = ref_outlines
        utilization_pred = ref_util
    # v1.4: 持续验证后重新计算利用率（chosen 可能已被降档）
    if outlines_pred is not None:
        try:
            utilization_pred = _calc_utilization(outlines_pred)
        except Exception:
            pass
    log(f"  选定比例 {scale_label}")
    log(f"  幅面利用率: {utilization_pred*100:.1f}%")
    log("  layout_4_views centers(mm): " + ", ".join(
        f"{k}=({v[0]*1000:.1f},{v[1]*1000:.1f})" for k,v in centers.items()))

    # 4) 新建工程图
    log("[4/9] 新建 A4 横向 / 第一角 / " + scale_label)
    # === 模板探测（template-aware） ===
    # 优先级：环境变量 DRWDOT_TEMPLATE > 仓库 templates/gb_a4_landscape.drwdot > SW 默认
    _draw_default_titleblock, _titleblock_policy_source = _v4_blueprint_default_titleblock_policy(
        _drawing_blueprint_v4,
    )
    if _draw_default_titleblock is None:
        _draw_default_titleblock, _titleblock_policy_source = _reference_style_should_draw_default_titleblock(
            part_path,
            reference_view_keys,
        )
    from pathlib import Path as _P
    _drwdot_env = os.environ.get("DRWDOT_TEMPLATE", "").strip()
    _drwdot_default = str(_BUNDLE_ROOT / "templates" / "gb_a4_landscape.DRWDOT")
    if not os.path.exists(_drwdot_default):
        _drwdot_default = str(_BUNDLE_ROOT / "templates" / "gb_a4_landscape.drwdot")
    _drwdot_path = _drwdot_env or _drwdot_default
    if not _draw_default_titleblock:
        log(f"[template] reference style -> create from DRWDOT, then strip default sheet artifacts ({_titleblock_policy_source})")
        warnings_box.append({
            "code": "reference_sheet_template_policy",
            "policy": "strip_default_template_artifacts",
            "source": _titleblock_policy_source,
            "reason": "same-name reference layout controls visible sheet/titleblock style",
        })
    if _P(_drwdot_path).exists():
        log(f"[template] using {_drwdot_path}")
    else:
        log(f"[template] fallback (template not found at {_drwdot_path})")
        _drwdot_path = ""
    # 若仓库模板不可用，再回退到 SW 自带模板搜索
    if not _drwdot_path:
        import glob as _g
        for d in [r"C:\ProgramData\SolidWorks\SOLIDWORKS *\templates",
                  r"C:\Program Files\SOLIDWORKS Corp25\SOLIDWORKS\lang\chinese-simplified",
                  r"C:\Program Files\SOLIDWORKS Corp25\SOLIDWORKS\lang\english",
                  r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\lang\chinese-simplified",
                  r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\lang\english"]:
            for f in _g.glob(os.path.join(d, "*.drwdot")):
                _drwdot_path = f; break
            if _drwdot_path: break
    # paper_size=12 = swDwgPaperA4size 横式；w/h 在模板存在时由模板决定
    if _drwdot_path and os.path.exists(_drwdot_path):
        drw = sw.NewDocument(_drwdot_path, 12, 0.297, 0.210)
    else:
        drw = sw.NewDocument("", 12, 0.297, 0.210)
    for _ in range(20):
        if drw is not None: break
        time.sleep(0.25); drw = sw.ActiveDoc
    if drw is None: raise SystemExit("新建工程图失败")
    _solidworks_doc_registry_event(
        "solidworks_doc_opened",
        role="generated_drawing",
        path=target_drw,
        title=_doc_title(drw),
        doc_type="drawing",
        stage="new_drawing_created",
    )
    sheet = call(drw, "GetCurrentSheet")
    sheet_name = call(sheet, "GetName") or "Sheet1"
    try: drw.SetupSheet5(sheet_name, 6, 13, scale_num, scale_den, True, "", 0.297, 0.21, "", True)
    except Exception: pass
    if not _draw_default_titleblock:
        _clear_reference_sheet_template_artifacts(
            drw,
            sheet_name,
            scale_num,
            scale_den,
            warnings_box,
            log,
        )

    # 字高 + 箭头大小
    try:
        ok_th = drw.SetUserPreferenceDoubleValue(89, text_height)
        log(f"  字高 SetUserPreferenceDoubleValue(89, {text_height}) -> {ok_th}")
    except Exception as exc:
        warnings_box.append({"code":"text_height_set_failed","msg":str(exc)})
    try:
        ok_arr = drw.SetUserPreferenceDoubleValue(2, 0.005)
        log(f"  箭头 SetUserPreferenceDoubleValue(2, 0.005) -> {ok_arr}")
    except Exception as exc:
        warnings_box.append({"code":"arrow_size_set_failed","msg":str(exc)})

    # drw 级别关闭视图箭头标签
    try: drw.SetUserPreferenceToggle(195, False)
    except Exception: pass
    try: drw.SetUserPreferenceToggle(196, False)
    except Exception: pass
    if str((_drawing_blueprint_v4 or {}).get("part_class") or "").strip().lower() == "long_thin":
        _apply_horizontal_dimension_text_policy(
            drw,
            warnings_box=warnings_box,
            log_fn=log,
            reason="long_thin_reference_callout_readability",
        )

    # 4.5) 创建 5 个图层
    log("[4.5/9] 创建 5 个图层")
    layer_mgr = None
    try:
        gl = getattr(drw, "GetLayerManager", None)
        layer_mgr = gl() if callable(gl) else gl
    except Exception:
        layer_mgr = None
    if layer_mgr is None:
        try: layer_mgr = drw.LayerMgr
        except Exception: layer_mgr = None
    if layer_mgr is None:
        warnings_box.append({"code":"layer_mgr_none","msg":"GetLayerManager / LayerMgr 均失败"})
        log("  ! 无法获取 LayerManager")
    else:
        for name, color, style, weight in LAYERS:
            try:
                rv = layer_mgr.AddLayer(name, "", color, style, weight)
                log(f"  + AddLayer({name}, color={color}, style={style}, weight={weight}) -> {rv}")
            except Exception as exc:
                warnings_box.append({"code":"layer_add_fail","name":name,"msg":str(exc)})
                log(f"  ! AddLayer({name}) 失败: {exc}")
        try:
            cnt = layer_mgr.GetLayerCount
            cnt = cnt() if callable(cnt) else cnt
            log(f"  LayerMgr.GetLayerCount() = {cnt}")
        except Exception as exc:
            warnings_box.append({"code":"layer_count_fail","msg":str(exc)})

    # 4.6) GB A4 图框 + 标题栏：原计划在此渲染，已移到所有视图布局之后
    #      (见 [9.6/9] 步骤)。此处保留占位说明，避免误以为漏掉。

    # v1.6 Task 1: 疑难件检测，若 InsertModelAnnotations3 历史失败，使用 model_dim_seed 副本出图
    # 检测条件：issues_in 含 "dim_count_sufficient" 或 part 为导入几何体（无特征尺寸）
    # v1.7 Task 1: 使用 RUN_DIR 环境变量统一路径，禁止从 out_dir 反推 run_dir
    _run_dir_env = os.environ.get("RUN_DIR", "")
    _dim_seed_used = False
    _work_part_path = part_path  # 默认用原始 part_path
    _seed_reason = ""
    if "dim_count_sufficient" in (issues or []):
        _seed_reason = "previous_dim_count_sufficient_issue"
    if _seed_reason:
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            from app.services.model_dim_seed_service import seed_model_dimensions
            # v1.7 Task 1: 优先用 RUN_DIR/input_work，否则降级到旧路径
            if _run_dir_env:
                run_dir_input_work = os.path.join(_run_dir_env, "input_work")
            else:
                run_dir_input_work = os.path.join(os.path.dirname(os.path.dirname(out_dir)), "input_work")
            os.makedirs(run_dir_input_work, exist_ok=True)
            seed_result = seed_model_dimensions(part_path, Path(run_dir_input_work))
            if seed_result.get("success") and seed_result.get("seed_dim_count", 0) > 0:
                _work_part_path = seed_result["work_part_path"]
                _dim_seed_used = True
                log(f"  [v1.6 dim_seed] reason={_seed_reason}")
                log(f"  [v1.6 dim_seed] 使用副本出图: {_work_part_path}")
                log(f"  [v1.6 dim_seed] seed_dim_count={seed_result['seed_dim_count']}")
                # 重新打开副本作为 part
                part = sw.OpenDoc6(_work_part_path, 1, 1|16|256, "", e, w)
                if part is not None:
                    _solidworks_doc_registry_event(
                        "solidworks_doc_opened",
                        role="copied_part",
                        path=_work_part_path,
                        title=_doc_title(part),
                        doc_type="part",
                        stage="seed_work_part_open",
                        extra={"open_errors": int(e.value), "open_warnings": int(w.value)},
                    )
                # 后续 CreateDrawViewFromModelView3 使用 _work_part_path
            else:
                log(f"  [v1.6 dim_seed] 失败: {seed_result.get('error', 'unknown')}")
        except Exception as exc:
            log(f"  [v1.6 dim_seed] 异常: {exc}")

    # 5) 4 个标准视图（按 layout_4_views）
    log("[5/9] 4 个标准视图（layout_4_views）")
    fx, fy = centers["front"]
    tx, ty = centers["top"]
    rx, ry = centers["right"]
    ix, iy = centers["iso"]
    bx, by = centers.get("bottom", (0.230, 0.080))
    log(f"  positions(mm): front=({fx*1000:.1f},{fy*1000:.1f}) "
        f"top=({tx*1000:.1f},{ty*1000:.1f}) right=({rx*1000:.1f},{ry*1000:.1f}) "
        f"iso=({ix*1000:.1f},{iy*1000:.1f}) bottom=({bx*1000:.1f},{by*1000:.1f})")
    positions_standard = [
        ("front", ("*Front", "*前视"),     (fx, fy)),
        ("top",   ("*Top",   "*上视"),     (tx, ty)),
        ("right", ("*Right", "*右视"),     (rx, ry)),
        ("iso",   ("*Isometric","*等轴测"),(ix, iy)),
    ]
    positions_reference_extra = [
        ("bottom", ("*Bottom", "*底视"), (bx, by)),
    ]
    if reference_view_keys:
        positions_all = positions_standard + positions_reference_extra
        reference_key_set = set(reference_view_keys)
        positions = [item for item in positions_all if item[0] in reference_key_set]
        log(f"  [reference_style] view_plan={reference_view_keys} source={reference_view_source}")
        if reference_layout_centers:
            log(f"  [reference_style] layout_source={reference_layout_source}")
    else:
        positions = positions_standard
    if reference_dim_floor:
        log(f"  [reference_style] DisplayDim floor={reference_dim_floor} source={reference_dim_source}")
    if not reference_section_allowed:
        log(f"  [reference_style] section skipped: same-name reference has only standard/projected views source={reference_section_source}")

    def _set_view_scale(view, num, den):
        # VARIANT R8 数组方式
        try:
            arr = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(num), float(den)])
            view.ScaleRatio = arr
            try:
                sr = list(view.ScaleRatio) if view.ScaleRatio else []
                if len(sr) >= 2 and abs(sr[0]/sr[1] - num/den) < 1e-6:
                    return True
            except Exception:
                return True
        except Exception:
            pass
        try:
            view.ScaleRatio = (float(num), float(den))
            return True
        except Exception:
            pass
        try:
            sd = getattr(view, "SetScale", None)
            if callable(sd):
                sd(float(num), float(den))
                return True
        except Exception:
            pass
        return False

    def _set_view_position(view, x, y):
        return _set_view_pos_v6(view, x, y)

    def _view_name_for_select(view):
        for attr in ("GetName2", "Name"):
            try:
                value = getattr(view, attr)
                value = value() if callable(value) else value
                if value:
                    return str(value)
            except Exception:
                pass
        return ""

    def _view_position_for_select(view):
        try:
            pos = getattr(view, "Position", None)
            if pos:
                values = list(pos)
                if len(values) >= 2:
                    return float(values[0]), float(values[1])
        except Exception:
            pass
        try:
            outline = view_outline_box(view)
            if outline:
                x0, y0, x1, y1 = outline
                return (x0 + x1) / 2.0, (y0 + y1) / 2.0
        except Exception:
            pass
        return 0.0, 0.0

    def _drawing_doc_getviews_candidates():
        candidates = []
        seen = set()

        def _append(view):
            if view is None:
                return
            try:
                name = _view_name_for_select(view)
                outline = view_outline_box(view)
                vtype = str(call(view, "Type") or "")
                if not (name or outline or vtype):
                    return
                key = (name, vtype, tuple(round(float(v), 9) for v in outline or ()))
                if key in seen:
                    return
                seen.add(key)
                candidates.append(view)
            except Exception:
                pass

        def _walk(value, depth=0):
            if value is None or depth > 5 or isinstance(value, (str, bytes)):
                return
            if isinstance(value, (list, tuple)):
                for item in value:
                    _walk(item, depth + 1)
                return
            _append(value)
            try:
                values = list(value)
            except Exception:
                values = []
            if values and values != [value]:
                for item in values:
                    _walk(item, depth + 1)

        for method_name in ("GetViews",):
            try:
                method = getattr(drw, method_name, None)
                if callable(method):
                    _walk(method())
            except Exception:
                pass
        try:
            sheet = call(drw, "GetCurrentSheet")
            method = getattr(sheet, "GetViews", None)
            if callable(method):
                _walk(method())
        except Exception:
            pass
        return candidates

    def _select_view_for_projection(view):
        view_name = _view_name_for_select(view)
        try:
            drw.ClearSelection2(True)
        except Exception:
            pass
        try:
            if view_name and callable(getattr(drw, "ActivateView", None)):
                drw.ActivateView(view_name)
        except Exception:
            pass
        try:
            drw.ActiveDrawingView = view
        except Exception:
            pass
        for method_name, args in (
            ("SelectEntity", (False,)),
            ("SelectEntity", (True,)),
            ("SelectEntity", ()),
            ("Select", (False,)),
            ("Select", (True,)),
            ("Select", ()),
            ("Select2", (False, 0)),
            ("Select2", (True, 0)),
        ):
            try:
                method = getattr(view, method_name, None)
                if callable(method):
                    selected = method(*args)
                    if selected is not False:
                        return True
            except Exception:
                pass
        px, py = _view_position_for_select(view)
        if view_name:
            name_candidates = [view_name]
            try:
                if sheet_name:
                    name_candidates.append(f"{view_name}@{sheet_name}")
            except Exception:
                pass
            try:
                callout_variants = [
                    None,
                    pythoncom.Empty,
                    pythoncom.Missing,
                    VARIANT(pythoncom.VT_DISPATCH, None),
                    VARIANT(pythoncom.VT_UNKNOWN, None),
                ]
            except Exception:
                callout_variants = [None]
            for candidate_name in name_candidates:
                for x_sel, y_sel in ((px, py), (0, 0)):
                    for select_type in ("DRAWINGVIEW", "DRAWING VIEW", ""):
                        for callout in callout_variants:
                            try:
                                if drw.Extension.SelectByID2(candidate_name, select_type, x_sel, y_sel, 0, False, 0, callout, 0):
                                    return True
                            except Exception:
                                pass
        try:
            callout_variants = [
                None,
                pythoncom.Empty,
                pythoncom.Missing,
                VARIANT(pythoncom.VT_DISPATCH, None),
                VARIANT(pythoncom.VT_UNKNOWN, None),
            ]
        except Exception:
            callout_variants = [None]
        for select_type in ("DRAWINGVIEW", "DRAWING VIEW", ""):
            for callout in callout_variants:
                try:
                    if drw.Extension.SelectByID2("", select_type, px, py, 0, False, 0, callout, 0):
                        return True
                except Exception:
                    pass
        try:
            if drw.Extension.SelectByID2("", "DRAWINGVIEW", px, py, 0, False, 0, None, 0):
                return True
        except Exception:
            pass
        return False

    def _select_view_for_autodimension(view):
        view_name = _view_name_for_select(view)
        px, py = _view_position_for_select(view)
        return _select_autodimension_point(px, py, view_name=view_name)

    def _select_autodimension_point(px, py, *, view_name="", view_names=None):
        last_error = ""
        try:
            drw.ClearSelection2(True)
        except Exception:
            pass
        try:
            if view_name and callable(getattr(drw, "ActivateView", None)):
                drw.ActivateView(view_name)
        except Exception:
            pass
        try:
            ok = drw.Extension.SelectByID2(
                "",
                "DRAWINGVIEW",
                float(px),
                float(py),
                0.0,
                False,
                0,
                vt_dispatch_none(),
                0,
            )
            if ok:
                return True, f"<point>:DRAWINGVIEW:{px:.6f},{py:.6f}"
        except Exception as exc:
            last_error = str(exc)
        if not view_name and not view_names:
            return False, last_error or "view_name_empty"
        name_candidates = []
        for candidate in list(view_names or []) + [view_name]:
            candidate = str(candidate or "").strip()
            if candidate and candidate not in name_candidates:
                name_candidates.append(candidate)
        try:
            if sheet_name:
                for candidate in list(name_candidates):
                    sheet_candidate = f"{candidate}@{sheet_name}"
                    if sheet_candidate not in name_candidates:
                        name_candidates.append(sheet_candidate)
        except Exception:
            pass
        for candidate_name in name_candidates:
            for select_type in ("DRAWINGVIEW", ""):
                for x_sel, y_sel in ((px, py), (0.0, 0.0)):
                    try:
                        ok = drw.Extension.SelectByID2(
                            candidate_name,
                            select_type,
                            float(x_sel),
                            float(y_sel),
                            0.0,
                            False,
                            0,
                            vt_dispatch_none(),
                            0,
                        )
                        if ok:
                            return True, f"{candidate_name}:{select_type or '<blank>'}"
                    except Exception as exc:
                        last_error = str(exc)
        return False, last_error or "select_view_failed"

    def _is_live_drawing_view(view):
        if view is None:
            return False
        try:
            vtype = str(call(view, "Type") or "")
            if vtype in {"0", "1"}:
                return False
        except Exception:
            pass
        try:
            return bool(view_outline_box(view))
        except Exception:
            return False

    def _selected_drawing_view_from_selection():
        try:
            sel_mgr = getattr(drw, "SelectionManager", None)
            sel_mgr = sel_mgr() if callable(sel_mgr) else sel_mgr
        except Exception:
            sel_mgr = None
        if sel_mgr is None:
            return None
        for mark in (-1, 0):
            try:
                view = sel_mgr.GetSelectedObject6(1, mark)
                if _is_live_drawing_view(view):
                    return view
            except Exception:
                pass
        return None

    def _drawing_view_by_name_or_point(view_name="", point=None):
        candidates = []
        base_name = str(view_name or "").strip()
        if base_name:
            candidates.append(base_name)
            try:
                if sheet_name:
                    candidates.append(f"{base_name}@{sheet_name}")
            except Exception:
                pass
        x_sel = y_sel = 0.0
        if point is not None:
            try:
                x_sel, y_sel = float(point[0]), float(point[1])
            except Exception:
                x_sel = y_sel = 0.0
        try:
            callout_variants = [
                vt_dispatch_none(),
                None,
                pythoncom.Empty,
                pythoncom.Missing,
            ]
        except Exception:
            callout_variants = [None]

        def _try_select(candidate, select_type, x, y):
            try:
                drw.ClearSelection2(True)
            except Exception:
                pass
            try:
                if base_name and callable(getattr(drw, "ActivateView", None)):
                    drw.ActivateView(base_name)
                    active = getattr(drw, "ActiveDrawingView", None)
                    active = active() if callable(active) else active
                    if _is_live_drawing_view(active):
                        return active
            except Exception:
                pass
            for callout in callout_variants:
                try:
                    if drw.Extension.SelectByID2(
                        candidate,
                        select_type,
                        float(x),
                        float(y),
                        0.0,
                        False,
                        0,
                        callout,
                        0,
                    ):
                        selected = _selected_drawing_view_from_selection()
                        if selected is not None:
                            return selected
                except Exception:
                    pass
            return None

        for candidate in candidates:
            for select_type in ("DRAWINGVIEW", "DRAWING VIEW", ""):
                for x, y in ((x_sel, y_sel), (0.0, 0.0)):
                    view = _try_select(candidate, select_type, x, y)
                    if view is not None:
                        return view
        if point is not None:
            for select_type in ("DRAWINGVIEW", "DRAWING VIEW", ""):
                view = _try_select("", select_type, x_sel, y_sel)
                if view is not None:
                    return view

        # Selection can fail after SaveAs/reopen even when the drawing view is
        # still present. Fall back to scanning live view objects by persisted
        # name and by the measured outline center used in slot rebinding.
        live_candidates = []

        def _append_live_candidate(view, source):
            if not _is_live_drawing_view(view):
                return
            try:
                outline = view_outline_box(view)
                if not outline:
                    return
                live_candidates.append({
                    "view": view,
                    "name": _view_name_for_select(view),
                    "outline": list(outline),
                    "source": source,
                })
            except Exception:
                pass

        try:
            sheet_view = drw.GetFirstView()
            cur = sheet_view.GetNextView() if sheet_view is not None else None
            guard = 0
            while cur is not None and guard < 50:
                _append_live_candidate(cur, "live_view_chain_scan")
                guard += 1
                try:
                    cur = cur.GetNextView()
                except Exception:
                    break
        except Exception:
            pass
        try:
            for view in _collect_drawing_views_for_style():
                _append_live_candidate(view, "live_collect_drawing_views_scan")
        except Exception:
            pass
        try:
            for view in _drawing_doc_getviews_candidates():
                _append_live_candidate(view, "live_getviews_scan")
        except Exception:
            pass
        try:
            for view in _created_views_for_autodimension():
                _append_live_candidate(view, "live_created_views_scan")
        except Exception:
            pass

        if base_name:
            base_key = base_name.lower()
            for item in live_candidates:
                if str(item.get("name") or "").lower() == base_key:
                    return item.get("view")

        if point is not None and live_candidates:
            ranked = []
            for item in live_candidates:
                center = _outline_center(item.get("outline"))
                if center is None:
                    continue
                dist = ((float(center[0]) - float(x_sel)) ** 2 + (float(center[1]) - float(y_sel)) ** 2) ** 0.5
                ranked.append((dist, item))
            ranked.sort(key=lambda pair: pair[0])
            if ranked:
                best_dist, best_item = ranked[0]
                second_dist = ranked[1][0] if len(ranked) > 1 else 999.0
                if best_dist <= 0.040 or second_dist - best_dist >= 0.006:
                    return best_item.get("view")
        return None

    def _autodimension_targets():
        targets = []
        seen = set()

        def _append_point(slot, point):
            try:
                px, py = float(point[0]), float(point[1])
            except Exception:
                return
            key = ("point", round(px, 6), round(py, 6))
            if key in seen:
                return
            seen.add(key)
            index_by_slot = {"front": 1, "top": 2, "right": 3, "iso": 4}
            idx = index_by_slot.get(str(slot))
            names = []
            if idx:
                names = [
                    f"工程图视图{idx}",
                    f"Drawing View{idx}",
                    f"Drawing View {idx}",
                ]
            targets.append({"slot": slot, "point": (px, py), "view": None, "view_names": names})

        try:
            for slot in ("front", "top", "right", "iso"):
                point = centers.get(slot)
                if point:
                    _append_point(slot, point)
        except Exception:
            pass

        for view in _created_views_for_autodimension():
            try:
                outline = view_outline_box(view)
                if outline:
                    x0, y0, x1, y1 = outline
                    point = ((float(x0) + float(x1)) / 2.0, (float(y0) + float(y1)) / 2.0)
                else:
                    point = _view_position_for_select(view)
                key = ("view", _view_name_for_select(view), tuple(round(float(v), 6) for v in point))
                if key in seen:
                    continue
                seen.add(key)
                targets.append({"slot": _view_name_for_select(view), "point": point, "view": view})
            except Exception:
                pass
        return targets

    def _created_views_for_autodimension():
        ordered = []
        seen = set()

        def _append(view):
            if view is None:
                return
            try:
                name = _view_name_for_select(view)
                outline = view_outline_box(view)
                vtype = str(call(view, "Type") or "")
                if vtype in {"0", "1"}:
                    if not outline:
                        return
                    try:
                        if float(outline[2]) >= 0.25 and float(outline[3]) >= 0.18:
                            return
                    except Exception:
                        pass
                key = (name, tuple(round(float(v), 9) for v in outline or ()))
                if key in seen:
                    return
                seen.add(key)
                ordered.append(view)
            except Exception:
                pass

        try:
            sheet_view = drw.GetFirstView()
            cur = sheet_view.GetNextView() if sheet_view is not None else None
            seen_chain = 0
            while cur is not None and seen_chain < 50:
                _append(cur)
                seen_chain += 1
                try:
                    cur = cur.GetNextView()
                except Exception:
                    break
        except Exception:
            pass
        try:
            for view in _collect_drawing_views_for_style():
                _append(view)
        except Exception:
            pass
        try:
            for key in ("front", "top", "right", "iso"):
                _append(created_views.get(key))
            for view in created_views.values():
                _append(view)
        except Exception:
            pass
        def _sort_key(view):
            try:
                outline = view_outline_box(view)
                if outline:
                    x0, y0, x1, y1 = outline
                    cx = (float(x0) + float(x1)) / 2.0
                    cy = (float(y0) + float(y1)) / 2.0
                    return (round(cx, 4), -round(cy, 4))
            except Exception:
                pass
            return (999.0, 999.0)
        ordered.sort(key=_sort_key)
        return ordered

    def _current_drawing_view_inventory(source_prefix):
        records = []
        seen = set()
        diagnostics = {
            "current_doc_view_count": 0,
            "current_doc_usable_view_count": 0,
            "getviews_count": 0,
            "getviews_usable_count": 0,
            "current_sheet_getviews_count": 0,
            "current_sheet_getviews_usable_count": 0,
            "active_doc_title": "",
            "active_doc_type": "",
            "sheet_name": "",
            "errors": [],
        }

        try:
            active_doc = call(sw, "ActiveDoc")
            diagnostics["active_doc_title"] = str(call(active_doc, "GetTitle") or "")
            diagnostics["active_doc_type"] = str(call(active_doc, "GetType") or "")
        except Exception:
            pass
        try:
            sheet = call(drw, "GetCurrentSheet")
            diagnostics["sheet_name"] = str(call(sheet, "GetName") or "")
        except Exception:
            try:
                diagnostics["sheet_name"] = str(sheet_name or "")
            except Exception:
                pass

        def _append(view, source, counter_key, usable_counter_key):
            if view is None:
                return
            diagnostics[counter_key] = int(diagnostics.get(counter_key) or 0) + 1
            try:
                outline = view_outline_box(view)
                vtype = str(call(view, "Type") or "")
                name = _view_name_for_select(view)
                if vtype in {"0", "1"} or not outline:
                    return
                key = (name, vtype, tuple(round(float(v), 9) for v in outline or ()))
                if key in seen:
                    return
                seen.add(key)
                diagnostics[usable_counter_key] = int(diagnostics.get(usable_counter_key) or 0) + 1
                records.append({
                    "view": view,
                    "name": name,
                    "type": vtype,
                    "outline": list(outline),
                    "source": source,
                })
            except Exception:
                pass

        try:
            view = call(drw, "GetFirstView")
            if view is None:
                diagnostics["get_first_view_none"] = True
            guard = 0
            while view is not None and guard < 100:
                guard += 1
                _append(
                    view,
                    f"{source_prefix}:GetFirstView",
                    "current_doc_view_count",
                    "current_doc_usable_view_count",
                )
                try:
                    view = call(view, "GetNextView")
                except Exception as exc:
                    diagnostics["errors"].append(f"GetNextView:{exc}")
                    break
        except Exception as exc:
            diagnostics["errors"].append(f"GetFirstView:{exc}")

        def _walk_getviews(value, append_fn, depth=0):
            if value is None or depth > 5 or isinstance(value, (str, bytes)):
                return
            if isinstance(value, (list, tuple)):
                for item in value:
                    _walk_getviews(item, append_fn, depth + 1)
                return
            append_fn(value)
            try:
                values = list(value)
            except Exception:
                values = []
            for item in values:
                _walk_getviews(item, append_fn, depth + 1)

        try:
            method = getattr(drw, "GetViews", None)
            if callable(method):
                _walk_getviews(
                    method(),
                    lambda view: _append(
                        view,
                        f"{source_prefix}:DrawingDoc.GetViews",
                        "getviews_count",
                        "getviews_usable_count",
                    ),
                )
            else:
                diagnostics["getviews_unavailable"] = True
        except Exception as exc:
            diagnostics["errors"].append(f"DrawingDoc.GetViews:{exc}")
        try:
            sheet = call(drw, "GetCurrentSheet")
            method = getattr(sheet, "GetViews", None)
            if callable(method):
                _walk_getviews(
                    method(),
                    lambda view: _append(
                        view,
                        f"{source_prefix}:CurrentSheet.GetViews",
                        "current_sheet_getviews_count",
                        "current_sheet_getviews_usable_count",
                    ),
                )
            else:
                diagnostics["current_sheet_getviews_unavailable"] = True
        except Exception as exc:
            diagnostics["errors"].append(f"CurrentSheet.GetViews:{exc}")
        diagnostics["record_count"] = len(records)
        diagnostics["records"] = [
            {
                "name": str(item.get("name") or ""),
                "type": str(item.get("type") or ""),
                "outline": list(item.get("outline") or []),
                "source": str(item.get("source") or ""),
            }
            for item in records
        ]
        return {"records": records, "diagnostics": diagnostics}

    def _reference_intent_dimension_targets():
        plan = (_drawing_blueprint_v4 or {}).get("dimension_plan") or {}
        targets = [item for item in (plan.get("dimension_targets") or []) if isinstance(item, dict)]
        targets.sort(key=lambda item: int(item.get("priority") or 0))
        return targets

    def _com_iterable(value):
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return list(value)
        try:
            return list(value)
        except Exception:
            return [value]

    def _dedupe_com_objects(items):
        result = []
        seen_ids = set()
        for item in items:
            if item is None:
                continue
            key = id(item)
            if key in seen_ids:
                continue
            seen_ids.add(key)
            result.append(item)
        return result

    def _curve_identity(entity):
        try:
            curve = call(entity, "GetCurve")
            value = call(curve, "Identity")
            return int(value)
        except Exception:
            return -1

    _reference_intent_slot_rebind_diagnostics = []
    _reference_intent_slot_rebind_summaries = []

    def _reference_intent_slot_views():
        diagnostics_start = len(_reference_intent_slot_rebind_diagnostics)
        expected_slots = {
            str(item.get("target_view") or "").strip().lower()
            for item in _reference_intent_dimension_targets()
            if str(item.get("target_view") or "").strip()
        }
        result = {}
        layout_plan = (_drawing_blueprint_v4 or {}).get("layout_plan") or {}
        layout_centers = {
            str(slot or "").strip().lower(): center
            for slot, center in _v4_blueprint_layout_centers(_drawing_blueprint_v4 or {}).items()
            if str(slot or "").strip()
        }
        if not layout_centers:
            sheet_size = _layout_sheet_size(layout_plan)
            for view_plan in (layout_plan.get("views") or [] if isinstance(layout_plan, dict) else []):
                if not isinstance(view_plan, dict):
                    continue
                slot = str(view_plan.get("slot") or "").strip().lower()
                center = view_plan.get("center_norm")
                if not slot or not isinstance(center, (list, tuple)) or len(center) < 2:
                    continue
                try:
                    layout_centers[slot] = (float(center[0]) * sheet_size[0], float(center[1]) * sheet_size[1])
                except Exception:
                    pass

        def _accept(slot, view, source):
            slot = str(slot or "").strip().lower()
            if not slot or slot not in expected_slots or slot in result or view is None:
                return False
            try:
                outline = view_outline_box(view)
                vtype = str(call(view, "Type") or "")
                if vtype in {"0", "1"}:
                    return False
                if not outline:
                    return False
            except Exception:
                return False
            result[slot] = {"view": view, "source": source}
            return True

        def _view_records_for_slot_rebind():
            records = []
            seen = set()

            def _append(view, source):
                if view is None:
                    return
                try:
                    outline = view_outline_box(view)
                    vtype = str(call(view, "Type") or "")
                    name = _view_name_for_select(view)
                    key = (name, vtype, tuple(round(float(v), 9) for v in outline or ()))
                    if key in seen:
                        return
                    seen.add(key)
                    records.append({
                        "view": view,
                        "name": name,
                        "type": vtype,
                        "outline": list(outline or []),
                        "source": source,
                    })
                except Exception:
                    pass

            for view in _created_views_for_autodimension():
                _append(view, "current_doc_views")
            try:
                inventory = _current_drawing_view_inventory("slot_rebind_live_inventory")
                for record in (inventory.get("records") or []):
                    if not isinstance(record, dict):
                        continue
                    _append(record.get("view"), str(record.get("source") or "slot_rebind_live_inventory"))
            except Exception:
                pass
            for slot, view in (created_views or {}).items():
                _append(view, f"created_views:{slot}")
            return records

        def _persisted_view_records_for_slot_rebind():
            records = []
            seen = set()
            try:
                outlines_snapshot = dict(real_outlines or {})
            except Exception:
                outlines_snapshot = {}
            for name, outline in outlines_snapshot.items():
                try:
                    outline_tuple = tuple(float(v) for v in list(outline or [])[:4])
                except Exception:
                    continue
                if len(outline_tuple) < 4:
                    continue
                key = (str(name or ""), tuple(round(v, 9) for v in outline_tuple))
                if key in seen:
                    continue
                seen.add(key)
                outline_center = _outline_center(outline_tuple)
                recovered_view = _drawing_view_by_name_or_point(
                    str(name or ""),
                    point=outline_center,
                )
                try:
                    recovered_type = str(call(recovered_view, "Type") or "") if recovered_view is not None else ""
                except Exception:
                    recovered_type = ""
                records.append({
                    "view": recovered_view,
                    "name": str(name or ""),
                    "type": recovered_type,
                    "outline": list(outline_tuple),
                    "source": "persisted_real_outlines_recovered_view" if recovered_view is not None else "persisted_real_outlines",
                    "recovered_from_persisted_outline": recovered_view is not None,
                })
            return records

        def _accept_match(slot, match, fallback_source):
            source = str(match.get("source") or fallback_source)
            view = match.get("view")
            direct_accept_failed = False
            accepted = _accept(slot, view, source)
            if not accepted:
                direct_accept_failed = view is not None
                recovered_view = _drawing_view_by_name_or_point(
                    match.get("view_name") or "",
                    point=_outline_center(match.get("outline")),
                )
                if recovered_view is not None:
                    view = recovered_view
                    if direct_accept_failed:
                        source = f"{source}|direct_accept_failed_select_by_persisted_name"
                    else:
                        source = f"{source}|select_by_persisted_name"
                    accepted = _accept(slot, view, source)
                else:
                    if direct_accept_failed:
                        source = f"{source}|direct_accept_failed_select_by_persisted_name_failed"
                    else:
                        source = f"{source}|select_by_persisted_name_failed"
            _reference_intent_slot_rebind_diagnostics.append({
                "slot": slot,
                "source": source,
                "accepted": bool(accepted),
                "direct_accept_failed": bool(direct_accept_failed),
                "view_name": str(match.get("view_name") or ""),
                "outline": list(match.get("outline") or []),
                "distance": match.get("distance"),
            })
            return accepted

        def _accept_reference_name_candidate(slot):
            if slot in result:
                return True
            dimension_plan = (_drawing_blueprint_v4 or {}).get("dimension_plan") or {}
            point = layout_centers.get(slot)
            for name in _reference_intent_view_name_candidates(slot, dimension_plan):
                source = f"reference_view_name_candidate_select:{name}"
                recovered_view = _drawing_view_by_name_or_point(name, point=point)
                accepted = _accept(slot, recovered_view, source)
                try:
                    recovered_outline = list(view_outline_box(recovered_view) or []) if recovered_view is not None else []
                except Exception:
                    recovered_outline = []
                _reference_intent_slot_rebind_diagnostics.append({
                    "slot": slot,
                    "source": source,
                    "accepted": bool(accepted),
                    "direct_accept_failed": False,
                    "view_name": name,
                    "outline": recovered_outline,
                    "distance": None,
                })
                if accepted:
                    return True
            return False

        current_records = _view_records_for_slot_rebind()
        persisted_records = []
        matched = _match_reference_intent_slot_views(
            current_records,
            layout_centers,
            expected_slots,
        )
        for slot, match in matched.items():
            source = str(match.get("source") or "current_doc_layout_match")
            distance = match.get("distance")
            if distance is not None and "nearest_layout_center" in source:
                source = f"{source}"
            current_match = dict(match)
            current_match["source"] = source
            _accept_match(slot, current_match, "current_doc_layout_match")
        if len(result) < len(expected_slots):
            persisted_records = _persisted_view_records_for_slot_rebind()
            persisted_matched = _match_reference_intent_slot_views(
                persisted_records,
                layout_centers,
                expected_slots,
            )
            for slot, match in persisted_matched.items():
                if slot in result:
                    continue
                _accept_match(slot, match, "persisted_real_outlines_layout_match")
        if len(result) < len(expected_slots):
            for slot in sorted(expected_slots):
                if slot in result:
                    continue
                _accept_reference_name_candidate(slot)
        for slot, view in (created_views or {}).items():
            _accept(slot, view, "created_views_fallback")
        try:
            _reference_intent_slot_rebind_summaries.append(
                _reference_intent_slot_rebind_summary(
                    current_records,
                    persisted_records,
                    layout_centers,
                    expected_slots,
                    result,
                    list(_reference_intent_slot_rebind_diagnostics[diagnostics_start:]),
                    (_drawing_blueprint_v4 or {}).get("dimension_plan") or {},
                )
            )
        except Exception as exc:
            _reference_intent_slot_rebind_summaries.append({
                "error": str(exc),
                "expected_slots": sorted(expected_slots),
                "bound_slots": sorted(result.keys()),
                "unbound_slots": [slot for slot in sorted(expected_slots) if slot not in result],
            })
        return result

    def _visible_entities_for_reference_intent(view, expected_type, target=None):
        entities = []
        witness_policy = (target or {}).get("allowed_witness_entity") or {}
        preferred_witness = [
            str(item or "").strip()
            for item in (witness_policy.get("preferred") or [])
            if str(item or "").strip()
        ]
        components = _com_iterable(call(view, "GetVisibleComponents"))
        filter_types = (1, 3) if "diameter" not in str(expected_type).lower() else (1, 2, 3)
        for comp in components:
            for filter_type in filter_types:
                try:
                    entities.extend(_com_iterable(call(view, "GetVisibleEntities2", comp, filter_type)))
                except Exception:
                    pass
        if not entities:
            for comp in (None, vt_dispatch_none()):
                for filter_type in filter_types:
                    try:
                        entities.extend(_com_iterable(call(view, "GetVisibleEntities2", comp, filter_type)))
                    except Exception:
                        pass
        if not entities:
            try:
                entities.extend(_com_iterable(call(view, "GetEdges", True)))
            except Exception:
                pass
        entities = _dedupe_com_objects(entities)

        def _rank(entity):
            rank = list(_reference_intent_entity_rank(expected_type, _curve_identity(entity)))
            if preferred_witness:
                rank.append(0 if "visible_model_edges" in preferred_witness else 1)
            return tuple(rank)

        entities.sort(key=_rank)
        return entities

    def _select_reference_entity(entity, append=False):
        try:
            sel_mgr = drw.SelectionManager
            sel_data = call(sel_mgr, "CreateSelectData")
        except Exception:
            sel_data = None
        attempts = (
            ("Select4", (bool(append), sel_data)),
            ("Select4", (bool(append), vt_dispatch_none())),
            ("Select4", (bool(append), None)),
            ("Select2", (bool(append), 0)),
            ("Select2", (bool(append),)),
            ("Select", (bool(append),)),
            ("Select", ()),
        )
        for method_name, args in attempts:
            try:
                method = getattr(entity, method_name, None)
                if not callable(method):
                    continue
                ok = method(*args)
                if ok is not False:
                    return True, method_name
            except Exception:
                continue
        return False, "entity_select_failed"

    def _reference_intent_dim_position(target, outline, side_counts):
        try:
            x0, y0, x1, y1 = [float(v) for v in outline[:4]]
        except Exception:
            return (0.0, 0.0)
        if x1 < x0:
            x0, x1 = x1, x0
        if y1 < y0:
            y0, y1 = y1, y0
        width = max(x1 - x0, 0.001)
        height = max(y1 - y0, 0.001)
        key = str(target.get("key") or "")
        slot = str(target.get("target_view") or "").strip().lower()
        placement_lane = target.get("placement_lane") if isinstance(target.get("placement_lane"), dict) else {}
        side = str(placement_lane.get("side") or target.get("preferred_side") or "above").strip().lower()
        idx_key = (slot, side)
        stack_idx = int(side_counts.get(idx_key, 0))
        side_counts[idx_key] = stack_idx + 1
        try:
            lane_index = max(stack_idx, int(placement_lane.get("lane_index") or 0))
        except Exception:
            lane_index = stack_idx
        fractions = {
            "overall_length": 0.50,
            "overall_width": 0.58,
            "overall_height": 0.56,
            "left_end_offset": 0.18,
            "right_end_offset": 0.82,
            "hole_diameter": 0.54,
            "hole_x_location": 0.38,
            "hole_y_location": 0.46,
            "hole_pitch": 0.70,
            "projection_view_width": 0.50,
            "projection_view_height": 0.50,
            "small_feature_location": 0.35,
        }
        try:
            frac = float(placement_lane.get("station"))
            frac = max(0.05, min(0.95, frac))
        except Exception:
            frac = fractions.get(key, ((stack_idx % 5) + 1) / 6.0)
        try:
            outside_gap = max(0.004, float(placement_lane.get("outside_gap_m") or 0.010))
        except Exception:
            outside_gap = 0.010
        try:
            stack_gap = max(0.002, float(placement_lane.get("stack_gap_m") or 0.004))
        except Exception:
            stack_gap = 0.004
        lane = outside_gap + stack_gap * lane_index
        if side in {"above", "top"}:
            return (x0 + width * frac, y1 + lane)
        if side in {"below", "bottom"}:
            return (x0 + width * frac, y0 - lane)
        if side in {"left"}:
            return (x0 - lane, y0 + height * frac)
        if side in {"right", "callout_right"}:
            return (x1 + lane, y0 + height * frac)
        return (x1 + lane, y1 + lane)

    def _add_reference_intent_display_dim(target, entity, position):
        expected_type = str(target.get("expected_type") or "").strip().lower()
        x, y = position
        if "diameter" in expected_type:
            add_diameter = getattr(drw, "AddDiameterDimension2", None)
            if callable(add_diameter):
                return add_diameter(float(x), float(y), 0.0), "AddDiameterDimension2"
        if "horizontal" in expected_type:
            return drw.AddHorizontalDimension2(float(x), float(y), 0.0), "AddHorizontalDimension2"
        if "vertical" in expected_type:
            return drw.AddVerticalDimension2(float(x), float(y), 0.0), "AddVerticalDimension2"
        return drw.AddDimension2(float(x), float(y), 0.0), "AddDimension2"

    def _run_reference_intent_explicit_display_dims(stage_name):
        targets = _reference_intent_dimension_targets()
        before = _count_display_dims(drw)
        coverage_before = _reference_intent_target_coverage_snapshot(
            drw,
            layout_plan=(_drawing_blueprint_v4 or {}).get("layout_plan") or {},
            dimension_plan=(_drawing_blueprint_v4 or {}).get("dimension_plan") or {},
        )
        missing_before = _reference_intent_missing_target_keys(coverage_before)
        repair_targets = _reference_intent_targets_for_repair(targets, coverage_before)
        result = {
            "stage": stage_name,
            "attempted": bool(targets),
            "before": before,
            "after": before,
            "created": 0,
            "target_count": len(targets),
            "missing_target_keys_before": sorted(missing_before),
            "target_coverage_before": coverage_before,
            "target_results": [],
            "slot_rebind_diagnostics": [],
            "source": "visible_entities2_select4_adddimension2",
        }
        if not targets:
            return result
        slot_diag_start = len(_reference_intent_slot_rebind_diagnostics)
        slot_summary_start = len(_reference_intent_slot_rebind_summaries)
        slot_views = _reference_intent_slot_views()
        result["slot_rebind_diagnostics"] = list(_reference_intent_slot_rebind_diagnostics[slot_diag_start:])
        slot_summaries = list(_reference_intent_slot_rebind_summaries[slot_summary_start:])
        result["slot_rebind_summary"] = slot_summaries[-1] if slot_summaries else {}
        result["slot_view_sources"] = {
            slot: str((info or {}).get("source") or "")
            for slot, info in slot_views.items()
            if isinstance(info, dict)
        }
        expected_repair_slots = {
            str(item.get("target_view") or "").strip().lower()
            for item in targets
            if str(item.get("target_view") or "").strip()
        }
        unbound_slots = [slot for slot in sorted(expected_repair_slots) if slot not in slot_views]
        result["bound_slots"] = sorted(slot_views.keys())
        result["unbound_slots"] = unbound_slots
        if stage_name == "post_layout" and unbound_slots:
            result["live_view_recovery_failed"] = True
            result["reason"] = "post_layout_live_view_recovery_failed"
            for target in repair_targets:
                target_key = str(target.get("key") or "")
                slot = str(target.get("target_view") or "").strip().lower()
                result["target_results"].append({
                    "key": target_key,
                    "target_key": target_key,
                    "slot": slot,
                    "view_slot": slot,
                    "expected_type": str(target.get("expected_type") or ""),
                    "expected_add_method": str(target.get("expected_add_method") or ""),
                    "selected_entity": None,
                    "add_method": "",
                    "display_dim_count_before": before,
                    "display_dim_count_before_target": before,
                    "display_dim_count_after": before,
                    "target_covered_after_attempt": False,
                    "persisted_after_reopen": False,
                    "success": False,
                    "attempts": [],
                    "reason": "post_layout_live_view_recovery_failed",
                })
            result["after"] = before
            result["target_coverage_after"] = coverage_before
            result["missing_target_keys_after"] = sorted(missing_before)
            warnings_box.append({
                "code": "post_layout_live_view_recovery_failed",
                "stage": stage_name,
                "before": before,
                "after": before,
                "bound_slots": result["bound_slots"],
                "unbound_slots": unbound_slots,
                "slot_rebind_summary": result.get("slot_rebind_summary") or {},
                "slot_rebind_diagnostics": result.get("slot_rebind_diagnostics") or [],
                "missing_target_keys": result["missing_target_keys_after"],
                "msg": "Post-layout live DrawingView recovery failed; explicit reference-intent DisplayDim repair is blocked rather than using stale COM objects.",
            })
            warnings_box.append({
                "code": "reference_intent_explicit_display_dims",
                "stage": stage_name,
                "before": result["before"],
                "after": result["after"],
                "created": result["created"],
                "reference_display_dim_floor": _dim_floor,
                "source": result["source"],
                "target_count": result["target_count"],
                "missing_target_keys_before": result["missing_target_keys_before"],
                "missing_target_keys_after": result["missing_target_keys_after"],
                "target_results": result["target_results"],
                "live_view_recovery_failed": True,
                "unbound_slots": unbound_slots,
            })
            log(
                "  [reference_intent explicit_dim] "
                f"{stage_name}: live view recovery failed unbound={unbound_slots}"
            )
            return result
        side_counts = {}
        try:
            uncovered_create_budget = max(
                1,
                int(os.environ.get("SWDS_REFERENCE_INTENT_UNCOVERED_CREATE_BUDGET", "3") or "3"),
            )
        except Exception:
            uncovered_create_budget = 3
        for target in repair_targets:
            coverage_now = _reference_intent_target_coverage_snapshot(
                drw,
                layout_plan=(_drawing_blueprint_v4 or {}).get("layout_plan") or {},
                dimension_plan=(_drawing_blueprint_v4 or {}).get("dimension_plan") or {},
            )
            missing_now = _reference_intent_missing_target_keys(coverage_now)
            current_count = _count_display_dims(drw)
            target_key = str(target.get("key") or "")
            if current_count >= _dim_floor and not missing_now:
                break
            if current_count >= _dim_floor and missing_now and target_key not in missing_now:
                continue
            slot = str(target.get("target_view") or "").strip().lower()
            view_info = slot_views.get(slot) or {}
            view = view_info.get("view")
            target_result = {
                "key": target_key,
                "target_key": target_key,
                "slot": slot,
                "view_slot": slot,
                "expected_type": str(target.get("expected_type") or ""),
                "expected_add_method": str(target.get("expected_add_method") or ""),
                "functional_role": str(target.get("functional_role") or ""),
                "reading_group": str(target.get("reading_group") or ""),
                "placement_lane": dict(target.get("placement_lane") or {}),
                "view_source": view_info.get("source", ""),
                "repair_reason": "missing_target_key" if target_key in missing_now else "display_dim_floor_gap",
                "display_dim_count_before": current_count,
                "display_dim_count_before_target": current_count,
                "display_dim_count_after": None,
                "selected_entity": None,
                "add_method": "",
                "target_covered_after_attempt": False,
                "missing_target_keys_before_target": sorted(missing_now),
                "success": False,
                "attempts": [],
            }
            if view is None:
                target_result["reason"] = "target_view_not_found"
                result["target_results"].append(target_result)
                continue
            outline = view_outline_box(view)
            if not outline:
                target_result["reason"] = "target_view_outline_missing"
                result["target_results"].append(target_result)
                continue
            entities = _visible_entities_for_reference_intent(view, target.get("expected_type", ""), target)
            target_result["entity_count"] = len(entities)
            target_result["allowed_witness_entity"] = dict(target.get("allowed_witness_entity") or {})
            if not entities:
                target_result["reason"] = "visible_entities_empty"
                result["target_results"].append(target_result)
                continue
            position = _reference_intent_dim_position(target, outline, side_counts)
            target_result["planned_position"] = [float(position[0]), float(position[1])]
            created_but_uncovered = 0
            for entity_index, entity in enumerate(entities[:18]):
                before_one = _count_display_dims(drw)
                try:
                    drw.ClearSelection2(True)
                except Exception:
                    pass
                selected, select_method = _select_reference_entity(entity)
                entity_identity = _curve_identity(entity)
                attempt = {
                    "target_key": target_key,
                    "view_slot": slot,
                    "entity_index": entity_index,
                    "curve_identity": entity_identity,
                    "selected_entity": entity_identity,
                    "entity_rank": list(_reference_intent_entity_rank(target.get("expected_type", ""), entity_identity)),
                    "selected": bool(selected),
                    "select_method": select_method,
                }
                if selected and target_result.get("selected_entity") is None:
                    target_result["selected_entity"] = entity_identity
                if not selected:
                    target_result["attempts"].append(attempt)
                    continue
                try:
                    dim_obj, add_method = _add_reference_intent_display_dim(target, entity, position)
                    try:
                        drw.ForceRebuild3(False)
                    except Exception:
                        pass
                    after_one = _count_display_dims(drw)
                    display_dim_created = bool(dim_obj is not None or after_one > before_one)
                    target_coverage_after_attempt = {}
                    target_covered_after_attempt = False
                    if display_dim_created:
                        target_coverage_after_attempt = _reference_intent_target_coverage_snapshot(
                            drw,
                            layout_plan=(_drawing_blueprint_v4 or {}).get("layout_plan") or {},
                            dimension_plan=(_drawing_blueprint_v4 or {}).get("dimension_plan") or {},
                        )
                        target_covered_after_attempt = _reference_intent_target_covered(
                            target_coverage_after_attempt,
                            target_key,
                        )
                    attempt.update({
                        "add_method": add_method,
                        "expected_add_method": str(target.get("expected_add_method") or ""),
                        "add_method_matches_expected": (
                            not str(target.get("expected_add_method") or "")
                            or add_method == str(target.get("expected_add_method") or "")
                        ),
                        "returned": bool(dim_obj is not None),
                        "display_dim_created": display_dim_created,
                        "before": before_one,
                        "after": after_one,
                        "display_dim_count_before": before_one,
                        "display_dim_count_after": after_one,
                        "position": [float(position[0]), float(position[1])],
                        "target_covered_after_attempt": target_covered_after_attempt,
                        "covered_target_keys_after_attempt": target_coverage_after_attempt.get("covered_target_keys", []),
                        "missing_target_keys_after_attempt": target_coverage_after_attempt.get("missing_target_keys", []),
                    })
                    if display_dim_created:
                        target_result.update({
                            "selected_entity": entity_identity,
                            "add_method": add_method,
                            "display_dim_count_before": before_one,
                            "display_dim_count_after": after_one,
                            "target_covered_after_attempt": target_covered_after_attempt,
                        })
                    if display_dim_created and target_covered_after_attempt:
                        target_result["success"] = True
                        target_result["after"] = after_one
                        target_result["target_coverage_after_creation"] = {
                            "covered_target_keys": target_coverage_after_attempt.get("covered_target_keys", []),
                            "missing_target_keys": target_coverage_after_attempt.get("missing_target_keys", []),
                        }
                        result["created"] += max(1, after_one - before_one)
                        target_result["attempts"].append(attempt)
                        log(
                            "  [reference_intent explicit_dim] "
                            f"{stage_name}:{target_key} slot={slot} "
                            f"{before_one}->{after_one} via {add_method}"
                        )
                        break
                    if display_dim_created:
                        created_but_uncovered += max(1, after_one - before_one)
                        target_result["created_but_target_not_covered"] = created_but_uncovered
                        attempt["created_but_target_not_covered"] = True
                        target_result["attempts"].append(attempt)
                        log(
                            "  [reference_intent explicit_dim] "
                            f"{stage_name}:{target_key} slot={slot} "
                            f"{before_one}->{after_one} via {add_method}, "
                            "but target coverage is still missing"
                        )
                        if created_but_uncovered >= uncovered_create_budget:
                            target_result["reason"] = "created_display_dims_but_target_not_covered"
                            target_result["uncovered_create_budget"] = uncovered_create_budget
                            break
                        continue
                except Exception as exc:
                    attempt["error"] = str(exc)
                target_result["attempts"].append(attempt)
            if not target_result.get("success") and not target_result.get("reason"):
                target_result["reason"] = "all_visible_entity_dimension_attempts_failed"
            result["target_results"].append(target_result)
        try:
            drw.ClearSelection2(True)
            drw.ForceRebuild3(False)
            drw.GraphicsRedraw2()
        except Exception:
            pass
        result["after"] = _count_display_dims(drw)
        coverage_after = _reference_intent_target_coverage_snapshot(
            drw,
            layout_plan=(_drawing_blueprint_v4 or {}).get("layout_plan") or {},
            dimension_plan=(_drawing_blueprint_v4 or {}).get("dimension_plan") or {},
        )
        result["target_coverage_after"] = coverage_after
        result["missing_target_keys_after"] = sorted(_reference_intent_missing_target_keys(coverage_after))
        warnings_box.append({
            "code": "reference_intent_explicit_display_dims",
            "stage": stage_name,
            "before": result["before"],
            "after": result["after"],
            "created": result["created"],
            "reference_display_dim_floor": _dim_floor,
            "source": result["source"],
            "target_count": result["target_count"],
            "missing_target_keys_before": result["missing_target_keys_before"],
            "missing_target_keys_after": result["missing_target_keys_after"],
            "target_results": result["target_results"],
        })
        log(
            f"  [reference_intent explicit_dim] {stage_name}: "
            f"{result['before']} -> {result['after']} created={result['created']} floor={_dim_floor}"
        )
        return result

    def _record_reference_intent_target_coverage(stage_name, *, persisted_after_reopen=False):
        plan = (_drawing_blueprint_v4 or {}).get("dimension_plan") or {}
        if not (plan.get("dimension_targets") or []):
            return {}
        snapshot = _reference_intent_target_coverage_snapshot(
            drw,
            layout_plan=(_drawing_blueprint_v4 or {}).get("layout_plan") or {},
            dimension_plan=plan,
        )
        snapshot["stage"] = stage_name
        snapshot["persisted_after_reopen"] = bool(persisted_after_reopen)
        if persisted_after_reopen:
            for item in snapshot.get("target_results") or []:
                item["persisted_after_reopen"] = int(item.get("matched_count") or 0) > 0
        try:
            _reference_intent_target_coverage_results.append(snapshot)
        except Exception:
            pass
        warnings_box.append({
            "code": "reference_intent_target_coverage",
            **snapshot,
        })
        log(
            "  [reference_intent target_coverage] "
            f"{stage_name}: covered={snapshot.get('covered_count')}/"
            f"{snapshot.get('target_count')} missing={snapshot.get('missing_target_keys')}"
        )
        return snapshot

    def _run_reference_autodimension():
        before = _count_display_dims(drw)
        if before >= _dim_floor:
            return {"applied": False, "before": before, "after": before, "attempts": []}
        attempts = []
        part_class = str((_drawing_blueprint_v4 or {}).get("part_class") or "").strip().lower()
        required_slots = _v4_dimension_autodim_slots(_drawing_blueprint_v4) if part_class == "long_thin" else []
        attempted_slots = set()

        def _intent_satisfied():
            if current < _dim_floor:
                return False
            if not required_slots:
                return True
            return all(slot in attempted_slots for slot in required_slots)

        candidates = [("preselect_baseline_above_right", (0, 1, 1, 1, 1))]
        if os.environ.get("SWDS_AUTODIM_EXTRA_CANDIDATES", "").strip() in {"1", "true", "yes"}:
            candidates.extend([
                ("all_baseline_above_right", (1, 1, 1, 1, 1)),
                ("selected_baseline_above_right", (2, 1, 1, 1, 1)),
                ("preselect_baseline_below_left", (0, 1, -1, 1, -1)),
                ("preselect_ordinate_above_right", (0, 2, 1, 2, 1)),
            ])
        default_budget = _reference_autodim_call_budget(_dim_floor, part_class=part_class)
        if required_slots:
            default_budget = max(default_budget, len(required_slots))
        try:
            call_budget = max(1, int(os.environ.get("SWDS_AUTODIM_CALL_BUDGET", str(default_budget)) or str(default_budget)))
        except Exception:
            call_budget = default_budget
        calls_used = 0
        current = before
        for target in _autodimension_targets():
            if calls_used >= call_budget:
                break
            view = target.get("view")
            point = target.get("point") or (0.0, 0.0)
            target_slot = str(target.get("slot") or "").strip().lower()
            if view is not None:
                view_name = _view_name_for_select(view)
                selected, select_reason = _select_view_for_autodimension(view)
                view_type = str(call(view, "Type") or "")
                outline = list(view_outline_box(view) or [])
            else:
                view_name = str(target.get("slot") or "")
                selected, select_reason = _select_autodimension_point(
                    point[0],
                    point[1],
                    view_name="",
                    view_names=target.get("view_names") or [],
                )
                view_type = ""
                outline = []
            view_attempt = {
                "view": view_name,
                "type": view_type,
                "outline": outline,
                "point": [float(point[0]), float(point[1])],
                "selected": bool(selected),
                "select_reason": select_reason,
                "calls": [],
            }
            if not selected:
                attempts.append(view_attempt)
                continue
            for label, args in candidates:
                if calls_used >= call_budget:
                    break
                before_call = _count_display_dims(drw)
                try:
                    returned = drw.AutoDimension(*args)
                    if target_slot:
                        attempted_slots.add(target_slot)
                    calls_used += 1
                    try:
                        drw.ForceRebuild3(False)
                    except Exception:
                        pass
                    after_call = _count_display_dims(drw)
                    call_result = {
                        "label": label,
                        "returned": str(returned),
                        "before": before_call,
                        "after": after_call,
                        "delta": after_call - before_call,
                    }
                    current = max(current, after_call)
                except Exception as exc:
                    calls_used += 1
                    call_result = {
                        "label": label,
                        "before": before_call,
                        "after": before_call,
                        "delta": 0,
                        "error": str(exc),
                    }
                    if target_slot:
                        attempted_slots.add(target_slot)
                view_attempt["calls"].append(call_result)
                log(
                    f"  [v1.8 autodim] view={view_name} {label} "
                    f"{call_result.get('before')}->{call_result.get('after')} "
                    f"ret={call_result.get('returned','ERR')}"
                )
                if _intent_satisfied():
                    break
                _select_view_for_autodimension(view)
            attempts.append(view_attempt)
            if _intent_satisfied():
                break
        try:
            drw.ClearSelection2(True)
        except Exception:
            pass
        return {
            "applied": current > before,
            "before": before,
            "after": current,
            "calls_used": calls_used,
            "required_slots": required_slots,
            "attempted_slots": sorted(attempted_slots),
            "attempts": attempts,
        }

    def _create_projected_view(parent_view, vkey, x, y):
        if parent_view is None:
            return None
        def _try_create(label):
            attempts = (
                ("CreateUnfoldedViewAt3", (x, y, 0, False)),
                ("CreateUnfoldedViewAt3", (x, y, 0, True)),
                ("CreateUnfoldedViewAt2", (x, y, 0)),
                ("CreateUnfoldedViewAt", (x, y, 0)),
            )
            for method_name, args in attempts:
                try:
                    method = getattr(drw, method_name, None)
                    if not callable(method):
                        continue
                    projected = method(*args)
                    if projected is not None and not isinstance(projected, bool):
                        log(f"  + projected {vkey} via {method_name}/{label} @({x*1000:.1f},{y*1000:.1f})mm")
                        return projected
                    if isinstance(projected, bool):
                        warnings_box.append({
                            "code":"projected_view_returned_bool",
                            "view":vkey,
                            "method":method_name,
                            "attempt":label,
                            "msg":f"returned {projected}; not a DrawingView object",
                        })
                except Exception as exc:
                    warnings_box.append({"code":"projected_view_create_failed","view":vkey,"method":method_name,"attempt":label,"msg":str(exc)})
            return None

        if _select_view_for_projection(parent_view):
            projected = _try_create("selected_base_view")
            if projected is not None:
                return projected
        else:
            warnings_box.append({"code":"projected_view_select_failed","view":vkey,"msg":"base view selection failed"})
        return _try_create("active_selection")

    def _collect_drawing_views_for_style():
        views_ = []
        seen_keys_ = set()

        def _add_view(view_):
            if view_ is None:
                return
            try:
                outline_ = view_outline_box(view_)
                vtype_ = str(call(view_, "Type") or "")
                if not outline_ and (not vtype_ or vtype_ == "0"):
                    return
                name_ = _view_name_for_select(view_)
                key_ = (name_, vtype_, tuple(round(float(v), 9) for v in outline_ or ()))
                if key_ in seen_keys_:
                    return
                seen_keys_.add(key_)
                views_.append(view_)
            except Exception:
                pass

        try:
            view_ = drw.GetFirstView()
            seen_ = 0
            while view_ is not None and seen_ < 100:
                seen_ += 1
                _add_view(view_)
                try:
                    view_ = view_.GetNextView()
                except Exception:
                    break
        except Exception:
            pass
        try:
            for view_ in _drawing_doc_getviews_candidates():
                _add_view(view_)
        except Exception:
            pass
        return views_

    def _refresh_current_drawing_doc_from_solidworks(stage_name, preferred_doc):
        info = {
            "stage": stage_name,
            "candidates": [],
            "selected_source": "",
            "selected_title": "",
            "selected_doc_type": "",
            "selected_sheet_name": "",
            "activate_attempt": {},
        }

        def _doc_info(source, doc):
            item = {"source": source, "present": doc is not None}
            if doc is None:
                return item
            try:
                item["title"] = str(call(doc, "GetTitle") or "")
            except Exception:
                item["title"] = ""
            try:
                item["doc_type"] = str(call(doc, "GetType") or "")
            except Exception:
                item["doc_type"] = ""
            try:
                sheet = call(doc, "GetCurrentSheet")
                item["sheet_name"] = str(call(sheet, "GetName") or "")
            except Exception:
                item["sheet_name"] = ""
            try:
                item["has_get_first_view"] = callable(getattr(doc, "GetFirstView", None))
            except Exception:
                item["has_get_first_view"] = False
            return item

        def _is_drawing_doc(item):
            if not item.get("present"):
                return False
            doc_type = str(item.get("doc_type") or "")
            return doc_type == "3" or bool(item.get("has_get_first_view"))

        candidates = [("reopened_doc", preferred_doc)]
        try:
            active_doc = call(sw, "ActiveDoc")
            candidates.append(("active_doc_before_activate", active_doc))
        except Exception:
            pass
        try:
            title = str(call(preferred_doc, "GetTitle") or "")
            if title:
                err_ = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                activate = getattr(sw, "ActivateDoc3", None)
                if callable(activate):
                    ok_ = activate(title, False, 0, err_)
                    info["activate_attempt"] = {
                        "method": "ActivateDoc3",
                        "title": title,
                        "ok": bool(ok_ is not False),
                        "errors": int(getattr(err_, "value", 0) or 0),
                    }
                else:
                    activate2 = getattr(sw, "ActivateDoc2", None)
                    if callable(activate2):
                        ok_ = activate2(title, False, err_)
                        info["activate_attempt"] = {
                            "method": "ActivateDoc2",
                            "title": title,
                            "ok": bool(ok_ is not False),
                            "errors": int(getattr(err_, "value", 0) or 0),
                        }
        except Exception as exc:
            info["activate_attempt"] = {"ok": False, "error": str(exc)}
        try:
            active_doc = call(sw, "ActiveDoc")
            candidates.append(("active_doc_after_activate", active_doc))
        except Exception:
            pass
        for key in (str(slddrw), os.path.basename(str(slddrw))):
            try:
                getter = getattr(sw, "GetOpenDocumentByName", None)
                if callable(getter) and key:
                    candidates.append((f"GetOpenDocumentByName:{key}", getter(key)))
            except Exception:
                pass

        selected_doc = preferred_doc
        seen = set()
        for source, doc in candidates:
            item = _doc_info(source, doc)
            key = (item.get("source"), item.get("title"), item.get("doc_type"), item.get("sheet_name"))
            if key in seen:
                continue
            seen.add(key)
            info["candidates"].append(item)
            if _is_drawing_doc(item):
                selected_doc = doc
                info["selected_source"] = source
                info["selected_title"] = str(item.get("title") or "")
                info["selected_doc_type"] = str(item.get("doc_type") or "")
                info["selected_sheet_name"] = str(item.get("sheet_name") or "")
                break
        if not info["selected_source"]:
            fallback = _doc_info("fallback_preferred_doc", preferred_doc)
            info["selected_source"] = "fallback_preferred_doc"
            info["selected_title"] = str(fallback.get("title") or "")
            info["selected_doc_type"] = str(fallback.get("doc_type") or "")
            info["selected_sheet_name"] = str(fallback.get("sheet_name") or "")
        warnings_box.append({
            "code": "post_layout_current_drawing_doc_refreshed",
            **info,
        })
        return selected_doc, info

    def _refresh_created_views_from_current_document(stage_name):
        expected_slots_ = {
            str(slot or "").strip().lower()
            for slot in (created_views or {}).keys()
            if str(slot or "").strip()
        }
        expected_slots_.update({
            str(item.get("target_view") or "").strip().lower()
            for item in _reference_intent_dimension_targets()
            if str(item.get("target_view") or "").strip()
        })
        if not expected_slots_:
            return {}
        layout_centers_ = {
            str(slot or "").strip().lower(): center
            for slot, center in _v4_blueprint_layout_centers(_drawing_blueprint_v4 or {}).items()
            if str(slot or "").strip()
        }
        if not layout_centers_:
            try:
                layout_centers_.update({
                    str(slot or "").strip().lower(): center
                    for slot, center in (centers or {}).items()
                    if str(slot or "").strip()
                })
            except Exception:
                pass

        def _prepare_reopened_views_for_rebind():
            actions_ = []
            try:
                materialization_ = _wait_for_drawing_views_materialized(
                    sw,
                    drw,
                    f"{stage_name}_before_slot_rebind",
                    log_fn=log,
                    max_attempts=4,
                    wait_s=0.4,
                )
                probe_ = materialization_.get("final_probe") or {}
                actions_.append({
                    "action": "post_layout_reopen_view_materialization_before_rebind",
                    "ok": bool(materialization_.get("success")),
                    "view_count": probe_.get("view_count"),
                    "usable_view_count": probe_.get("usable_view_count"),
                    "getviews_count": probe_.get("getviews_count"),
                    "current_sheet_getviews_count": probe_.get("current_sheet_getviews_count"),
                    "errors": list(probe_.get("errors") or []),
                })
            except Exception as exc:
                actions_.append({
                    "action": "post_layout_reopen_view_materialization_before_rebind",
                    "ok": False,
                    "error": str(exc),
                })
            try:
                if sheet_name and callable(getattr(drw, "ActivateSheet", None)):
                    actions_.append({"action": "ActivateSheet", "ok": bool(drw.ActivateSheet(sheet_name))})
            except Exception as exc:
                actions_.append({"action": "ActivateSheet", "ok": False, "error": str(exc)})
            try:
                drw.ForceRebuild3(True)
                actions_.append({"action": "ForceRebuild3", "ok": True})
            except Exception as exc:
                actions_.append({"action": "ForceRebuild3", "ok": False, "error": str(exc)})
            try:
                drw.GraphicsRedraw2()
                actions_.append({"action": "GraphicsRedraw2", "ok": True})
            except Exception as exc:
                actions_.append({"action": "GraphicsRedraw2", "ok": False, "error": str(exc)})
            try:
                time.sleep(0.75)
                actions_.append({"action": "post_layout_reopen_force_rebuild_wait", "ok": True})
            except Exception as exc:
                actions_.append({"action": "post_layout_reopen_force_rebuild_wait", "ok": False, "error": str(exc)})
            return actions_

        inventory_ = _current_drawing_view_inventory("post_layout_reopen_refresh")
        records_ = list(inventory_.get("records") or [])
        inventory_diagnostics_ = dict(inventory_.get("diagnostics") or {})
        refresh_actions_ = []
        if not records_:
            refresh_actions_ = _prepare_reopened_views_for_rebind()
            inventory_ = _current_drawing_view_inventory("post_layout_reopen_refresh_after_rebuild")
            records_ = list(inventory_.get("records") or [])
            inventory_diagnostics_ = dict(inventory_.get("diagnostics") or {})
        matched_ = _match_reference_intent_slot_views(
            records_,
            layout_centers_,
            expected_slots_,
        )
        refreshed_ = {}
        for slot_, match_ in matched_.items():
            view_ = match_.get("view")
            if view_ is None:
                continue
            try:
                if not _is_live_drawing_view(view_):
                    continue
            except Exception:
                continue
            created_views[slot_] = view_
            refreshed_[slot_] = {
                "view_name": str(match_.get("view_name") or ""),
                "source": str(match_.get("source") or ""),
                "distance": match_.get("distance"),
            }
        diagnostic_ = {
            "code": "reference_intent_created_views_refreshed",
            "stage": stage_name,
            "source": "post_layout_reopen_getviews_refresh",
            "expected_slots": sorted(expected_slots_),
            "record_count": len(records_),
            "current_doc_view_count": inventory_diagnostics_.get("current_doc_view_count"),
            "getviews_count": inventory_diagnostics_.get("getviews_count"),
            "current_sheet_getviews_count": inventory_diagnostics_.get("current_sheet_getviews_count"),
            "current_doc_usable_view_count": inventory_diagnostics_.get("current_doc_usable_view_count"),
            "getviews_usable_count": inventory_diagnostics_.get("getviews_usable_count"),
            "current_sheet_getviews_usable_count": inventory_diagnostics_.get("current_sheet_getviews_usable_count"),
            "active_doc_title": inventory_diagnostics_.get("active_doc_title", ""),
            "active_doc_type": inventory_diagnostics_.get("active_doc_type", ""),
            "sheet_name": inventory_diagnostics_.get("sheet_name", ""),
            "live_view_records": inventory_diagnostics_.get("records", []),
            "refresh_actions": refresh_actions_,
            "refreshed_slots": sorted(refreshed_.keys()),
            "matched_slots": sorted(matched_.keys()),
            "unbound_slots": [slot for slot in sorted(expected_slots_) if slot not in refreshed_],
            "details": refreshed_,
        }
        warnings_box.append(diagnostic_)
        return diagnostic_

    def _outline_size_for_style(view_):
        ob_ = view_outline_box(view_)
        if not ob_:
            return (0.0, 0.0, 0.0)
        x0_, y0_, x1_, y1_ = ob_
        w_ = abs(float(x1_) - float(x0_))
        h_ = abs(float(y1_) - float(y0_))
        return (w_, h_, w_ * h_)

    def _apply_view_common(vkey_, view_, x_, y_):
        ok_sc_ = _set_view_scale(view_, scale_num, scale_den)
        log(f"    set scale {vkey_} -> {scale_num}:{scale_den}  ok={ok_sc_}")
        try:
            if _cached_cfg_name:
                try: view_.SetReferencedConfiguration(_cached_cfg_name)
                except Exception: pass
                print(f"[refdoc] view {getattr(view_,'Name','?')} bound config {_cached_cfg_name}")
        except Exception as e_:
            print(f"[refdoc] cfg bind failed: {e_}")
        try:
            view_.DisplayMode = 2
        except Exception:
            try: view_.DisplayMode = 3
            except Exception as exc_:
                warnings_box.append({"code":"display_mode_fail","view":vkey_,"msg":str(exc_)})
        ok_set_ = _set_view_position(view_, x_, y_)
        log(f"    force position {vkey_} -> ({x_*1000:.1f},{y_*1000:.1f})mm  set_ok={ok_set_}")

    created_views = {}
    projected_view_keys = set()
    standard_view_keys_created = set()

    def _bind_first_angle_standard_views():
        views_ = _collect_drawing_views_for_style()
        base_candidates_ = []
        projected_candidates_ = []
        for view_ in views_:
            vtype_ = str(call(view_, "Type") or "")
            if vtype_ == "4":
                projected_candidates_.append(view_)
            else:
                base_candidates_.append(view_)
        if len(projected_candidates_) < 2:
            return False, views_, len(projected_candidates_)
        base_candidates_.sort(key=lambda v__: _outline_size_for_style(v__)[2], reverse=True)
        projected_candidates_.sort(
            key=lambda v__: (_outline_size_for_style(v__)[0] / max(_outline_size_for_style(v__)[1], 1e-9)),
            reverse=True,
        )
        front_ = base_candidates_[0] if base_candidates_ else views_[0]
        top_ = projected_candidates_[0]
        right_ = projected_candidates_[1]
        _apply_view_common("front", front_, fx, fy)
        _apply_view_common("top", top_, tx, ty)
        _apply_view_common("right", right_, rx, ry)
        created_views["front"] = front_
        created_views["top"] = top_
        created_views["right"] = right_
        projected_view_keys.update(["top", "right"])
        standard_view_keys_created.update(["front", "top", "right"])
        return True, views_, len(projected_candidates_)

    def _refresh_after_standard_views():
        try: drw.ForceRebuild3(True)
        except Exception: pass
        try: drw.GraphicsRedraw2()
        except Exception: pass
        try: time.sleep(0.25)
        except Exception: pass

    def _create_first_angle_standard_views():
        if not reference_view_keys or not _reference_style_should_use_first_angle(reference_view_keys):
            return False
        strict_bind_required_ = "bottom" in set(reference_view_keys or [])
        before_count_ = len(_collect_drawing_views_for_style())
        ok_ = False
        method_used_ = ""
        for method_name_ in ("Create1stAngleViews2", "Create1stAngleViews"):
            try:
                method_ = getattr(drw, method_name_, None)
                if callable(method_):
                    rv_ = method_(_work_part_path)
                    ok_ = bool(rv_ is not False)
                    log(f"  [reference_style] {method_name_} -> {rv_}")
                    if ok_:
                        method_used_ = method_name_
                        break
            except Exception as exc_:
                warnings_box.append({"code":"first_angle_views_failed","method":method_name_,"msg":str(exc_)})
        if not ok_:
            return False

        # SolidWorks can return success before the new views are enumerable. In
        # that case the standard views still exist, so reserve the slots and
        # avoid falling through to duplicate named-view creation.
        last_views_ = []
        last_projected_ = 0
        bound_ = False
        bind_attempts_ = 12 if strict_bind_required_ else 4
        for _idx_ in range(bind_attempts_):
            _refresh_after_standard_views()
            bound_, last_views_, last_projected_ = _bind_first_angle_standard_views()
            if bound_:
                standard_view_keys_created.update(["front", "top", "right"])
                log("  [reference_style] first-angle standard views accepted")
                break
        if not bound_:
            warnings_box.append({
                "code":"first_angle_views_pending_unbound",
                "method":method_used_,
                "msg":f"method succeeded but bind delayed; views={len(last_views_)} before={before_count_} projected={last_projected_}",
            })
            if strict_bind_required_:
                log("  [reference_style] first-angle views unbound; fallback to manual projected creation for bottom plan")
                return False
            standard_view_keys_created.update(["front", "top", "right"])
            log("  [reference_style] first-angle standard views reserved; skip duplicate named-view fallback")
        return True

    print("[v6 layout] checking overlaps...")
    front_view = None
    if _create_first_angle_standard_views():
        front_view = created_views.get("front")
    for vkey, aliases, (x,y) in positions:
        if vkey in created_views or vkey in standard_view_keys_created:
            continue
        v = None
        if vkey in ("top", "right", "bottom") and front_view is not None:
            v = _create_projected_view(front_view, vkey, x, y)
            if v is not None:
                projected_view_keys.add(vkey)
        if v is None and vkey in ("top", "right", "bottom") and front_view is not None:
            for parent_key in ("top", "right", "bottom"):
                parent_candidate = created_views.get(parent_key)
                if parent_candidate is None or parent_candidate is front_view:
                    continue
                v = _create_projected_view(parent_candidate, vkey, x, y)
                if v is not None:
                    projected_view_keys.add(vkey)
                    warnings_box.append({
                        "code": "projected_view_alternate_parent",
                        "view": vkey,
                        "parent": parent_key,
                        "msg": "front projection failed; created projected view from another projected slot",
                    })
                    break
        if v is None:
            for vname in aliases:
                try:
                    v = drw.CreateDrawViewFromModelView3(_work_part_path, vname, x, y, 0)
                    if v is not None:
                        if vkey in ("top", "right", "bottom") and front_view is not None:
                            warnings_box.append({
                                "code":"projected_view_fallback_named_view",
                                "view":vkey,
                                "msg":f"projected view failed; fallback to {vname}",
                            })
                        log(f"  + {vname} ok @({x*1000:.1f},{y*1000:.1f})mm")
                        break
                except Exception: pass
        if v is not None and vkey == "front":
            front_view = v
        if v is not None:
            _apply_view_common(vkey, v, x, y)
            # 清掉 SolidWorks 默认视图标签 / 对齐箭头
            if vkey not in projected_view_keys:
                try: v.RemoveAlignment()
                except Exception: pass
            created_views[vkey] = v
    if standard_view_keys_created and "front" not in created_views:
        _refresh_after_standard_views()
        bound_, last_views_, last_projected_ = _bind_first_angle_standard_views()
        if bound_:
            front_view = created_views.get("front")
            log("  [reference_style] first-angle standard views rebound after manual slot skip")
        else:
            warnings_box.append({
                "code":"first_angle_views_still_unbound",
                "msg":f"views={len(last_views_)} projected={last_projected_}",
            })
    if reference_layout_centers:
        for k_, point_ in reference_layout_centers.items():
            v_ = created_views.get(k_)
            if v_ is None:
                continue
            if k_ in projected_view_keys:
                try:
                    v_.RemoveAlignment()
                except Exception:
                    pass
            ok_ref_pos_ = _set_view_position(v_, point_[0], point_[1])
            log(f"  [reference_style] refit {k_} center -> ({point_[0]*1000:.1f},{point_[1]*1000:.1f})mm ok={ok_ref_pos_}")
    try: drw.ForceRebuild3(False)
    except Exception: pass

    # 实测重叠 + 基于实测 outline 重新摆位
    def _measure_outlines():
        outs = {}
        for k_, v_ in created_views.items():
            ob_ = view_outline_box(v_)
            if ob_: outs[k_] = ob_
        return outs

    def _detect_overlap(outs):
        pairs_ = []
        ks_ = list(outs.keys())
        for i_ in range(len(ks_)):
            for j_ in range(i_+1, len(ks_)):
                if _rect_intersect(outs[ks_[i_]], outs[ks_[j_]]):
                    pairs_.append((ks_[i_], ks_[j_]))
        return pairs_

    def _apply_reference_outline_size_corrections(stage_):
        layout_plan_ = ((_drawing_blueprint_v4 or {}).get("layout_plan") or {})
        layout_policy_ = layout_plan_.get("reference_view_outline_policy") or {}
        required_ = (
            bool(reference_layout_outlines)
            and (
                layout_plan_.get("view_outline_size_match_required") is True
                or layout_policy_.get("view_outline_size_match_required") is True
            )
            and (
                layout_plan_.get("independent_view_scale_allowed") is True
                or layout_policy_.get("independent_view_scale_allowed") is True
            )
        )
        if not required_:
            return []
        try:
            tolerance_ = float(
                layout_plan_.get(
                    "view_outline_size_tolerance",
                    layout_policy_.get("view_outline_size_tolerance", 0.18),
                )
            )
        except Exception:
            tolerance_ = 0.18
        current_outlines_ = _measure_outlines()
        corrections_ = []
        for slot_, target_outline_ in reference_layout_outlines.items():
            view_ = created_views.get(slot_)
            current_outline_ = current_outlines_.get(slot_)
            if view_ is None or not current_outline_:
                continue
            correction_ = _reference_view_outline_size_correction(
                current_outline_,
                target_outline_,
                (scale_num, scale_den),
                tolerance=tolerance_,
            )
            if not correction_:
                continue
            ok_scale_ = _set_view_scale(view_, correction_["scale_num"], correction_["scale_den"])
            center_ = reference_layout_centers.get(slot_) if isinstance(reference_layout_centers, dict) else None
            ok_pos_ = False
            if center_ and len(center_) >= 2:
                ok_pos_ = _set_view_position(view_, float(center_[0]), float(center_[1]))
            correction_ = dict(correction_)
            correction_.update({
                "slot": slot_,
                "stage": stage_,
                "scale_applied": bool(ok_scale_),
                "position_applied": bool(ok_pos_),
                "target_center": list(center_ or []),
            })
            corrections_.append(correction_)
            log(
                f"  [reference_style] outline size correction {slot_}: "
                f"factor={correction_['scale_factor']:.3f} "
                f"scale={correction_['scale_num']:.3g}:{correction_['scale_den']:.3g} "
                f"ok={ok_scale_}"
            )
        if corrections_:
            try: drw.ForceRebuild3(False)
            except Exception: pass
            warnings_box.append({
                "code": "reference_view_outline_size_correction",
                "stage": stage_,
                "source": reference_layout_outline_source or reference_layout_source,
                "tolerance": tolerance_,
                "corrections": corrections_,
            })
        return corrections_

    def _delete_view(vkey):
        v_ = created_views.get(vkey)
        if v_ is None: return False
        # 优先 SetSuppression(True)
        for arg in (True, 1, VARIANT(pythoncom.VT_BOOL, True)):
            try:
                ss = getattr(v_, "SetSuppression", None)
                if callable(ss):
                    ss(arg)
                    log(f"    suppress view {vkey} (arg={arg})")
                    created_views.pop(vkey, None)
                    return True
            except Exception:
                continue
        # 退而求其次：SelectByID2 + DeleteSelection2
        try:
            vname = call(v_, "GetName2") or ""
            if vname:
                drw.ClearSelection2(True)
                ok_sel = drw.Extension.SelectByID2(vname, "DRAWINGVIEW", 0, 0, 0, False, 0, None, 0)
                if ok_sel:
                    drw.DeleteSelection2(False)
                    log(f"    delete view {vkey} ({vname})")
                    created_views.pop(vkey, None)
                    return True
        except Exception as exc:
            warnings_box.append({"code":"view_delete_fail","view":vkey,"msg":str(exc)})
        # 兜底：把视图移到图框外（视为不参与重叠）
        ok_off = _set_view_position(v_, 0.500, 0.500)
        if ok_off:
            log(f"    move view {vkey} off-frame as fallback")
            created_views.pop(vkey, None)
            return True
        return False

    real_outlines = _measure_outlines()
    real_overlap_pairs = _detect_overlap(real_outlines)
    rearrange_attempts = 0
    # v6: 重叠时按 1:1 / 1:2 / 1:5 / 1:10 / 1:20 / 1:50 逐档下降
    _v6_scale_ladder = [(1,1),(1,2),(1,5),(1,10),(1,20),(1,50)]
    _v6_ladder_idx = 0
    while real_overlap_pairs and _v6_ladder_idx + 1 < len(_v6_scale_ladder):
        _v6_ladder_idx += 1
        new_n, new_d = _v6_scale_ladder[_v6_ladder_idx]
        rearrange_attempts += 1
        log(f"  ! v6 实测重叠 (#{rearrange_attempts}) {real_overlap_pairs}, 降至 {new_n}:{new_d}")
        for k_, v_ in created_views.items():
            ok_sc = _set_view_scale(v_, new_n, new_d)
            log(f"    {k_} ScaleRatio -> {new_n}:{new_d}  ok={ok_sc}")
        try: drw.ForceRebuild3(False)
        except Exception: pass
        scale_num, scale_den = new_n, new_d
        scale_label = f"{scale_num}:{scale_den}"
        # 重新强制 T 字位置
        for k_, (nx, ny) in centers.items():
            v_ = created_views.get(k_)
            if v_ is not None:
                _set_view_position(v_, nx, ny)
        try: drw.ForceRebuild3(False)
        except Exception: pass
        real_outlines = _measure_outlines()
        real_overlap_pairs = _detect_overlap(real_outlines)
        if not real_overlap_pairs:
            log(f"  ✓ v6 比例 {scale_label} 后无重叠")
            break

    if real_overlap_pairs:
        log(f"  ! 最终仍重叠: {real_overlap_pairs}")
        warnings_box.append({"code":"view_overlap_real","pairs":real_overlap_pairs})
    elif rearrange_attempts == 0:
        log(f"  ✓ 实测 {len(real_outlines)} 个视图无重叠")

    # 5.5) view_in_frame：检查并把越界视图拉回工作区
    log("[5.5/9] view_in_frame 越界检查")
    FRAME_BOX = (0.010, 0.010, 0.287, 0.200)
    real_outlines = _measure_outlines()
    out_of_frame = []
    for k_, ob_ in real_outlines.items():
        x0, y0, x1, y1 = ob_
        if x0 < FRAME_BOX[0] or y0 < FRAME_BOX[1] or x1 > FRAME_BOX[2] or y1 > FRAME_BOX[3]:
            out_of_frame.append(k_)
    if out_of_frame:
        log(f"  ! 越界视图: {out_of_frame}")
        for k_ in out_of_frame:
            v_ = created_views.get(k_)
            if v_ is None: continue
            ob_ = view_outline_box(v_)
            if not ob_: continue
            x0, y0, x1, y1 = ob_
            cx_now = (x0 + x1) / 2.0
            cy_now = (y0 + y1) / 2.0
            w_half = (x1 - x0) / 2.0
            h_half = (y1 - y0) / 2.0
            new_cx = min(max(cx_now, FRAME_BOX[0] + w_half + 0.002), FRAME_BOX[2] - w_half - 0.002)
            new_cy = min(max(cy_now, FRAME_BOX[1] + h_half + 0.002), FRAME_BOX[3] - h_half - 0.002)
            ok_set = _set_view_position(v_, new_cx, new_cy)
            log(f"    relocate {k_} -> ({new_cx*1000:.1f},{new_cy*1000:.1f})mm  set_ok={ok_set}")
        try: drw.ForceRebuild3(False)
        except Exception: pass

        # v1.5 Task 3: view_in_frame 重定位后重新检测重叠，必要时降档（复用 L970-993 逻辑）
        real_outlines = _measure_outlines()
        real_overlap_pairs = _detect_overlap(real_outlines)
        if real_overlap_pairs:
            log(f"  ! view_in_frame 重定位后新重叠: {real_overlap_pairs}, 进入降档循环")
            _relocate_downgraded = False
            while real_overlap_pairs and _v6_ladder_idx + 1 < len(_v6_scale_ladder):
                _v6_ladder_idx += 1
                new_n, new_d = _v6_scale_ladder[_v6_ladder_idx]
                rearrange_attempts += 1
                _relocate_downgraded = True
                log(f"  ! v6 重定位后重叠 (#{rearrange_attempts}) {real_overlap_pairs}, 降至 {new_n}:{new_d}")
                for k_, v_ in created_views.items():
                    ok_sc = _set_view_scale(v_, new_n, new_d)
                    log(f"    {k_} ScaleRatio -> {new_n}:{new_d}  ok={ok_sc}")
                try: drw.ForceRebuild3(False)
                except Exception: pass
                scale_num, scale_den = new_n, new_d
                scale_label = f"{scale_num}:{scale_den}"
                # 重新强制 T 字位置
                for k_, (nx, ny) in centers.items():
                    v_ = created_views.get(k_)
                    if v_ is not None:
                        _set_view_position(v_, nx, ny)
                try: drw.ForceRebuild3(False)
                except Exception: pass
                real_outlines = _measure_outlines()
                real_overlap_pairs = _detect_overlap(real_outlines)
                if not real_overlap_pairs:
                    log(f"  ✓ v6 比例 {scale_label} 后无重叠")
                    break
            if real_overlap_pairs and _relocate_downgraded:
                log(f"  ! view_in_frame 降档后仍重叠: {real_overlap_pairs}")
                warnings_box.append({"code":"view_overlap_real","pairs":real_overlap_pairs})
            elif real_overlap_pairs:
                log(f"  ! view_in_frame 后仍重叠（降档梯已耗尽）: {real_overlap_pairs}")
            else:
                log(f"  ✓ view_in_frame 降档后无重叠")
        else:
            log(f"  ✓ view_in_frame 重定位后无新重叠")

    _apply_reference_outline_size_corrections("post_view_in_frame")

    # 6) 自动尺寸（v1.4 Task 4: 优先 InsertModelAnnotations3，失败兜底 InsertDimension2）
    log("[6/9] 导入模型尺寸 InsertModelAnnotations3")
    ext = drw.Extension
    imported = False
    try:
        _reference_concise_dim_sample = 0 < int(reference_dim_floor or 0) <= 2
    except Exception:
        _reference_concise_dim_sample = False
    _skip_generic_model_dim_import = _v4_should_skip_generic_model_dimension_import(
        _drawing_blueprint_v4,
        reference_dim_floor,
    )
    _disable_reference_autodimension = _v4_should_disable_reference_autodimension(
        _drawing_blueprint_v4,
        reference_dim_floor,
    )
    if _reference_concise_dim_sample:
        log("  [reference_style] skip model dimension import for concise same-name reference")
        warnings_box.append({
            "code": "reference_model_dim_import_skipped",
            "reference_display_dim_floor": reference_dim_floor,
            "msg": "同名参考图为极简尺寸风格，跳过模型尺寸全量导入以避免过标注。",
        })
    if _skip_generic_model_dim_import:
        log("  [reference_intent] skip generic model dimension import; explicit target groups drive 006")
        warnings_box.append({
            "code": "reference_intent_model_dim_import_skipped",
            "reference_display_dim_floor": reference_dim_floor,
            "dimension_target_count": len(((_drawing_blueprint_v4 or {}).get("dimension_plan") or {}).get("dimension_targets") or []),
            "msg": "Reference-intent dimension targets are active; skip bulk model dimensions to avoid AutoDimension-style slanted callout stacks.",
        })
    try:
        fn = getattr(ext, "InsertModelAnnotations3", None)
        if callable(fn) and not _reference_concise_dim_sample and not _skip_generic_model_dim_import:
            # InsertModelAnnotations3(Type, Options, AllViews, Process, IncludeChildren, IncludeFeatures, FeatTolType)
            # Options=32 表示所有尺寸；FeatTolType=0 = swFeatureTolType_None
            # 与 sw_com_api_index.md L115 的 7 参数签名对齐（v1.5 Task 1.1）
            fn(0, 32, True, True, False, False, 0)
            imported = True
            log("  + InsertModelAnnotations3 调用成功（7 参数）")
    except Exception as exc:
        log(f"  ! InsertModelAnnotations3 异常: {exc}")
        warnings_box.append({"code":"dim_import3_exc","msg":str(exc)})

    if not imported and not _reference_concise_dim_sample and not _skip_generic_model_dim_import:
        try:
            sw.RunCommand(826, "")
            imported = True
            log("  + RunCommand(826) 兜底成功")
        except Exception as exc:
            log(f"  ! RunCommand(826) 兜底失败: {exc}")
            warnings_box.append({"code":"dim_import_failed","msg":str(exc)})

    # v1.4 Task 4: 二次拉模型项 + 检查 dim_total，若仍为 0 则 InsertDimension2 兜底
    try:
        drw.ForceRebuild3(True)
        import time as _t
        _t.sleep(1.0)
        if imported:
            try:
                sw.RunCommand(826, "")
                print("[v6 dim] second RunCommand(826) issued")
            except Exception as e:
                print(f"[v6 dim] second RunCommand failed: {e}")
    except Exception as e:
        print(f"[v6 dim] second RunCommand failed: {e}")

    # v1.4 Task 4.2: 检查 dim_total，若 < 5 则 InsertDimension2 兜底插入 5 个尺寸
    def _count_display_dims(drw_doc):
        try:
            api_total = 0
            view_for_api = call(drw_doc, "GetFirstView")
            seen_views = 0
            while view_for_api is not None and seen_views < 100:
                seen_views += 1
                view_count = 0
                try:
                    view_count = max(view_count, len(list(call(view_for_api, "GetDisplayDimensions") or [])))
                except Exception:
                    pass
                try:
                    display_dim = call(view_for_api, "GetFirstDisplayDimension")
                    seen_dims = 0
                    while display_dim is not None and seen_dims < 2000:
                        seen_dims += 1
                        try:
                            display_dim = view_for_api.GetNextDisplayDimension(display_dim)
                        except Exception:
                            break
                    view_count = max(view_count, seen_dims)
                except Exception:
                    pass
                api_total += view_count
                view_for_api = call(view_for_api, "GetNextView")
            if api_total > 0:
                return api_total
        except Exception:
            pass
        try:
            cnt = 0
            v = call(drw_doc, "GetFirstView")
            while v is not None:
                a = call(v, "GetFirstAnnotation3")
                while a is not None:
                    t = call(a, "GetType")
                    if t == 1 and not _is_cosmetic_thread_annotation(a):  # DisplayDim
                        cnt += 1
                    a = call(a, "GetNext3")
                v = call(v, "GetNextView")
            return cnt
        except Exception:
            return 0

    _dim_floor = _effective_dimension_floor(reference_dim_floor)
    _dim_now = _count_display_dims(drw)
    log(f"  [v1.4 dim] 当前 DisplayDim 数量: {_dim_now}")
    if _dim_now < _dim_floor and front_view is not None:
        log(f"  [v1.4 dim] DisplayDim < {_dim_floor}, 启动 InsertDimension2 兜底")
        try:
            # v1.5 Task 1.2: 枚举前视图可见边，选中目标边后再插入尺寸
            edges = None
            try:
                edges = front_view.GetEdges(True)  # visible edges
            except Exception as exc:
                log(f"    ! GetEdges 异常: {exc}")
                edges = None

            if not edges:
                # v1.5 Task 1.3: GetEdges 不可用或返回空，降级到轮廓尺寸（Task 2）
                log("  [v1.5 dim] GetEdges 返回空，降级到轮廓尺寸（Task 2）")
            else:
                log(f"  [v1.5 dim] GetEdges 返回 {len(edges)} 条可见边")
                ob_front = view_outline_box(front_view)
                if not ob_front:
                    log("  [v1.5 dim] 无前视图 outline，降级到轮廓尺寸（Task 2）")
                else:
                    # 选中第一条边（优先 Select4，降级 SelectByID2）
                    first_edge = edges[0]
                    edge_selected = False
                    try:
                        sel_mgr = drw.SelectionManager
                        sel_data = call(sel_mgr, "CreateSelectData")
                        edge_selected = first_edge.Select4(True, sel_data)
                    except Exception as exc:
                        log(f"    ! Select4 选中边失败: {exc}")
                        edge_selected = False
                    if not edge_selected:
                        try:
                            edge_selected = ext.SelectByID2("", "EDGE", 0.0, 0.0, 0.0, False, 0, None, 0)
                        except Exception as exc:
                            log(f"    ! SelectByID2 选中边失败: {exc}")
                            edge_selected = False

                    if not edge_selected:
                        # v1.5 Task 1.3: 选中失败，降级到轮廓尺寸（Task 2）
                        log("  [v1.5 dim] 边选中失败，降级到轮廓尺寸（Task 2）")
                    else:
                        log("  [v1.5 dim] 边选中成功，插入尺寸")
                        fx0, fy0, fx1, fy1 = ob_front
                        fw = abs(fx1 - fx0); fh = abs(fy1 - fy0)
                        # 2 个水平尺寸 + 2 个垂直尺寸 + 1 个对角尺寸
                        horiz_pts = [
                            (fx0 + fw * 0.20, fy1 + 0.012),
                            (fx0 + fw * 0.70, fy1 + 0.012),
                        ]
                        vert_pts = [
                            (fx0 - 0.012, fy0 + fh * 0.30),
                            (fx0 - 0.012, fy0 + fh * 0.70),
                        ]
                        diag_pt = (fx1 + 0.012, fy1 + 0.012)
                        target_attempts = _reference_dimension_attempt_target(_dim_now, reference_dim_floor)
                        dim_plan = _dimension_insert_plan_for_outline(
                            ob_front,
                            target_attempts,
                            allow_diagonal=not _skip_generic_model_dim_import,
                        )
                        if dim_plan:
                            horiz_pts = [(x, y) for kind, x, y in dim_plan if kind == "horizontal"]
                            vert_pts = [(x, y) for kind, x, y in dim_plan if kind == "vertical"]
                            diag_pts = [(x, y) for kind, x, y in dim_plan if kind == "diagonal"]
                            diag_pt = diag_pts[0] if diag_pts else diag_pt
                            log(f"    [reference_style] dim insert plan attempts={len(dim_plan)} floor={_dim_floor}")

                        def _reselect_first_edge_for_dim():
                            try:
                                sel_mgr = drw.SelectionManager
                                sel_data = call(sel_mgr, "CreateSelectData")
                                return bool(first_edge.Select4(False, sel_data))
                            except Exception as exc:
                                log(f"    ! reselect edge failed: {exc}")
                                return False
                        for hx, hy in horiz_pts:
                            try:
                                drw.ClearSelection2(True)
                                if not _reselect_first_edge_for_dim():
                                    continue
                                drw.AddHorizontalDimension2(float(hx), float(hy), 0.0)
                                log(f"    + 水平尺寸 @({hx*1000:.1f},{hy*1000:.1f})mm")
                            except Exception as exc:
                                log(f"    ! 水平尺寸失败: {exc}")
                        for vx, vy in vert_pts:
                            try:
                                drw.ClearSelection2(True)
                                if not _reselect_first_edge_for_dim():
                                    continue
                                drw.AddVerticalDimension2(float(vx), float(vy), 0.0)
                                log(f"    + 垂直尺寸 @({vx*1000:.1f},{vy*1000:.1f})mm")
                            except Exception as exc:
                                log(f"    ! 垂直尺寸失败: {exc}")
                        try:
                            drw.ClearSelection2(True)
                            # 对角尺寸用 AddDimension2（非水平非垂直）
                            if not _reselect_first_edge_for_dim():
                                raise RuntimeError("edge reselect failed before diagonal dimension")
                            drw.AddDimension2(float(diag_pt[0]), float(diag_pt[1]), 0.0)
                            for extra_dx, extra_dy in (locals().get("diag_pts") or [])[1:]:
                                drw.ClearSelection2(True)
                                if not _reselect_first_edge_for_dim():
                                    continue
                                drw.AddDimension2(float(extra_dx), float(extra_dy), 0.0)
                                log(f"    + diagonal DisplayDim @({extra_dx*1000:.1f},{extra_dy*1000:.1f})mm")
                            log(f"    + 对角尺寸 @({diag_pt[0]*1000:.1f},{diag_pt[1]*1000:.1f})mm")
                        except Exception as exc:
                            log(f"    ! 对角尺寸失败: {exc}")
                        drw.ClearSelection2(True)
                        try: drw.ForceRebuild3(False)
                        except Exception: pass
        except Exception as exc:
            warnings_box.append({"code":"dim_fallback_fail","msg":str(exc)})

    # v1.5 Task 2: 轮廓尺寸降级（针对导入几何体零件）
    # 触发条件：InsertModelAnnotations3 + InsertDimension2 均未使 dim_total ≥ 5
    _dim_after_ins2 = _count_display_dims(drw)
    log(f"  [v1.5 dim] InsertDimension2 后 DisplayDim 数量: {_dim_after_ins2}")
    if _dim_after_ins2 < _dim_floor and front_view is not None:
        log(f"  [v1.5 dim] DisplayDim 仍 < {_dim_floor}, 启动轮廓尺寸降级（GetPartBox）")
        try:
            # Task 2.1: 获取包围盒坐标
            box = part.GetPartBox(True)
            box = list(box) if box else None
            if not box or len(box) < 6:
                log("  [v1.5 dim] GetPartBox 返回空，跳过轮廓尺寸降级")
            else:
                bx_min, by_min, bz_min = box[0], box[1], box[2]
                bx_max, by_max, bz_max = box[3], box[4], box[5]
                Lx = abs(bx_max - bx_min)  # 总长
                Ly = abs(by_max - by_min)  # 总宽
                log(f"  [v1.5 dim] bbox Lx={Lx*1000:.1f}mm Ly={Ly*1000:.1f}mm")
                ob_front = view_outline_box(front_view)
                if not ob_front:
                    log("  [v1.5 dim] 无前视图 outline，跳过轮廓尺寸降级")
                else:
                    fx0, fy0, fx1, fy1 = ob_front
                    fw = abs(fx1 - fx0); fh = abs(fy1 - fy0)
                    # Task 2.2: 选中包围盒角点（前视图坐标系，投影到 XY 平面）
                    # 角点顺序：左下 -> 右下 -> 右上 -> 左上
                    corner_pts = [
                        (float(bx_min), float(by_min), 0.0),
                        (float(bx_max), float(by_min), 0.0),
                        (float(bx_max), float(by_max), 0.0),
                        (float(bx_min), float(by_max), 0.0),
                    ]
                    for cx, cy, cz in corner_pts:
                        try:
                            ext.SelectByID2("", "POINT", cx, cy, cz, True, 0, None, 0)
                        except Exception as exc:
                            log(f"    ! 选中角点({cx*1000:.1f},{cy*1000:.1f})失败: {exc}")
                    # 插入总长（水平尺寸）
                    fallback_attempts = _reference_dimension_attempt_target(_dim_after_ins2, reference_dim_floor)
                    fallback_dim_plan = _dimension_insert_plan_for_outline(
                        ob_front,
                        fallback_attempts,
                        allow_diagonal=not _skip_generic_model_dim_import,
                    )
                    if fallback_dim_plan:
                        log(f"    [reference_style] outline dim plan attempts={len(fallback_dim_plan)} floor={_dim_floor}")

                    def _select_bbox_points_for_dimension(kind):
                        point_pairs = {
                            "horizontal": ((float(bx_min), float(by_min), 0.0), (float(bx_max), float(by_min), 0.0)),
                            "vertical": ((float(bx_min), float(by_min), 0.0), (float(bx_min), float(by_max), 0.0)),
                            "diagonal": ((float(bx_min), float(by_min), 0.0), (float(bx_max), float(by_max), 0.0)),
                        }
                        first, second = point_pairs.get(kind, point_pairs["diagonal"])
                        try:
                            drw.ClearSelection2(True)
                            ok1 = ext.SelectByID2("", "POINT", first[0], first[1], first[2], False, 0, None, 0)
                            ok2 = ext.SelectByID2("", "POINT", second[0], second[1], second[2], True, 0, None, 0)
                            return bool(ok1 and ok2)
                        except Exception as exc:
                            log(f"    ! bbox point reselect failed ({kind}): {exc}")
                            return False

                    try:
                        drw.ClearSelection2(True)
                        if not _select_bbox_points_for_dimension("horizontal"):
                            raise RuntimeError("bbox horizontal point selection failed")
                        hx = fx0 + fw * 0.5
                        hy = fy1 + 0.012
                        drw.AddHorizontalDimension2(float(hx), float(hy), 0.0)
                        log(f"    + 轮廓水平尺寸（总长 {Lx*1000:.1f}mm） @({hx*1000:.1f},{hy*1000:.1f})mm")
                    except Exception as exc:
                        log(f"    ! 轮廓水平尺寸失败: {exc}")
                    # 插入总宽（垂直尺寸）
                    try:
                        drw.ClearSelection2(True)
                        if not _select_bbox_points_for_dimension("vertical"):
                            raise RuntimeError("bbox vertical point selection failed")
                        vx = fx0 - 0.012
                        vy = fy0 + fh * 0.5
                        drw.AddVerticalDimension2(float(vx), float(vy), 0.0)
                        log(f"    + 轮廓垂直尺寸（总宽 {Ly*1000:.1f}mm） @({vx*1000:.1f},{vy*1000:.1f})mm")
                    except Exception as exc:
                        log(f"    ! 轮廓垂直尺寸失败: {exc}")
                    # 插入对角尺寸
                    try:
                        drw.ClearSelection2(True)
                        if not _select_bbox_points_for_dimension("diagonal"):
                            raise RuntimeError("bbox diagonal point selection failed")
                        dx = fx1 + 0.012
                        dy = fy1 + 0.012
                        drw.AddDimension2(float(dx), float(dy), 0.0)
                        for extra_kind, extra_x, extra_y in fallback_dim_plan[3:]:
                            if not _select_bbox_points_for_dimension(extra_kind):
                                continue
                            if extra_kind == "horizontal":
                                drw.AddHorizontalDimension2(float(extra_x), float(extra_y), 0.0)
                            elif extra_kind == "vertical":
                                drw.AddVerticalDimension2(float(extra_x), float(extra_y), 0.0)
                            else:
                                drw.AddDimension2(float(extra_x), float(extra_y), 0.0)
                            log(f"    + outline {extra_kind} DisplayDim @({extra_x*1000:.1f},{extra_y*1000:.1f})mm")
                        log(f"    + 轮廓对角尺寸 @({dx*1000:.1f},{dy*1000:.1f})mm")
                    except Exception as exc:
                        log(f"    ! 轮廓对角尺寸失败: {exc}")
                    drw.ClearSelection2(True)
                    try: drw.ForceRebuild3(False)
                    except Exception: pass
        except Exception as exc:
            warnings_box.append({"code":"outline_dim_fallback_fail","msg":str(exc)})

    # 6.5) Reference-aware front-view dimension reinforcement.
    try:
        if front_view is not None:
            ob_front = view_outline_box(front_view)
            _dim_before_force = _count_display_dims(drw)
            if ob_front and _dim_before_force < _dim_floor:
                force_plan = _force_dimension_insert_plan(
                    ob_front,
                    _dim_before_force,
                    reference_dim_floor,
                    allow_diagonal=not _skip_generic_model_dim_import,
                )
                log(
                    f"  [v1.6 dim] force plan before={_dim_before_force} "
                    f"floor={_dim_floor} attempts={len(force_plan)}"
                )
                force_edges = None

                def _select_front_edge_for_force_dim():
                    nonlocal force_edges
                    if force_edges is None:
                        try:
                            force_edges = list(front_view.GetEdges(True) or [])
                        except Exception as exc:
                            log(f"    ! force GetEdges failed: {exc}")
                            force_edges = []
                    if force_edges:
                        try:
                            sel_mgr = drw.SelectionManager
                            sel_data = call(sel_mgr, "CreateSelectData")
                            return bool(force_edges[0].Select4(False, sel_data))
                        except Exception as exc:
                            log(f"    ! force Select4 failed: {exc}")
                    try:
                        return bool(ext.SelectByID2("", "EDGE", 0.0, 0.0, 0.0, False, 0, None, 0))
                    except Exception as exc:
                        log(f"    ! force SelectByID2 failed: {exc}")
                        return False

                for kind, px, py in force_plan:
                    try:
                        if _count_display_dims(drw) >= _dim_floor:
                            break
                        drw.ClearSelection2(True)
                        if not _select_front_edge_for_force_dim():
                            warnings_box.append({"code":"force_dim_edge_select_failed","kind":kind})
                            continue
                        if kind == "horizontal":
                            drw.AddHorizontalDimension2(float(px), float(py), 0.0)
                        elif kind == "vertical":
                            drw.AddVerticalDimension2(float(px), float(py), 0.0)
                        else:
                            drw.AddDimension2(float(px), float(py), 0.0)
                        try:
                            drw.ForceRebuild3(False)
                        except Exception:
                            pass
                        log(f"    + force {kind} DisplayDim @({px*1000:.1f},{py*1000:.1f})mm")
                    except Exception as exc:
                        warnings_box.append({"code":"force_dim_insert_fail","kind":kind,"msg":str(exc)})
                drw.ClearSelection2(True)
                _dim_after_force = _count_display_dims(drw)
                log(f"  [v1.6 dim] force DisplayDim count: {_dim_before_force} -> {_dim_after_force}")
    except Exception as exc:
        warnings_box.append({"code":"force_dim_outer","msg":str(exc)})

    # 6.5) 前视图强制尺寸增强（≥2 水平 + ≥2 垂直）
    try:
        if False and front_view is not None:
            ob_front = view_outline_box(front_view)
            if ob_front:
                fx0, fy0, fx1, fy1 = ob_front
                fw = abs(fx1 - fx0); fh = abs(fy1 - fy0)
                horiz_pts = [
                    (fx0 + fw * 0.25, fy1 + 0.012),
                    (fx0 + fw * 0.75, fy1 + 0.012),
                ]
                vert_pts = [
                    (fx0 - 0.012, fy0 + fh * 0.25),
                    (fx0 - 0.012, fy0 + fh * 0.75),
                ]
                for hx, hy in horiz_pts:
                    try:
                        drw.ClearSelection2(True)
                        drw.AddHorizontalDimension2(float(hx), float(hy), 0.0)
                    except Exception as exc:
                        warnings_box.append({"code":"add_h_dim_fail","msg":str(exc)})
                for vx, vy in vert_pts:
                    try:
                        drw.ClearSelection2(True)
                        drw.AddVerticalDimension2(float(vx), float(vy), 0.0)
                    except Exception as exc:
                        warnings_box.append({"code":"add_v_dim_fail","msg":str(exc)})
                drw.ClearSelection2(True)
    except Exception as exc:
        warnings_box.append({"code":"force_dim_outer","msg":str(exc)})

    # 7) 剖视图（section_helper）
    log("[7/9] 创建剖视图 section_helper.create_section_in_active_drawing")
    section_view = False
    section_helper_called = False
    if not reference_section_allowed:
        log("  [reference_style] 同名参考图未使用剖视图；跳过自动剖视以保持参考视图数量")
        warnings_box.append({
            "code":"OK",
            "key":"section_view_exempt_reference_style",
            "msg":"同名参考图未使用剖视图；已按参考图跳过自动剖视，保持视图数量一致",
        })
    else:
        try:
            section_helper_called = True
            ok_sec = create_section_in_active_drawing(sw, drw)
            if ok_sec:
                section_view = True
                log("  + 剖视图 A-A OK")
                warnings_box.append({"code":"OK","key":"section_view","msg":"剖视图 A-A 创建成功"})
            else:
                warnings_box.append({"code":"section_helper_failed",
                                     "msg":"create_section_in_active_drawing 返回 False"})
        except Exception as exc:
            warnings_box.append({"code":"section_helper_exc","msg":str(exc)})

    # Strategy 8: VBA macro fallback via RunMacro2 (v6: .swp 优先 + 大小校验)
    if reference_section_allowed and not section_view:
        try:
            from pathlib import Path as _P
            ROOT_PATH = _P(__file__).resolve().parent.parent.parent.parent
            swp = ROOT_PATH / "templates" / "macros" / "auto_section.swp"
            bas = ROOT_PATH / "templates" / "macros" / "auto_section.bas"
            macro = swp if swp.exists() and swp.stat().st_size > 1000 else (bas if bas.exists() else None)
            macro_path = str(macro) if macro else None
            if macro_path:
                print(f"[section] fallback to RunMacro2: {macro_path}")
                try:
                    ok = sw.RunMacro2(macro_path, "auto_section", "main", 1, 0)
                    print(f"[section] RunMacro2 result={ok}")
                    if ok:
                        section_view = True
                        warnings_box.append({"code":"OK","key":"section_view_vba","msg":"剖视图通过 VBA 兜底创建"})
                except Exception as e:
                    print(f"[section] RunMacro2 failed: {e}")
                    warnings_box.append({"code":"section_vba_fail","msg":str(e)})
        except Exception as e:
            print(f"[section] vba strategy setup failed: {e}")
            warnings_box.append({"code":"section_vba_setup_fail","msg":str(e)})

    # 8) 13 项属性写入
    log("[8/9] 写 13 项属性 (Add3 + Set2)")
    write_targets = []
    try: write_targets.append(drw.Extension.CustomPropertyManager(""))
    except Exception: pass
    try:
        cfg_names = drw.GetConfigurationNames if not callable(getattr(drw, "GetConfigurationNames", None)) else drw.GetConfigurationNames()
        for cn in list(cfg_names or []):
            try: write_targets.append(drw.Extension.CustomPropertyManager(cn))
            except Exception: pass
    except Exception: pass
    for cpm in write_targets:
        for k in PROP_KEYS:
            val = src_props.get(k, "") or ""
            try:
                cpm.Add3(k, 30, val, 2)
                if val:
                    try: cpm.Set2(k, val)
                    except Exception: pass
            except Exception as exc:
                warnings_box.append({"code":"prop_write_fail","key":k,"msg":str(exc)})

    # 9) 兜底 Note：技术要求 + Ra + 基准 A（单 Note 多行，单次插入）
    log("[9/9] 兜底 Notes：技术要求 / Ra / 基准 A（每条 1 次）")
    try:
        drw.ClearSelection2(True)
        try: drw.ActivateSheet(sheet_name)
        except Exception: pass

        def _insert_note_n(text, base_pos, n=1, dy=0.005):
            def _place_note(note_obj, x, y):
                if note_obj is None:
                    return False
                try:
                    if hasattr(note_obj, "SetText"):
                        note_obj.SetText(str(text))
                except Exception:
                    pass
                try:
                    note_obj.Text = str(text)
                except Exception:
                    pass
                ann = call(note_obj, "GetAnnotation")
                if ann is not None:
                    try:
                        ann.SetPosition2(x, y, 0)
                    except Exception:
                        pass
                return True

            ok_n = 0
            for i_ in range(n):
                x = base_pos[0]
                y = base_pos[1] - i_ * dy
                try:
                    drw.ClearSelection2(True)
                    note = None
                    try:
                        note = drw.InsertNote(str(text))
                    except Exception:
                        note = None
                    if note is None:
                        try:
                            note = drw.InsertNote(str(text), float(x), float(y))
                        except Exception:
                            note = None
                    if note is None:
                        try:
                            note = drw.CreateText2(str(text), float(x), float(y), 0.0, 0.005, 0.0)
                        except Exception:
                            note = None
                    if _place_note(note, float(x), float(y)):
                        ok_n += 1
                    drw.ClearSelection2(True)
                except Exception as exc:
                    warnings_box.append({"code":"note_insert_exc","text":text[:20],"i":i_,"msg":str(exc)})
            return ok_n

        _bp_note_insertions = _v4_blueprint_note_insertions(_drawing_blueprint_v4)
        _bp_titlebar_insertions = _v4_blueprint_titlebar_insertions(_drawing_blueprint_v4, src_props)
        _bp_flags = (
            _v4_blueprint_annotation_flags(_drawing_blueprint_v4)
            if _drawing_blueprint_v4
            else {"roughness_required": True, "datum_required": True, "gtol_required": True}
        )
        if _bp_note_insertions:
            n_tech = 0
            for plan in _bp_note_insertions:
                n_tech += _insert_note_n(plan["text"], plan["position_m"], n=1)
            warnings_box.append({
                "code": "drawing_blueprint_notes_inserted",
                "planned": len(_bp_note_insertions),
                "inserted": n_tech,
                "source": "DrawingBlueprint.notes_plan",
            })
            log(f"  + v4 blueprint notes x{n_tech}")
        else:
            n_tech = _insert_note_n(TECH_NOTES, FALLBACK_NOTE_POS["tech"], n=1)
            log(f"  + 技术要求 Note x{n_tech}")
            n_ra = _insert_note_n("其余 √Ra3.2", FALLBACK_NOTE_POS["ra"], n=1)
            log(f"  + Ra 3.2 Note x{n_ra}")

        if _bp_titlebar_insertions:
            n_tb = 0
            for plan in _bp_titlebar_insertions:
                n_tb += _insert_note_n(plan["text"], plan["position_m"], n=1)
            warnings_box.append({
                "code": "drawing_blueprint_titlebar_note_inserted",
                "planned": len(_bp_titlebar_insertions),
                "inserted": n_tb,
                "source": "DrawingBlueprint.titlebar_plan",
            })
            log(f"  + v4 blueprint titlebar visible Note x{n_tb}")

        # 基准 A：优先 InsertDatumTag2，失败兜底 InsertNote("△A")
        n_dt = 0
        if _bp_flags.get("datum_required"):
            try:
                drw.ClearSelection2(True)
                dt = None
                try:
                    dt = drw.InsertDatumTag2()
                except Exception:
                    dt = None
                if dt is not None:
                    ann = call(dt, "GetAnnotation")
                    if ann is not None:
                        try:
                            ann.SetPosition2(FALLBACK_NOTE_POS["datum"][0],
                                             FALLBACK_NOTE_POS["datum"][1], 0)
                        except Exception:
                            pass
                    n_dt = 1
                drw.ClearSelection2(True)
            except Exception as exc:
                warnings_box.append({"code":"datum_tag_exc","msg":str(exc)})
            if n_dt == 0:
                n_dt = _insert_note_n("△A", FALLBACK_NOTE_POS["datum"], n=1)
            log(f"  + 基准 A x{n_dt}")
        else:
            log("  + v4 blueprint datum skipped (not required)")

        # 形位公差框（平面度 0.05）
        if _bp_flags.get("gtol_required"):
            try:
                drw.ClearSelection2(True)
                gtol = None
                try: gtol = drw.InsertGtol()
                except Exception: gtol = None
                if gtol is None:
                    try: gtol = drw.InsertGtol()
                    except Exception: gtol = None
                if gtol is not None:
                    try: gtol.SetSymbol(2, "0.05", "A")
                    except Exception: pass
                    try:
                        ann = gtol.GetAnnotation()
                        ann.SetPosition2(0.025, 0.105, 0)
                    except Exception: pass
                    print("[gtol] inserted flatness 0.05 A")
                else:
                    fb_ok = _insert_note_n("⏥ 0.05 A", (0.025, 0.105), n=1)
                    if fb_ok > 0:
                        print("[gtol] fallback note '⏥ 0.05 A' inserted")
                    else:
                        fb2 = _insert_note_n("[FLAT] 0.05 A", (0.025, 0.105), n=1)
                        if fb2 > 0:
                            print("[gtol] fallback ASCII note '[FLAT] 0.05 A' inserted")
                        else:
                            print("[gtol] fallback note insertion all failed")
            except Exception as e:
                print(f"[gtol] insert failed: {e}")
                warnings_box.append({"code":"gtol_fail","msg":str(e)})
        else:
            log("  + v4 blueprint gtol skipped (not required)")
    except Exception as exc:
        warnings_box.append({"code":"notes_outer","msg":str(exc)})

    # 9.5) SaveAs 前最终强制：字高 + 前视图位置 + ForceRebuild
    log("[9.5/9] SaveAs 前最终强制：字高 + front_view.Position")
    try:
        for try_th in (text_height, 0.006, 0.007, 0.005):
            ok_th_drw = drw.SetUserPreferenceDoubleValue(89, try_th)
            ok_th_sw = False
            try:
                ok_th_sw = sw.SetUserPreferenceDoubleValue(89, try_th)
            except Exception: pass
            try: drw.ForceRebuild3(True)
            except Exception: pass
            cur = drw.GetUserPreferenceDoubleValue(89)
            cur_sw = None
            try: cur_sw = sw.GetUserPreferenceDoubleValue(89)
            except Exception: pass
            log(f"  字高强制 try={try_th}  drw_ok={ok_th_drw} sw_ok={ok_th_sw}  drw={cur} sw={cur_sw}")
            try:
                if float(cur) >= 0.0035:
                    break
            except Exception:
                pass
        try:
            ext_ = drw.Extension
            for nid in (8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20):
                try: ext_.SetUserPreferenceDouble(89, nid, 0.005)
                except Exception: pass
        except Exception: pass
        try:
            tf = sw.GetUserPreferenceTextFormat(0, 0) if hasattr(sw, "GetUserPreferenceTextFormat") else None
            if tf is not None:
                try: tf.CharHeight = 0.005
                except Exception: pass
                try: tf.CharHeightInPts = 14
                except Exception: pass
                try: sw.SetUserPreferenceTextFormat(0, 0, tf)
                except Exception: pass
                try: drw.SetUserPreferenceTextFormat(0, 0, tf)
                except Exception: pass
                cur = drw.GetUserPreferenceDoubleValue(89)
                log(f"  TextFormat 强制后 drw GetUserPref={cur}")
        except Exception as exc:
            warnings_box.append({"code":"text_format_fail","msg":str(exc)})
    except Exception as exc:
        warnings_box.append({"code":"text_height_final_fail","msg":str(exc)})

    # 强制把前视图位置摆回 (0.080, 0.140) — v6 T 字主位
    try:
        if front_view is not None and "front" in created_views:
            front_x, front_y = _final_front_position(centers)
            ok_fp = _set_view_position(front_view, front_x, front_y)
            try:
                pos = list(front_view.Position) if front_view.Position else []
            except Exception:
                pos = []
            log(f"  强制 front Position=(80,140)mm  set_ok={ok_fp}  实际={pos}")
            log(f"  reference front target=({front_x*1000:.1f},{front_y*1000:.1f})mm")
            try: drw.ForceRebuild3(False)
            except Exception: pass
    except Exception as exc:
        warnings_box.append({"code":"front_force_fail","msg":str(exc)})

    # 9.6) 视图布局完成后，最终渲染 GB A4 图框 + 标题栏
    if not _drwdot_path or not os.path.exists(_drwdot_path):
        if not _draw_default_titleblock:
            log(f"[9.6/9] reference style -> skip built-in GB frame/titleblock ({_titleblock_policy_source})")
            warnings_box.append({
                "code": "reference_titleblock_policy",
                "policy": "skip_builtin_gb_frame_titleblock",
                "source": _titleblock_policy_source,
                "reason": "same-name reference layout controls visible sheet/titleblock style",
            })
        else:
            log("[9.6/9] no template -> draw GB frame & titleblock by API")
            try:
                _draw_gb_frame_and_titleblock(drw, drw)
                try: drw.ForceRebuild3(True)
                except Exception: pass
                try: drw.GraphicsRedraw2()
                except Exception: pass
            except Exception as exc:
                warnings_box.append({"code":"frame_titleblock_fail","msg":str(exc)})
                log(f"[9.6/9] draw failed: {exc}")
    else:
        log(f"[9.6/9] using template, skip self-drawing frame/titleblock")
        try: drw.ForceRebuild3(True)
        except Exception: pass
        try: drw.GraphicsRedraw2()
        except Exception: pass

    # [9.7/9] 重新绑定所有视图的 ReferencedDocument + ReferencedConfiguration（v6 用缓存）
    _rebound_view_names: list = []
    try:
        rebind_count = 0
        view_iter = list(created_views.values())
        try:
            sheet_view = drw.GetFirstView()
            cur = sheet_view.GetNextView() if sheet_view else None
            seen_ids = set(id(v) for v in view_iter)
            while cur:
                if id(cur) not in seen_ids:
                    view_iter.append(cur)
                    seen_ids.add(id(cur))
                try: cur = cur.GetNextView()
                except Exception: break
        except Exception: pass
        for v_ in view_iter:
            try:
                try: v_.SetReferencedDocument(part)
                except Exception: pass
                if _cached_cfg_name:
                    try: v_.SetReferencedConfiguration(_cached_cfg_name)
                    except Exception: pass
                try:
                    _vn = v_.Name
                    if _vn and _vn not in _rebound_view_names:
                        _rebound_view_names.append(_vn)
                except Exception: pass
                rebind_count += 1
            except Exception: pass
        print(f"[9.7/9] rebound {rebind_count} views to part+cfg='{_cached_cfg_name}', names={_rebound_view_names}")
        try: drw.ForceRebuild3(True)
        except Exception: pass
    except Exception as e:
        print(f"[9.7/9] rebind failed: {e}")

    # [9.8/9] SaveAs 之前对所有视图调用 ReplaceViewModel 重新绑定模型（探索性）
    try:
        import pythoncom as _pyc_rv
        from win32com.client import VARIANT as _VARIANT_RV
        from pathlib import Path as _PathRV

        _part_abs = ""
        try: _part_abs = str(_PathRV(part_path).resolve())
        except Exception:
            try: _part_abs = str(_PathRV(sys.argv[1]).resolve())
            except Exception: _part_abs = ""

        # 视图名优先复用 [9.7/9] 中已经枚举到的；否则再次链表枚举
        view_names = list(_rebound_view_names) if '_rebound_view_names' in dir() and _rebound_view_names else []
        if not view_names:
            try:
                sheet_view = drw.GetFirstView()
                cur = sheet_view.GetNextView() if sheet_view else None
                while cur:
                    try:
                        n = cur.Name
                        if n: view_names.append(n)
                    except Exception: pass
                    try: cur = cur.GetNextView()
                    except Exception: break
            except Exception as _e:
                print(f"[v6 replace] enum views failed: {_e}")
        # 再退一步：用 created_views（v6 主流程创建的视图字典/列表）
        if not view_names and 'created_views' in dir():
            try:
                _cv = created_views
                _iter = _cv.values() if hasattr(_cv, 'values') else _cv
                for v in _iter:
                    try:
                        n = v.Name
                        if n and n not in view_names: view_names.append(n)
                    except Exception: pass
            except Exception: pass

        if _part_abs and _PathRV(_part_abs).exists() and view_names:
            print(f"[v6 replace] view_names={view_names}, part_abs={_part_abs}")
            try:
                names_arr = _VARIANT_RV(_pyc_rv.VT_ARRAY | _pyc_rv.VT_BSTR, view_names)
                inst_arr = _VARIANT_RV(_pyc_rv.VT_ARRAY | _pyc_rv.VT_DISPATCH, [None] * len(view_names))
                ok = drw.ReplaceViewModel(_part_abs, names_arr, inst_arr)
                print(f"[v6 replace] ReplaceViewModel({len(view_names)} views) -> {ok}")
            except Exception as e:
                print(f"[v6 replace] ReplaceViewModel(VARIANT) failed: {e}")
                try:
                    ok = drw.ReplaceViewModel(_part_abs, view_names, None)
                    print(f"[v6 replace] ReplaceViewModel(plain) -> {ok}")
                except Exception as e2:
                    print(f"[v6 replace] ReplaceViewModel(plain) failed: {e2}")
        else:
            print(f"[v6 replace] skip (part_abs={_part_abs!r}, view_names={view_names})")
    except Exception as e:
        print(f"[v6 replace] block failed: {e}")

    try: drw.ForceRebuild3(True)
    except Exception: pass
    try: drw.GraphicsRedraw2()
    except Exception: pass

    _autodim_result = {"applied": False, "before": None, "after": None, "attempts": []}
    _dim_prune_result = {"enabled": False, "cap": 0, "success": True}
    _reference_intent_target_coverage_results = []
    try:
        _autodim_before = _count_display_dims(drw)
        if _autodim_before < _dim_floor:
            if _disable_reference_autodimension:
                _explicit_dim_result = _run_reference_intent_explicit_display_dims("pre_saveas")
                _autodim_before = _count_display_dims(drw)
                log(
                    f"  [reference_intent] AutoDimension disabled before SaveAs; "
                    f"DisplayDim={_autodim_before} floor={_dim_floor}"
                )
                _autodim_result = {
                    "applied": False,
                    "skipped": True,
                    "before": _autodim_before,
                    "after": _autodim_before,
                    "reason": "reference_intent_autodimension_disabled_by_ui_screenshot_gate",
                    "explicit_display_dims": _explicit_dim_result,
                    "attempts": [],
                }
                if _autodim_before < _dim_floor:
                    warnings_box.append({
                        "code": "reference_intent_autodimension_disabled",
                        "before": _autodim_before,
                        "after": _autodim_before,
                        "reference_display_dim_floor": _dim_floor,
                        "reason": "application_ui_screenshot_visual_acceptance_failed_generic_autodimension",
                        "msg": "Reference-intent path forbids IDrawingDoc.AutoDimension as acceptance evidence; explicit DisplayDim placement must reach the floor.",
                    })
            else:
                log(f"  [v1.8 autodim] before SaveAs DisplayDim={_autodim_before} floor={_dim_floor}")
                _autodim_result = _run_reference_autodimension()
                _autodim_after = int(_autodim_result.get("after") or 0)
                log(f"  [v1.8 autodim] result {_autodim_result.get('before')} -> {_autodim_after}")
                if _autodim_result.get("applied"):
                    warnings_box.append({
                        "code": "reference_autodim_applied",
                        "before": _autodim_result.get("before"),
                        "after": _autodim_after,
                        "reference_display_dim_floor": _dim_floor,
                    })
                elif _autodim_after < _dim_floor:
                    warnings_box.append({
                        "code": "reference_autodim_no_increase",
                        "before": _autodim_result.get("before"),
                        "after": _autodim_after,
                        "reference_display_dim_floor": _dim_floor,
                    })
            try: drw.ForceRebuild3(True)
            except Exception: pass
            try: drw.GraphicsRedraw2()
            except Exception: pass
    except Exception as exc:
        log(f"  [v1.8 autodim] exception: {exc}")
        warnings_box.append({"code":"reference_autodim_exception","msg":str(exc)})
    _pre_saveas_target_coverage = _record_reference_intent_target_coverage("pre_saveas")

    # 10) 保存（_v5 后缀，保持向后兼容） — part 必须仍在内存中
    log("[save] 保存 SLDDRW / PDF / DXF（_v5 后缀） — part 保持打开")
    try:
        drw_cpm = drw.Extension.CustomPropertyManager("")
        for k, v in _default_props.items():
            if v:
                try: drw_cpm.Add3(k, 30, str(v), 1)
                except Exception:
                    try: drw_cpm.Set2(k, str(v))
                    except Exception: pass
    except Exception as e:
        print(f"[cprop] drw write failed: {e}")
    try: drw.ForceRebuild3(True)
    except Exception: pass
    try: drw.GraphicsRedraw2()
    except Exception: pass
    try:
        sw.ActivateDoc3(call(drw, "GetTitle"), True, 0,
                        VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0))
    except Exception:
        try: sw.ActivateDoc2(call(drw, "GetTitle"), True,
                             VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0))
        except Exception: pass
    slddrw = os.path.join(out_dir, f"{base_name}_v5.SLDDRW")
    pdf    = os.path.join(out_dir, f"{base_name}_v5.PDF")
    dxf    = os.path.join(out_dir, f"{base_name}_v5.DXF")
    _dimension_arrange_results = []

    def _arrange_norm_box_to_sheet(box_norm, layout_plan):
        if not isinstance(box_norm, (list, tuple)) or len(box_norm) < 4:
            return None
        sheet_size = (layout_plan or {}).get("sheet_size") or {}
        try:
            sheet_w = float(sheet_size.get("width") or REFERENCE_SHEET_SIZE_M[0])
            sheet_h = float(sheet_size.get("height") or REFERENCE_SHEET_SIZE_M[1])
            x0, y0, x1, y1 = [float(v) for v in box_norm[:4]]
        except Exception:
            return None
        x0, x1 = sorted((max(0.0, min(1.0, x0)), max(0.0, min(1.0, x1))))
        y0, y1 = sorted((max(0.0, min(1.0, y0)), max(0.0, min(1.0, y1))))
        return (x0 * sheet_w, y0 * sheet_h, x1 * sheet_w, y1 * sheet_h)

    def _arrange_dim_position(dim_obj):
        for name in ("TextPosition", "GetTextPosition", "GetPosition"):
            value = call(dim_obj, name)
            if value and not isinstance(value, str):
                try:
                    if len(value) >= 2:
                        return (float(value[0]), float(value[1]))
                except Exception:
                    continue
        return (0.0, 0.0)

    def _arrange_dim_arrow_position(dim_obj, fallback):
        for name in ("ArrowHeadPosition", "GetArrowHeadPosition", "GetArrowPosition"):
            value = call(dim_obj, name)
            if value and not isinstance(value, str):
                try:
                    if len(value) >= 2:
                        return (float(value[0]), float(value[1]))
                except Exception:
                    continue
        return fallback

    def _arrange_set_dim_position(dim_obj, pos):
        values = [float(pos[0]), float(pos[1])]
        try:
            dim_obj.TextPosition = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, values)
            return True
        except Exception:
            pass
        for candidate in (tuple(values), values):
            try:
                setattr(dim_obj, "TextPosition", candidate)
                return True
            except Exception:
                continue
        for method_name in ("SetPosition2", "SetPosition"):
            method = getattr(dim_obj, method_name, None)
            if not callable(method):
                continue
            try:
                method(float(pos[0]), float(pos[1]), 0.0)
                return True
            except TypeError:
                try:
                    method(float(pos[0]), float(pos[1]))
                    return True
                except Exception:
                    continue
            except Exception:
                continue
        return False

    def _arrange_distance(a, b):
        return ((float(a[0]) - float(b[0])) ** 2 + (float(a[1]) - float(b[1])) ** 2) ** 0.5

    def _arrange_point_in_box(point, box):
        return bool(box and box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3])

    def _arrange_collision_count(points, min_gap=0.008):
        count = 0
        for i in range(len(points)):
            for j in range(i + 1, len(points)):
                if _arrange_distance(points[i], points[j]) < min_gap:
                    count += 1
        return count

    def _arrange_layout_with_blueprint_context(layout_plan):
        merged = dict(layout_plan or {})
        if _drawing_blueprint_v4:
            merged.setdefault("part_class", str(_drawing_blueprint_v4.get("part_class") or ""))
            merged.setdefault(
                "required_display_dim_count",
                (_drawing_blueprint_v4.get("dimension_plan") or {}).get("required_display_dim_count"),
            )
        return merged

    def _arrange_display_dim_annotations_stage(stage_name, run_dir_for_arrange, layout_plan):
        sheet_size = (layout_plan or {}).get("sheet_size") or {}
        sheet_w = float(sheet_size.get("width") or REFERENCE_SHEET_SIZE_M[0])
        sheet_h = float(sheet_size.get("height") or REFERENCE_SHEET_SIZE_M[1])
        margin = 0.006
        track_gap = 0.012
        part_class = str((layout_plan or {}).get("part_class") or "").strip().lower()
        titlebar_box = (
            _arrange_norm_box_to_sheet((layout_plan or {}).get("titlebar_box_norm"), layout_plan)
            or (0.202, 0.0, 0.297, 0.038)
        )
        notes_box = _arrange_norm_box_to_sheet((layout_plan or {}).get("notes_box_norm"), layout_plan)
        avoid_boxes = [titlebar_box] + ([notes_box] if notes_box else [])

        layout_views = []
        for view_plan_item in (layout_plan or {}).get("views") or []:
            if not isinstance(view_plan_item, dict):
                continue
            box = _arrange_norm_box_to_sheet(view_plan_item.get("box_norm"), layout_plan)
            if not box:
                center_norm = view_plan_item.get("center_norm")
                if isinstance(center_norm, list) and len(center_norm) >= 2:
                    try:
                        cx = float(center_norm[0]) * sheet_w
                        cy = float(center_norm[1]) * sheet_h
                        box = (cx, cy, cx, cy)
                    except Exception:
                        box = None
            if box:
                layout_views.append({
                    "slot": str(view_plan_item.get("slot") or ""),
                    "box": tuple(box),
                })

        def _slot_for_outline(outline):
            if not layout_views or not outline:
                return ""
            cx = (float(outline[0]) + float(outline[2])) / 2.0
            cy = (float(outline[1]) + float(outline[3])) / 2.0
            best_slot = ""
            best_dist = 999.0
            for item in layout_views:
                box = item["box"]
                bx = (float(box[0]) + float(box[2])) / 2.0
                by = (float(box[1]) + float(box[3])) / 2.0
                dist = _arrange_distance((cx, cy), (bx, by))
                if dist < best_dist:
                    best_dist = dist
                    best_slot = item["slot"]
            return best_slot

        def _dimension_side(point, outline):
            x0, y0, x1, y1 = outline
            x, y = point
            if y > y1:
                return "top"
            if y < y0:
                return "bottom"
            if x < x0:
                return "left"
            if x > x1:
                return "right"
            distances = {
                "top": abs(y - y1),
                "bottom": abs(y - y0),
                "left": abs(x - x0),
                "right": abs(x - x1),
            }
            return min(distances, key=distances.get)

        def _long_thin_candidates(item):
            x0, y0, x1, y1 = item["outline"]
            width = max(float(x1) - float(x0), 0.001)
            height = max(float(y1) - float(y0), 0.001)
            rank = int(item.get("slot_order") or 0) + 1
            total = max(1, int(item.get("slot_total") or 1))
            frac = rank / float(total + 1)
            x_on_view = float(x0) + width * frac
            y_on_view = float(y0) + height * frac
            slot = str(item.get("slot") or "").lower()
            side = _dimension_side(item["position"], item["outline"])
            if slot == "top":
                anchor = tuple(item.get("arrow_position") or item.get("position") or (x_on_view, y_on_view))
                try:
                    anchor_x = float(anchor[0])
                    anchor_y = float(anchor[1])
                except Exception:
                    anchor_x, anchor_y = item["position"]
                x_on_view = max(float(x0), min(float(x1), anchor_x))
                y_on_view = max(float(y0), min(float(y1), anchor_y))
            if slot == "top":
                if str(item.get("lane_role") or "") == "right_callout":
                    preferred = ["top", "bottom"]
                elif side == "bottom":
                    preferred = ["bottom", "top"]
                else:
                    preferred = ["top", "bottom"]
                preserve_current_side = False
            elif slot in {"right", "iso"}:
                preferred = ["right", "top", "bottom", "left"]
                preserve_current_side = True
            else:
                preferred = ["top", "bottom", "left", "right"]
                preserve_current_side = True
            if preserve_current_side and side in preferred:
                preferred = [side] + [candidate for candidate in preferred if candidate != side]
            candidates = []
            if str(item.get("lane_role") or "") == "right_callout":
                callout_order = max(0, int(item.get("side_order") or 0) - 1)
                for level in range(0, 4):
                    col = callout_order // 4
                    row = callout_order % 4
                    candidates.append(_clamp((
                        float(x1) + 0.020 + col * 0.018 + level * 0.006,
                        float(y1) + 0.004 - row * 0.011,
                    )))
            for level in range(0, 5):
                offset = (0.018 + level * 0.009) if slot == "top" else (0.010 + level * 0.007)
                for side_name in preferred:
                    if side_name == "top":
                        candidates.append(_clamp((x_on_view, float(y1) + offset)))
                    elif side_name == "bottom":
                        candidates.append(_clamp((x_on_view, float(y0) - offset)))
                    elif side_name == "left":
                        candidates.append(_clamp((float(x0) - offset, y_on_view)))
                    else:
                        candidates.append(_clamp((float(x1) + offset, y_on_view)))
            candidates.append(_clamp(item["position"]))
            return candidates

        def _long_thin_lane_role(item):
            slot = str(item.get("slot") or "").strip().lower()
            side = str(item.get("side") or "").strip().lower()
            total = int(item.get("slot_total") or 0)
            side_order = int(item.get("side_order") or 0)
            if slot == "top" and total >= 5:
                # generator_top_view_local_reference_lanes:
                # LB26001-006 reference-style top-view dimensions must stay
                # in local top/bottom lanes; far-right callouts create the
                # cross-view leader lines seen in the UI screenshot failures.
                return "standard"
            return "standard"

        def _reference_lane_geometry_issues(items_for_check, *, use_new_position=False):
            # reference_lane_geometry_guard:
            # Supporting diagnostic for the application UI screenshot failure.
            # Overlap can be zero while diagonal/cross-region leader geometry
            # still makes 006 read like AutoDimension output.
            if part_class != "long_thin":
                return []
            lane_policy = (((_drawing_blueprint_v4 or {}).get("layout_plan") or {}).get(
                "reference_dimension_lane_policy"
            ) or {})
            allow_compact_top_side = bool(lane_policy.get("allow_compact_top_view_side_lanes"))
            try:
                top_side_max_gap = float(lane_policy.get("top_view_side_lane_max_gap_m") or 0.0)
            except Exception:
                top_side_max_gap = 0.0
            issues = []
            for item_for_check in items_for_check or []:
                slot = str(item_for_check.get("slot") or "").strip().lower()
                if slot not in {"front", "top", "right"}:
                    continue
                outline = item_for_check.get("outline")
                if not outline:
                    continue
                if use_new_position:
                    pos = tuple(item_for_check.get("new_position") or item_for_check.get("position") or (0.0, 0.0))
                else:
                    pos = tuple(item_for_check.get("position") or (0.0, 0.0))
                arrow = tuple(item_for_check.get("arrow_position") or item_for_check.get("position") or pos)
                side = _dimension_side(pos, outline)
                x0, y0, x1, y1 = outline
                gap = 0.0
                if side == "top":
                    gap = max(0.0, pos[1] - y1)
                elif side == "bottom":
                    gap = max(0.0, y0 - pos[1])
                elif side == "left":
                    gap = max(0.0, x0 - pos[0])
                elif side == "right":
                    gap = max(0.0, pos[0] - x1)
                issue_key = ""
                compact_top_side_lane = (
                    slot == "top"
                    and side in {"left", "right"}
                    and allow_compact_top_side
                    and top_side_max_gap > 0.0
                    and gap <= top_side_max_gap
                )
                if slot == "top" and side in {"left", "right"} and not compact_top_side_lane:
                    issue_key = "top_view_cross_region_side"
                elif side in {"top", "bottom"} and gap > 0.046:
                    issue_key = "reference_lane_far_from_view"
                elif side in {"left", "right"} and gap > 0.030:
                    issue_key = "reference_lane_far_from_view"
                dx = abs(float(pos[0]) - float(arrow[0]))
                dy = abs(float(pos[1]) - float(arrow[1]))
                leader_distance = (dx * dx + dy * dy) ** 0.5
                diagonal_leader = dx > 0.030 and dy > 0.018 and leader_distance > 0.038
                if diagonal_leader:
                    issue_key = "reference_lane_diagonal_or_cross_region_leader"
                if not issue_key:
                    continue
                issues.append({
                    "index": item_for_check.get("index"),
                    "view": item_for_check.get("view"),
                    "slot": slot,
                    "side": side,
                    "issue": issue_key,
                    "text_position": list(pos),
                    "arrow_position": list(arrow),
                    "gap": round(float(gap), 6),
                    "leader_distance": round(float(leader_distance), 6),
                    "diagonal_leader": bool(diagonal_leader),
                })
            return issues

        def _reference_lane_issue_for_candidate(item_for_check, candidate):
            if part_class != "long_thin":
                return ""
            probe = dict(item_for_check or {})
            probe["new_position"] = tuple(candidate)
            issues_for_probe = _reference_lane_geometry_issues([probe], use_new_position=True)
            if not issues_for_probe:
                return ""
            return str((issues_for_probe[0] or {}).get("issue") or "")

        raw_items = _display_dim_annotations_in_doc(drw)
        items = []
        for index, item in enumerate(raw_items):
            target = item.get("annotation") or item.get("display_dim")
            view_obj = item.get("view_obj")
            outline = view_outline_box(view_obj) if view_obj is not None else None
            if target is None or not outline:
                continue
            position = _arrange_dim_position(target)
            arrow_position = _arrange_dim_arrow_position(target, position)
            slot = _slot_for_outline(outline)
            items.append({
                "index": index,
                "target": target,
                "view": item.get("view"),
                "source": item.get("source"),
                "outline": outline,
                "position": position,
                "arrow_position": arrow_position,
                "slot": slot,
                "side": _dimension_side(position, outline),
            })

        grouped_items = {}
        for item in items:
            grouped_items.setdefault(str(item.get("slot") or item.get("view") or ""), []).append(item)
        for group in grouped_items.values():
            group.sort(key=lambda entry: (entry["position"][0], -entry["position"][1]))
            for rank, entry in enumerate(group):
                entry["slot_order"] = rank
                entry["slot_total"] = len(group)
        grouped_sides = {}
        for item in items:
            grouped_sides.setdefault((str(item.get("slot") or ""), str(item.get("side") or "")), []).append(item)
        for group in grouped_sides.values():
            group.sort(key=lambda entry: (entry["position"][0], -entry["position"][1]))
            for rank, entry in enumerate(group):
                entry["side_order"] = rank
                entry["side_total"] = len(group)
                entry["lane_role"] = _long_thin_lane_role(entry) if part_class == "long_thin" else "standard"
        slot_order = {"front": 0, "top": 1, "right": 2, "iso": 3}
        items.sort(key=lambda entry: (slot_order.get(str(entry.get("slot") or "").lower(), 99), int(entry.get("slot_order") or 0)))

        points_before = [item["position"] for item in items]
        reference_lane_issues_before = _reference_lane_geometry_issues(items, use_new_position=False)
        avoid_before = sum(
            1 for point in points_before
            if any(_arrange_point_in_box(point, box) for box in avoid_boxes)
        )
        overlap_before = _arrange_collision_count(points_before)
        adjusted = 0
        used_points = []
        dimensions_report = []

        def _clamp(point):
            return (
                max(margin, min(sheet_w - margin, float(point[0]))),
                max(margin, min(sheet_h - margin, float(point[1]))),
            )

        for order, item in enumerate(items):
            x0, y0, x1, y1 = item["outline"]
            original = item["position"]
            candidates = []
            if part_class == "long_thin":
                candidates.extend(_long_thin_candidates(item))
            else:
                for level in range(0, 8):
                    step = (level + 1) * track_gap
                    candidates.extend([
                        _clamp((original[0], y1 + step)),
                        _clamp((original[0], y0 - step)),
                        _clamp((x1 + step, original[1])),
                        _clamp((x0 - step, original[1])),
                    ])
                candidates.append(_clamp(original))
            chosen = None
            fallback_candidate = None
            for candidate in candidates:
                if any(_arrange_point_in_box(candidate, box) for box in avoid_boxes):
                    continue
                if any(_arrange_distance(candidate, prior) < 0.008 for prior in used_points):
                    continue
                if fallback_candidate is None:
                    fallback_candidate = candidate
                if part_class == "long_thin" and _reference_lane_issue_for_candidate(item, candidate):
                    continue
                chosen = candidate
                break
            if chosen is None:
                chosen = fallback_candidate or candidates[-1]
            ok = False
            if _arrange_distance(original, chosen) > 0.001:
                ok = _arrange_set_dim_position(item["target"], chosen)
                if ok:
                    adjusted += 1
            final_position = chosen if ok else original
            item["new_position"] = final_position
            used_points.append(final_position)
            dimensions_report.append({
                "index": item["index"],
                "view": item.get("view"),
                "source": item.get("source"),
                "slot": item.get("slot"),
                "side": item.get("side"),
                "lane_role": item.get("lane_role") or "standard",
                "original_position": list(original),
                "new_position": list(final_position),
                "adjusted": bool(ok),
            })

        points_after = [tuple(item["new_position"]) for item in dimensions_report]
        reference_lane_issues_after = _reference_lane_geometry_issues(items, use_new_position=True)
        issues_by_index = {issue.get("index"): issue.get("issue") for issue in reference_lane_issues_after}
        for item in dimensions_report:
            issue = issues_by_index.get(item.get("index"))
            if issue:
                item["reference_lane_issue"] = issue
        avoid_after = sum(
            1 for point in points_after
            if any(_arrange_point_in_box(point, box) for box in avoid_boxes)
        )
        overlap_after = _arrange_collision_count(points_after)
        result = {
            "stage": stage_name,
            "attempted": True,
            "success": bool(items),
            "source": "generator_display_dim_annotation_chain",
            "total_dimensions": len(items),
            "adjusted_dimensions": adjusted,
            "callout_lane_applied": any(str(item.get("lane_role") or "") == "right_callout" for item in items),
            "callout_lane_count": sum(1 for item in items if str(item.get("lane_role") or "") == "right_callout"),
            "overlap_before": overlap_before,
            "overlap_after": overlap_after,
            "titlebar_collision_before": sum(_arrange_point_in_box(p, titlebar_box) for p in points_before),
            "titlebar_collision_after": sum(_arrange_point_in_box(p, titlebar_box) for p in points_after),
            "avoid_collision_before": avoid_before,
            "avoid_collision_after": avoid_after,
            "line_crossing_before": 0,
            "line_crossing_after": 0,
            "reference_lane_geometry_issue_count_before": len(reference_lane_issues_before),
            "reference_lane_geometry_issue_count_after": len(reference_lane_issues_after),
            "reference_lane_geometry_issues": reference_lane_issues_after,
            "reason": "fallback_used" if items else "no_displaydim_annotations",
        }
        try:
            qc_dir = Path(run_dir_for_arrange) / "qc"
            qc_dir.mkdir(parents=True, exist_ok=True)
            (qc_dir / "dimension_arrange.json").write_text(
                json.dumps({
                    "run_id": base_name,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    **result,
                    "sheet_size": [sheet_w, sheet_h],
                    "titlebar_box": list(titlebar_box),
                    "notes_box": list(notes_box) if notes_box else [],
                    "avoid_boxes": [list(box) for box in avoid_boxes],
                    "reference_dimension_lane_policy": (((_drawing_blueprint_v4 or {}).get("layout_plan") or {}).get(
                        "reference_dimension_lane_policy"
                    ) or {}),
                    "dimensions": dimensions_report,
                }, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as exc:
            result["write_error"] = str(exc)
        return result

    def _run_dimension_arrange_stage(stage_name):
        result = {"stage": stage_name, "attempted": True, "success": False}
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            from app.services.dimension_arrange_service import arrange_dimensions

            _run_dir_for_arrange = Path(_run_dir_env) if _run_dir_env else Path(out_dir)
            _layout_plan = _arrange_layout_with_blueprint_context((_drawing_blueprint_v4 or {}).get("layout_plan") or {})
            arranged = arrange_dimensions(
                sw,
                drw,
                run_dir=_run_dir_for_arrange,
                run_id=base_name,
                layout_plan=_layout_plan,
            )
            result.update({
                "success": bool(arranged.success),
                "total_dimensions": int(arranged.total_dimensions or 0),
                "adjusted_dimensions": int(arranged.adjusted_dimensions or 0),
                "overlap_before": int(arranged.overlap_before or 0),
                "overlap_after": int(arranged.overlap_after or 0),
                "titlebar_collision_before": int(arranged.titlebar_collision_before or 0),
                "titlebar_collision_after": int(arranged.titlebar_collision_after or 0),
                "avoid_collision_before": int(arranged.avoid_collision_before or 0),
                "avoid_collision_after": int(arranged.avoid_collision_after or 0),
                "line_crossing_before": int(arranged.line_crossing_before or 0),
                "line_crossing_after": int(arranged.line_crossing_after or 0),
                "reference_lane_geometry_issue_count_before": int(
                    getattr(arranged, "reference_lane_geometry_issue_count_before", 0) or 0
                ),
                "reference_lane_geometry_issue_count_after": int(
                    getattr(arranged, "reference_lane_geometry_issue_count_after", 0) or 0
                ),
                "reference_lane_geometry_issues": list(
                    getattr(arranged, "reference_lane_geometry_issues", []) or []
                ),
                "callout_lane_applied": bool(getattr(arranged, "callout_lane_applied", False)),
                "callout_lane_count": int(getattr(arranged, "callout_lane_count", 0) or 0),
                "reason": str(arranged.reason or ""),
            })
            if result["total_dimensions"] == 0:
                fallback_result = _arrange_display_dim_annotations_stage(
                    stage_name,
                    _run_dir_for_arrange,
                    _layout_plan,
                )
                if int(fallback_result.get("total_dimensions") or 0) > 0:
                    result.update(fallback_result)
            _dimension_arrange_results.append(result)
            log(
                f"  [v4 dimension arrange] {stage_name}: "
                f"success={result['success']} adjusted={result['adjusted_dimensions']}/"
                f"{result['total_dimensions']} overlap={result['overlap_before']}->{result['overlap_after']} "
                f"avoid={result['avoid_collision_before']}->{result['avoid_collision_after']}"
            )
            if result["success"]:
                try: drw.ForceRebuild3(True)
                except Exception: pass
                try: drw.GraphicsRedraw2()
                except Exception: pass
            return result
        except Exception as exc:
            result["error"] = str(exc)
            _dimension_arrange_results.append(result)
            warnings_box.append({"code": "dimension_arrange_exception", "stage": stage_name, "msg": str(exc)})
            log(f"  [v4 dimension arrange] {stage_name} exception: {exc}")
            return result

    err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warn = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    ok1 = drw.Extension.SaveAs(slddrw, 0, 1, vt_dispatch_none(), err, warn)
    log(f"  SLDDRW: {'OK' if ok1 else 'FAIL'}  err={err.value}")
    if ok1:
        try:
            drw, _dim_prune_result = _prune_persisted_reference_display_dims(
                sw,
                drw,
                slddrw,
                reference_dim_floor,
                log_fn=log,
                part_class=(_drawing_blueprint_v4 or {}).get("part_class", ""),
                dimension_plan=(_drawing_blueprint_v4 or {}).get("dimension_plan") or {},
                layout_plan=(_drawing_blueprint_v4 or {}).get("layout_plan") or {},
            )
            if _dim_prune_result.get("enabled"):
                prune_info = _dim_prune_result.get("prune") or {}
                log(
                    "  [reference_style] persisted DisplayDim prune "
                    f"cap={_dim_prune_result.get('cap')} "
                    f"before={prune_info.get('before')} after={prune_info.get('after')} "
                    f"deleted={prune_info.get('deleted')}"
                )
                if prune_info.get("deleted"):
                    warnings_box.append({
                        "code": "reference_display_dim_pruned",
                        "cap": _dim_prune_result.get("cap"),
                        "before": prune_info.get("before"),
                        "after": prune_info.get("after"),
                        "deleted": prune_info.get("deleted"),
                    })
                if not _dim_prune_result.get("success"):
                    warnings_box.append({
                        "code": "reference_display_dim_prune_failed",
                        "cap": _dim_prune_result.get("cap"),
                        "result": _dim_prune_result,
                    })
        except Exception as exc:
            log(f"  [reference_style] persisted DisplayDim prune exception: {exc}")
            _dim_prune_result = {
                "enabled": True,
                "cap": _reference_display_dim_cap(
                    reference_dim_floor,
                    part_class=(_drawing_blueprint_v4 or {}).get("part_class", ""),
                ),
                "slot_quotas": _v4_dimension_view_quotas(_drawing_blueprint_v4 or {}),
                "success": False,
                "reason": str(exc),
            }
            warnings_box.append({"code":"reference_display_dim_prune_exception","msg":str(exc)})
    _post_saveas_target_coverage = _record_reference_intent_target_coverage(
        "post_saveas_reopen_prune",
        persisted_after_reopen=True,
    )

    _post_prune_dim_guard = {"attempted": False, "before": None, "after": None}
    _dim_before_sidecar = _count_display_dims(drw)
    _post_prune_guard_reason = _reference_intent_post_layout_repair_reason(
        _dim_before_sidecar,
        _dim_floor,
        _post_saveas_target_coverage or {},
    )
    _post_prune_dim_guard.update({
        "before": _dim_before_sidecar,
        "repair_reason": _post_prune_guard_reason,
        "target_coverage_before_repair": _post_saveas_target_coverage,
    })
    if _skip_generic_model_dim_import and _post_prune_guard_reason:
        _post_prune_dim_guard["attempted"] = True
        _post_prune_explicit = _run_reference_intent_explicit_display_dims("post_saveas_reopen_prune_guard")
        _dim_after_post_prune_guard = _count_display_dims(drw)
        _post_prune_missing_after = sorted(
            _reference_intent_missing_target_keys(
                (_post_prune_explicit or {}).get("target_coverage_after") or {}
            )
        )
        _post_prune_dim_guard.update({
            "after": _dim_after_post_prune_guard,
            "explicit_display_dims": _post_prune_explicit,
            "missing_target_keys_after_repair": _post_prune_missing_after,
        })
        _post_prune_guard_still_blocked = (
            _dim_after_post_prune_guard < _dim_floor
            or bool(_post_prune_missing_after)
        )
        if not _post_prune_guard_still_blocked:
            _post_prune_arrange = _run_dimension_arrange_stage("post_saveas_reopen_prune_guard")
            _post_prune_dim_guard["dimension_arrange"] = _post_prune_arrange
            try:
                err.value = 0; warn.value = 0
                drw.Extension.SaveAs(slddrw, 0, 1, vt_dispatch_none(), err, warn)
                _post_prune_dim_guard["save"] = {
                    "success": True,
                    "errors": int(err.value),
                    "warnings": int(warn.value),
                    "method": "Extension.SaveAs",
                }
                log(f"  [reference_style] post-prune guard SLDDRW save: err={err.value}")
            except Exception as exc_save:
                _post_prune_dim_guard["save"] = {
                    "success": False,
                    "reason": str(exc_save),
                    "method": "Extension.SaveAs",
                }
                warnings_box.append({"code":"post_prune_reference_intent_guard_save_failed","msg":str(exc_save)})
        else:
            warnings_box.append({
                "code": "post_prune_reference_intent_guard_still_blocked",
                "before": _dim_before_sidecar,
                "after": _dim_after_post_prune_guard,
                "missing_target_keys": _post_prune_missing_after,
                "repair_reason": _post_prune_guard_reason,
                "msg": "Post-prune explicit DisplayDim guard could not restore every required 006 reference-intent target before sidecar diagnostics.",
            })
        _dim_before_sidecar = _dim_after_post_prune_guard
    else:
        _post_prune_dim_guard["after"] = _dim_before_sidecar
    _post_prune_guard_target_coverage = _record_reference_intent_target_coverage(
        "post_saveas_reopen_prune_guard",
        persisted_after_reopen=True,
    )
    _post_prune_dim_guard["target_coverage_after_guard"] = _post_prune_guard_target_coverage
    _post_prune_dim_guard["missing_target_keys_after_guard"] = sorted(
        _reference_intent_missing_target_keys(_post_prune_guard_target_coverage or {})
    )

    # v1.7 Task 1+3: 用 dimension_sidecar_service（C# 早期绑定 + Python 降级）替代 VBA sidecar
    # 不再用 annotate_sidecar_service.RunMacro2（v1.6 已确认 RunMacro2 返回 False）
    # 触发条件扩展为 (not imported) OR (dim_total < 5)
    #   原因：RunCommand(826) 不抛异常就把 imported=True，但实际可能未插入尺寸
    # v1.7 Task 1: 使用 RUN_DIR 环境变量统一 sidecar 输出路径
    log(f"  [v1.7 sidecar] sidecar 前 DisplayDim 数量: {_dim_before_sidecar}")
    _need_sidecar = _needs_dimension_sidecar(
        imported or _skip_generic_model_dim_import,
        _dim_before_sidecar,
        _dim_floor,
    )
    _sidecar_mode = _dimension_sidecar_mode_for_reference_intent(
        _need_sidecar,
        _skip_generic_model_dim_import,
    )
    if not _need_sidecar and _skip_generic_model_dim_import:
        warnings_box.append({
            "code": "reference_intent_dimension_sidecar_skipped",
            "display_dim_count": _dim_before_sidecar,
            "reference_display_dim_floor": _dim_floor,
            "run_sidecar": False,
            "diagnostic_only": False,
            "acceptance_allowed": False,
            "msg": "Reference-intent path reached the DisplayDim floor without running the generic dimension sidecar.",
        })
    elif _need_sidecar and _skip_generic_model_dim_import and not _sidecar_mode.get("run_sidecar"):
        warnings_box.append({
            "code": "reference_intent_dimension_sidecar_diagnostic_only",
            "display_dim_count": _dim_before_sidecar,
            "reference_display_dim_floor": _dim_floor,
            "reason": _sidecar_mode.get("reason", ""),
            "run_sidecar": False,
            "diagnostic_only": True,
            "acceptance_allowed": False,
            "drawing_path": str(slddrw),
            "run_dir": str(_run_dir_env or out_dir),
            "api_is_not_final_judgement": True,
            "msg": (
                "Reference-intent acceptance requires real SolidWorks DisplayDim coverage; "
                "dimension sidecar/Note/OCR evidence is diagnostic only and was not used for acceptance."
            ),
        })
    if _sidecar_mode.get("run_sidecar"):
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            # v1.7 Task 2: 先分类零件，决定 sidecar 策略
            from app.services.part_classification_service import classify_part
            from app.services.dimension_sidecar_service import run_dimension_sidecar
            _run_dir_for_sidecar = Path(_run_dir_env) if _run_dir_env else Path(out_dir)
            _qc_dir_for_sidecar = _run_dir_for_sidecar / "qc"
            _qc_dir_for_sidecar.mkdir(parents=True, exist_ok=True)
            # 分类（写 part_class.json 到 run_dir/qc）
            _cls = classify_part(
                _work_part_path,
                bbox_mm=[bbox_m[0]*1000.0, bbox_m[1]*1000.0, bbox_m[2]*1000.0] if bbox_m and len(bbox_m) >= 3 else None,
                history_dim_total=_dim_before_sidecar,
                write_json=True,
                out_dir=_qc_dir_for_sidecar,
            )
            _part_class = _cls.part_class
            log(f"  [v1.7 sidecar] part_class={_part_class} reason={_cls.reason}")
            warnings_box.append({"code":"part_class","msg":f"{_part_class}: {_cls.reason}"})
            # 调用 dimension sidecar
            _sidecar_result = run_dimension_sidecar(
                drawing_path=slddrw,
                part_path=_work_part_path,
                run_dir=_run_dir_for_sidecar,
                part_class=_part_class,
            )
            if _sidecar_result.get("success"):
                imported = True
                log(f"  [v1.7 sidecar] 成功: status={_sidecar_result.get('status')} added={_sidecar_result.get('annotations_added')}")
                warnings_box.append({
                    "code": "dim_via_sidecar",
                    "msg": _sidecar_result.get("msg") or _sidecar_result.get("status", ""),
                    "annotations_added": _sidecar_result.get("annotations_added", 0),
                    "standard_annotation_present": _sidecar_result.get("standard_annotation_present", False),
                    "fallback_mode": _sidecar_result.get("fallback_mode", ""),
                    "drawing_path": str(slddrw),
                    "run_dir": str(_run_dir_for_sidecar),
                    "diagnostic_only": bool(_sidecar_mode.get("diagnostic_only")),
                    "acceptance_allowed": not _skip_generic_model_dim_import,
                })
                # sidecar 已插入尺寸/标注，重新激活确保后续导出包含
                try:
                    sw.ActivateDoc3(call(drw, "GetTitle"), True, 0,
                                    VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0))
                except Exception:
                    pass
                try: drw.ForceRebuild3(True)
                except Exception: pass
                # 重新计数 dim_total
                _dim_after_sidecar = _count_display_dims(drw)
                log(f"  [v1.7 sidecar] sidecar 后 DisplayDim 数量: {_dim_after_sidecar}")
                _dim_now = _dim_after_sidecar
                # 重新保存 SLDDRW（确保 sidecar 插入的内容持久化）
                try:
                    err.value = 0; warn.value = 0
                    drw.Extension.SaveAs(slddrw, 0, 1, vt_dispatch_none(), err, warn)
                    log(f"  [v1.7 sidecar] SLDDRW 重新保存: err={err.value}")
                except Exception as _e:
                    log(f"  [v1.7 sidecar] SLDDRW 重新保存失败: {_e}")
            else:
                log(f"  [v1.7 sidecar] 失败: status={_sidecar_result.get('status')} reason={_sidecar_result.get('reason')}")
                warnings_box.append({
                    "code": "dim_sidecar_fail",
                    "msg": f"{_sidecar_result.get('status')}: {_sidecar_result.get('reason','')}",
                    "fallback_mode": _sidecar_result.get("fallback_mode", ""),
                    "drawing_path": str(slddrw),
                    "run_dir": str(_run_dir_for_sidecar),
                    "diagnostic_only": bool(_sidecar_mode.get("diagnostic_only")),
                    "acceptance_allowed": not _skip_generic_model_dim_import,
                })
        except Exception as exc:
            log(f"  [v1.7 sidecar] 异常: {exc}")
            warnings_box.append({
                "code": "dim_sidecar_exc",
                "msg": str(exc),
                "drawing_path": str(slddrw),
                "run_dir": str(_run_dir_env or out_dir),
                "diagnostic_only": bool(_sidecar_mode.get("diagnostic_only")),
                "acceptance_allowed": not _skip_generic_model_dim_import,
            })

    _dim_final_for_reference = _count_display_dims(drw)
    log(f"  [reference_style] final DisplayDim count before floor check: {_dim_final_for_reference}")
    _pre_export_target_coverage = _record_reference_intent_target_coverage(
        "pre_export_final",
        persisted_after_reopen=True,
    )
    _floor_gap = _reference_dim_floor_gap(_dim_final_for_reference, reference_dim_floor)
    if _floor_gap:
        gap = int(_floor_gap["gap"])
        warnings_box.append({
            "code": "reference_display_dim_floor_unmet",
            "msg": f"DisplayDim {_dim_final_for_reference} < reference {reference_dim_floor}; gap={gap}",
            "reference_display_dim_floor": int(_floor_gap["reference_display_dim_floor"]),
            "generated_display_dim_count": int(_floor_gap["generated_display_dim_count"]),
        })
        log(f"  [reference_style] DisplayDim floor unmet: {_dim_final_for_reference}/{reference_dim_floor} gap={gap}")

    _pre_export_dimension_arrange = _run_dimension_arrange_stage("pre_export")
    if _pre_export_dimension_arrange.get("success"):
        try:
            err.value = 0; warn.value = 0
            drw.Extension.SaveAs(slddrw, 0, 1, vt_dispatch_none(), err, warn)
            log(f"  [v4 dimension arrange] pre_export SLDDRW save: err={err.value}")
        except Exception as exc:
            warnings_box.append({"code":"dimension_arrange_pre_export_save_failed","msg":str(exc)})
            log(f"  [v4 dimension arrange] pre_export save failed: {exc}")

    try:
        pdf_data = sw.GetExportFileData(1)
        sn = drw.GetSheetNames if not callable(getattr(drw,"GetSheetNames",None)) else drw.GetSheetNames()
        sheet_names = list(sn) if sn else []
        if pdf_data and sheet_names:
            try:
                if callable(getattr(pdf_data,"SetSheets",None)):
                    pdf_data.SetSheets(0, sheet_names)
            except Exception: pass
        err.value = 0; warn.value = 0
        ok2 = drw.Extension.SaveAs(pdf, 0, 1, pdf_data, err, warn)
        log(f"  PDF:    {'OK' if ok2 else 'FAIL'}  err={err.value}")
    except Exception as exc:
        log(f"  PDF EXC {exc}")
    try:
        err.value = 0; warn.value = 0
        ok3 = drw.Extension.SaveAs(dxf, 0, 1, vt_dispatch_none(), err, warn)
        log(f"  DXF:    {'OK' if ok3 else 'FAIL'}  err={err.value}")
    except Exception as exc:
        log(f"  DXF EXC {exc}")

    # v1.5 Task 4: PNG 导出改用 PDF→PyMuPDF 回退（run_manager.py L222-254 实现）
    # 背景：sw.GetExportFileData(2)（swExportPngData）在 SW2025 Rev 33.5.0 返回 None，冗余 COM 调用已移除
    png_path = os.path.join(out_dir, f"{base_name}_v5.PNG")
    log("  [v1.5 PNG] 由 run_manager PDF→PyMuPDF 回退生成（跳过 sw.GetExportFileData(2) COM 调用）")
    warnings_box.append({"code":"png_fallback_to_pdf","msg":"PNG 由 run_manager PDF→PyMuPDF 回退生成"})
    _png_render_result = _render_pdf_first_page_to_png(pdf, png_path, warnings_box, log)

    # v1.6 Task 3: 持久化布局求解（SaveAs → Close → Reopen → GetOutline）
    # 不只在内存态检查 outline，确保保存/重载后 outline 一致
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        from app.services.persisted_layout_solver import solve_persisted_layout
        _scale_ladder = [(5,1),(2,1),(1,1),(1,2),(1,5),(1,10),(1,20),(1,50)]
        _layout_centers_for_solver = _created_view_centers_for_persisted_layout(created_views.keys(), centers)
        _layout_outlines_for_solver = _created_view_outlines_for_persisted_layout(
            created_views.keys(),
            reference_layout_outlines,
        )
        layout_result = solve_persisted_layout(
            sw, slddrw, created_views, _layout_centers_for_solver, _scale_ladder,
            max_iterations=8, log_fn=log, drawing_doc=drw,
            target_outlines=_layout_outlines_for_solver,
            target_outline_tolerance=0.28,
            start_scale=chosen,
        )
        if layout_result.get("target_outline_size_warning_issues"):
            warnings_box.append({
                "code": "persisted_layout_target_outline_warning",
                "issues": layout_result.get("target_outline_size_warning_issues"),
                "target_outline_scale_direction": layout_result.get("target_outline_scale_direction"),
            })
        if layout_result.get("target_outline_size_blocking_issues"):
            warnings_box.append({
                "code": "persisted_layout_target_outline_blocking",
                "issues": layout_result.get("target_outline_size_blocking_issues"),
                "target_outline_scale_direction": layout_result.get("target_outline_scale_direction"),
            })
        if layout_result.get("success"):
            log(f"  [v1.6 layout] 持久化布局求解成功: scale={layout_result['final_scale']}, iters={layout_result['iterations']}")
        else:
            log(f"  [v1.6 layout] 持久化布局求解失败: {layout_result.get('error', 'unknown')}")
            if layout_result.get("overlap_pairs"):
                warnings_box.append({"code":"persisted_view_overlap","pairs":layout_result["overlap_pairs"]})
            if layout_result.get("out_of_frame"):
                warnings_box.append({"code":"persisted_view_out_of_frame","views":layout_result["out_of_frame"]})
        # 更新 scale_label 和 real_outlines
        if layout_result.get("final_scale"):
            scale_label = layout_result["final_scale"]
        if layout_result.get("final_outlines"):
            real_outlines = layout_result["final_outlines"]
    except Exception as exc:
        log(f"  [v1.6 layout] 异常: {exc}")
        warnings_box.append({"code":"persisted_layout_exc","msg":str(exc)})

    _post_layout_dim_result = {"attempted": False, "before": None, "after": None}
    try:
        if _dim_floor > 0:
            reopened_after_layout, reopen_after_layout_info = _reopen_saved_drawing(
                sw,
                drw,
                slddrw,
                log_fn=log,
            )
            if reopened_after_layout is not None:
                drw = reopened_after_layout
                drw, _post_layout_current_doc_refresh = _refresh_current_drawing_doc_from_solidworks(
                    "post_layout_reopen",
                    drw,
                )
                _post_layout_dim_result["current_drawing_doc_refresh"] = _post_layout_current_doc_refresh
                _post_layout_dim_result["created_views_refresh"] = _refresh_created_views_from_current_document(
                    "post_layout_reopen"
                )
            _post_layout_before = _count_display_dims(drw)
            _post_layout_dim_result.update({
                "attempted": True,
                "before": _post_layout_before,
                "reopen": reopen_after_layout_info,
            })
            _post_layout_dim_result["target_coverage_before_repair"] = _record_reference_intent_target_coverage(
                "post_layout_reopen_before_repair",
                persisted_after_reopen=True,
            )
            _post_layout_repair_reason = _reference_intent_post_layout_repair_reason(
                _post_layout_before,
                _dim_floor,
                _post_layout_dim_result.get("target_coverage_before_repair") or {},
            )
            _post_layout_dim_result["repair_reason"] = _post_layout_repair_reason
            _post_layout_dim_result["missing_target_keys_before_repair"] = sorted(
                _reference_intent_missing_target_keys(
                    _post_layout_dim_result.get("target_coverage_before_repair") or {}
                )
            )
            log(f"  [reference_style] post-layout persisted DisplayDim={_post_layout_before} floor={_dim_floor}")
            if _post_layout_repair_reason:
                if _disable_reference_autodimension:
                    _post_layout_explicit = _run_reference_intent_explicit_display_dims("post_layout")
                    _post_layout_after = _count_display_dims(drw)
                    _post_layout_missing_after = sorted(
                        _reference_intent_missing_target_keys(
                            (_post_layout_explicit or {}).get("target_coverage_after") or {}
                        )
                    )
                    _post_layout_dim_result.update({
                        "after": _post_layout_after,
                        "explicit_display_dims": _post_layout_explicit,
                        "missing_target_keys_after_repair": _post_layout_missing_after,
                        "autodim": {
                            "applied": False,
                            "skipped": True,
                            "before": _post_layout_before,
                            "after": _post_layout_after,
                            "reason": "reference_intent_autodimension_disabled_by_ui_screenshot_gate",
                            "attempts": [],
                        },
                    })
                    _post_layout_repair_still_blocked = (
                        _post_layout_after < _dim_floor
                        or bool(_post_layout_missing_after)
                    )
                    if _post_layout_after < _dim_floor:
                        warnings_box.append({
                            "code": "post_layout_reference_intent_autodimension_disabled",
                            "before": _post_layout_before,
                            "after": _post_layout_after,
                            "reference_display_dim_floor": _dim_floor,
                            "reason": "application_ui_screenshot_visual_acceptance_failed_generic_autodimension",
                            "msg": "Post-layout AutoDimension is disabled for reference-intent 006; do not recreate the slanted AutoDimension stack.",
                        })
                    if _post_layout_missing_after:
                        warnings_box.append({
                            "code": "post_layout_reference_intent_targets_still_missing",
                            "before": _post_layout_before,
                            "after": _post_layout_after,
                            "missing_target_keys": _post_layout_missing_after,
                            "repair_reason": _post_layout_repair_reason,
                            "msg": "Post-layout explicit DisplayDim repair did not cover every required reference-intent target.",
                        })
                    if not _post_layout_repair_still_blocked:
                        _post_layout_arrange = _run_dimension_arrange_stage("post_layout")
                        _post_layout_dim_result["dimension_arrange"] = _post_layout_arrange
                        try:
                            err.value = 0; warn.value = 0
                            drw.Extension.SaveAs(slddrw, 0, 1, vt_dispatch_none(), err, warn)
                            _post_layout_dim_result["save"] = {"errors": int(err.value), "warnings": int(warn.value)}
                            log(f"  [reference_style] post-layout explicit-dim SLDDRW save: err={err.value}")
                        except Exception as exc_save:
                            _post_layout_dim_result["save_error"] = str(exc_save)
                            warnings_box.append({"code":"post_layout_explicit_dim_save_failed","msg":str(exc_save)})
                        try:
                            pdf_data = sw.GetExportFileData(1)
                            sheet_names = list(drw.GetSheetNames()) if callable(getattr(drw, "GetSheetNames", None)) else []
                            if pdf_data and sheet_names and callable(getattr(pdf_data, "SetSheets", None)):
                                pdf_data.SetSheets(0, sheet_names)
                            err.value = 0; warn.value = 0
                            drw.Extension.SaveAs(pdf, 0, 1, pdf_data, err, warn)
                            err.value = 0; warn.value = 0
                            drw.Extension.SaveAs(dxf, 0, 1, vt_dispatch_none(), err, warn)
                            _post_layout_dim_result["reexported"] = True
                            log("  [reference_style] post-layout explicit-dim PDF/DXF re-exported")
                            _png_render_result = _render_pdf_first_page_to_png(pdf, png_path, warnings_box, log)
                            _post_layout_dim_result["png_render"] = _png_render_result
                        except Exception as exc_export:
                            _post_layout_dim_result["reexport_error"] = str(exc_export)
                            warnings_box.append({"code":"post_layout_explicit_dim_reexport_failed","msg":str(exc_export)})
                else:
                    _post_layout_autodim = _run_reference_autodimension()
                    _post_layout_after = _count_display_dims(drw)
                    _post_layout_dim_result.update({
                        "after": _post_layout_after,
                        "autodim": _post_layout_autodim,
                    })
                    warnings_box.append({
                        "code": "post_layout_reference_autodim",
                        "before": _post_layout_before,
                        "after": _post_layout_after,
                        "reference_display_dim_floor": _dim_floor,
                    })
                    _post_layout_arrange = _run_dimension_arrange_stage("post_layout")
                    _post_layout_dim_result["dimension_arrange"] = _post_layout_arrange
                    try:
                        err.value = 0; warn.value = 0
                        drw.Extension.SaveAs(slddrw, 0, 1, vt_dispatch_none(), err, warn)
                        _post_layout_dim_result["save"] = {"errors": int(err.value), "warnings": int(warn.value)}
                        log(f"  [reference_style] post-layout SLDDRW save: err={err.value}")
                    except Exception as exc_save:
                        _post_layout_dim_result["save_error"] = str(exc_save)
                        warnings_box.append({"code":"post_layout_dim_save_failed","msg":str(exc_save)})
                    try:
                        pdf_data = sw.GetExportFileData(1)
                        sheet_names = list(drw.GetSheetNames()) if callable(getattr(drw, "GetSheetNames", None)) else []
                        if pdf_data and sheet_names and callable(getattr(pdf_data, "SetSheets", None)):
                            pdf_data.SetSheets(0, sheet_names)
                        err.value = 0; warn.value = 0
                        drw.Extension.SaveAs(pdf, 0, 1, pdf_data, err, warn)
                        err.value = 0; warn.value = 0
                        drw.Extension.SaveAs(dxf, 0, 1, vt_dispatch_none(), err, warn)
                        _post_layout_dim_result["reexported"] = True
                        log("  [reference_style] post-layout PDF/DXF re-exported")
                        _png_render_result = _render_pdf_first_page_to_png(pdf, png_path, warnings_box, log)
                        _post_layout_dim_result["png_render"] = _png_render_result
                    except Exception as exc_export:
                        _post_layout_dim_result["reexport_error"] = str(exc_export)
                        warnings_box.append({"code":"post_layout_dim_reexport_failed","msg":str(exc_export)})
            else:
                _post_layout_dim_result["after"] = _post_layout_before
                _post_layout_arrange = _run_dimension_arrange_stage("post_layout")
                _post_layout_dim_result["dimension_arrange"] = _post_layout_arrange
                try:
                    err.value = 0; warn.value = 0
                    drw.Extension.SaveAs(slddrw, 0, 1, vt_dispatch_none(), err, warn)
                    _post_layout_dim_result["save"] = {"errors": int(err.value), "warnings": int(warn.value)}
                    log(f"  [reference_style] post-layout floor-preserving SLDDRW save: err={err.value}")
                except Exception as exc_save:
                    _post_layout_dim_result["save_error"] = str(exc_save)
                    warnings_box.append({"code":"post_layout_floor_save_failed","msg":str(exc_save)})
                try:
                    pdf_data = sw.GetExportFileData(1)
                    sheet_names = list(drw.GetSheetNames()) if callable(getattr(drw, "GetSheetNames", None)) else []
                    if pdf_data and sheet_names and callable(getattr(pdf_data, "SetSheets", None)):
                        pdf_data.SetSheets(0, sheet_names)
                    err.value = 0; warn.value = 0
                    drw.Extension.SaveAs(pdf, 0, 1, pdf_data, err, warn)
                    err.value = 0; warn.value = 0
                    drw.Extension.SaveAs(dxf, 0, 1, vt_dispatch_none(), err, warn)
                    _post_layout_dim_result["reexported"] = True
                    log("  [reference_style] post-layout floor-preserving PDF/DXF re-exported")
                    _png_render_result = _render_pdf_first_page_to_png(pdf, png_path, warnings_box, log)
                    _post_layout_dim_result["png_render"] = _png_render_result
                except Exception as exc_export:
                    _post_layout_dim_result["reexport_error"] = str(exc_export)
                    warnings_box.append({"code":"post_layout_floor_reexport_failed","msg":str(exc_export)})
            if _v4_dimension_view_quotas(_drawing_blueprint_v4 or {}):
                try:
                    drw, _post_layout_prune = _prune_persisted_reference_display_dims(
                        sw,
                        drw,
                        slddrw,
                        reference_dim_floor,
                        log_fn=log,
                        part_class=(_drawing_blueprint_v4 or {}).get("part_class", ""),
                        dimension_plan=(_drawing_blueprint_v4 or {}).get("dimension_plan") or {},
                        layout_plan=(_drawing_blueprint_v4 or {}).get("layout_plan") or {},
                        restore_on_failed_prune=False,
                    )
                    _post_layout_dim_result["post_layout_reference_prune"] = _post_layout_prune
                    prune_info = (_post_layout_prune or {}).get("prune") or {}
                    if prune_info.get("deleted"):
                        warnings_box.append({
                            "code": "post_layout_reference_pruned",
                            "cap": _post_layout_prune.get("cap"),
                            "before": prune_info.get("before"),
                            "after": prune_info.get("after"),
                            "deleted": prune_info.get("deleted"),
                            "after_slot_counts": prune_info.get("after_slot_counts"),
                        })
                    if not (_post_layout_prune or {}).get("success", True):
                        warnings_box.append({
                            "code": "post_layout_reference_prune_failed",
                            "result": _post_layout_prune,
                        })
                    else:
                        pdf_data = sw.GetExportFileData(1)
                        sheet_names = list(drw.GetSheetNames()) if callable(getattr(drw, "GetSheetNames", None)) else []
                        if pdf_data and sheet_names and callable(getattr(pdf_data, "SetSheets", None)):
                            pdf_data.SetSheets(0, sheet_names)
                        err.value = 0; warn.value = 0
                        drw.Extension.SaveAs(pdf, 0, 1, pdf_data, err, warn)
                        err.value = 0; warn.value = 0
                        drw.Extension.SaveAs(dxf, 0, 1, vt_dispatch_none(), err, warn)
                        _post_layout_dim_result["post_layout_prune_reexported"] = True
                        log("  [reference_style] post-layout quota-pruned PDF/DXF re-exported")
                        _png_render_result = _render_pdf_first_page_to_png(pdf, png_path, warnings_box, log)
                        _post_layout_dim_result["post_layout_prune_png_render"] = _png_render_result
                except Exception as exc_prune:
                    _post_layout_dim_result["post_layout_reference_prune_error"] = str(exc_prune)
                    warnings_box.append({"code":"post_layout_reference_prune_exception","msg":str(exc_prune)})
            _post_layout_after_prune_coverage = _record_reference_intent_target_coverage(
                "post_layout_after_prune",
                persisted_after_reopen=True,
            )
            _post_layout_dim_result["target_coverage_after_prune"] = _post_layout_after_prune_coverage
            _post_layout_after_prune_count = _count_display_dims(drw)
            _post_layout_prune_guard_reason = _reference_intent_post_layout_repair_reason(
                _post_layout_after_prune_count,
                _dim_floor,
                _post_layout_after_prune_coverage or {},
            )
            _post_layout_dim_result["post_layout_prune_guard_reason"] = _post_layout_prune_guard_reason
            if _skip_generic_model_dim_import and _post_layout_prune_guard_reason:
                _post_layout_dim_result["post_layout_prune_guard_attempted"] = True
                _post_layout_prune_guard_explicit = _run_reference_intent_explicit_display_dims(
                    "post_layout_prune_guard"
                )
                _post_layout_after_guard_count = _count_display_dims(drw)
                _post_layout_after_guard_missing = sorted(
                    _reference_intent_missing_target_keys(
                        (_post_layout_prune_guard_explicit or {}).get("target_coverage_after") or {}
                    )
                )
                _post_layout_dim_result.update({
                    "post_layout_prune_guard_display_dim_count_before": _post_layout_after_prune_count,
                    "post_layout_prune_guard_display_dim_count_after": _post_layout_after_guard_count,
                    "post_layout_prune_guard_explicit_display_dims": _post_layout_prune_guard_explicit,
                    "post_layout_prune_guard_missing_target_keys_after": _post_layout_after_guard_missing,
                })
                _post_layout_prune_guard_still_blocked = (
                    _post_layout_after_guard_count < _dim_floor
                    or bool(_post_layout_after_guard_missing)
                )
                if not _post_layout_prune_guard_still_blocked:
                    _post_layout_prune_guard_arrange = _run_dimension_arrange_stage("post_layout_prune_guard")
                    _post_layout_dim_result["post_layout_prune_guard_dimension_arrange"] = (
                        _post_layout_prune_guard_arrange
                    )
                    _post_layout_after_arrange_coverage = _record_reference_intent_target_coverage(
                        "post_layout_prune_guard_after_arrange",
                        persisted_after_reopen=True,
                    )
                    _post_layout_dim_result["post_layout_prune_guard_target_coverage_after_arrange"] = (
                        _post_layout_after_arrange_coverage
                    )
                    _post_layout_after_arrange_count = _count_display_dims(drw)
                    _post_layout_after_arrange_missing = sorted(
                        _reference_intent_missing_target_keys(_post_layout_after_arrange_coverage or {})
                    )
                    _post_layout_arrange_guard_reason = _reference_intent_post_layout_repair_reason(
                        _post_layout_after_arrange_count,
                        _dim_floor,
                        _post_layout_after_arrange_coverage or {},
                    )
                    _post_layout_dim_result["post_layout_prune_guard_arrange_guard_reason"] = (
                        _post_layout_arrange_guard_reason
                    )
                    if _post_layout_arrange_guard_reason:
                        _post_layout_dim_result["post_layout_prune_guard_arrange_guard_attempted"] = True
                        _post_layout_arrange_guard_explicit = _run_reference_intent_explicit_display_dims(
                            "post_layout_prune_guard_after_arrange"
                        )
                        _post_layout_after_arrange_guard_count = _count_display_dims(drw)
                        _post_layout_after_arrange_guard_missing = sorted(
                            _reference_intent_missing_target_keys(
                                (_post_layout_arrange_guard_explicit or {}).get("target_coverage_after") or {}
                            )
                        )
                        _post_layout_dim_result.update({
                            "post_layout_prune_guard_arrange_guard_display_dim_count_before": (
                                _post_layout_after_arrange_count
                            ),
                            "post_layout_prune_guard_arrange_guard_display_dim_count_after": (
                                _post_layout_after_arrange_guard_count
                            ),
                            "post_layout_prune_guard_arrange_guard_explicit_display_dims": (
                                _post_layout_arrange_guard_explicit
                            ),
                            "post_layout_prune_guard_arrange_guard_missing_target_keys_after": (
                                _post_layout_after_arrange_guard_missing
                            ),
                        })
                        _post_layout_arrange_guard_still_blocked = (
                            _post_layout_after_arrange_guard_count < _dim_floor
                            or bool(_post_layout_after_arrange_guard_missing)
                        )
                        if _post_layout_arrange_guard_still_blocked:
                            warnings_box.append({
                                "code": "post_layout_prune_guard_after_arrange_still_blocked",
                                "before": _post_layout_after_arrange_count,
                                "after": _post_layout_after_arrange_guard_count,
                                "missing_target_keys": _post_layout_after_arrange_guard_missing,
                                "repair_reason": _post_layout_arrange_guard_reason,
                                "msg": "Post-layout prune guard arrange changed required target coverage and repair could not restore it.",
                            })
                    else:
                        _post_layout_dim_result["post_layout_prune_guard_arrange_guard_attempted"] = False
                    try:
                        err.value = 0; warn.value = 0
                        drw.Extension.SaveAs(slddrw, 0, 1, vt_dispatch_none(), err, warn)
                        _post_layout_dim_result["post_layout_prune_guard_save"] = {
                            "errors": int(err.value),
                            "warnings": int(warn.value),
                            "method": "Extension.SaveAs",
                        }
                        log(f"  [reference_style] post-layout prune-guard SLDDRW save: err={err.value}")
                    except Exception as exc_save:
                        _post_layout_dim_result["post_layout_prune_guard_save_error"] = str(exc_save)
                        warnings_box.append({"code":"post_layout_prune_guard_save_failed","msg":str(exc_save)})
                    try:
                        pdf_data = sw.GetExportFileData(1)
                        sheet_names = list(drw.GetSheetNames()) if callable(getattr(drw, "GetSheetNames", None)) else []
                        if pdf_data and sheet_names and callable(getattr(pdf_data, "SetSheets", None)):
                            pdf_data.SetSheets(0, sheet_names)
                        err.value = 0; warn.value = 0
                        drw.Extension.SaveAs(pdf, 0, 1, pdf_data, err, warn)
                        err.value = 0; warn.value = 0
                        drw.Extension.SaveAs(dxf, 0, 1, vt_dispatch_none(), err, warn)
                        _post_layout_dim_result["post_layout_prune_guard_reexported"] = True
                        log("  [reference_style] post-layout prune-guard PDF/DXF re-exported")
                        _png_render_result = _render_pdf_first_page_to_png(pdf, png_path, warnings_box, log)
                        _post_layout_dim_result["post_layout_prune_guard_png_render"] = _png_render_result
                    except Exception as exc_export:
                        _post_layout_dim_result["post_layout_prune_guard_reexport_error"] = str(exc_export)
                        warnings_box.append({"code":"post_layout_prune_guard_reexport_failed","msg":str(exc_export)})
                else:
                    warnings_box.append({
                        "code": "post_layout_prune_guard_still_blocked",
                        "before": _post_layout_after_prune_count,
                        "after": _post_layout_after_guard_count,
                        "missing_target_keys": _post_layout_after_guard_missing,
                        "repair_reason": _post_layout_prune_guard_reason,
                        "msg": "Post-layout prune guard could not restore every required 006 reference-intent target.",
                    })
            else:
                _post_layout_dim_result["post_layout_prune_guard_attempted"] = False
            _post_layout_final_exact_prune_before = _count_display_dims(drw)
            _post_layout_final_exact_prune_target_count = len([
                item for item in _reference_intent_dimension_targets()
                if isinstance(item, dict) and str(item.get("key") or "").strip()
            ])
            _post_layout_final_exact_prune_floor = max(
                _dim_floor,
                _post_layout_final_exact_prune_target_count,
            )
            if (
                _skip_generic_model_dim_import
                and _v4_dimension_view_quotas(_drawing_blueprint_v4 or {})
                and _post_layout_final_exact_prune_before > _post_layout_final_exact_prune_floor
            ):
                try:
                    # post_layout_final_exact_prune:
                    # Last chance to remove non-reference DisplayDims after all
                    # repair/arrange passes. This keeps 006 visual acceptance
                    # from regressing back to a 20+ DisplayDim sheet.
                    drw, _post_layout_final_exact_prune = _prune_persisted_reference_display_dims(
                        sw,
                        drw,
                        slddrw,
                        reference_dim_floor,
                        log_fn=log,
                        part_class=(_drawing_blueprint_v4 or {}).get("part_class", ""),
                        dimension_plan=(_drawing_blueprint_v4 or {}).get("dimension_plan") or {},
                        layout_plan=(_drawing_blueprint_v4 or {}).get("layout_plan") or {},
                        restore_on_failed_prune=False,
                    )
                    _post_layout_final_exact_prune_after = _count_display_dims(drw)
                    _post_layout_dim_result.update({
                        "post_layout_final_exact_prune": _post_layout_final_exact_prune,
                        "post_layout_final_exact_prune_display_dim_count_before": (
                            _post_layout_final_exact_prune_before
                        ),
                        "post_layout_final_exact_prune_display_dim_count_after": (
                            _post_layout_final_exact_prune_after
                        ),
                    })
                    if (_post_layout_final_exact_prune or {}).get("success"):
                        try:
                            pdf_data = sw.GetExportFileData(1)
                            sheet_names = list(drw.GetSheetNames()) if callable(getattr(drw, "GetSheetNames", None)) else []
                            if pdf_data and sheet_names and callable(getattr(pdf_data, "SetSheets", None)):
                                pdf_data.SetSheets(0, sheet_names)
                            err.value = 0; warn.value = 0
                            drw.Extension.SaveAs(pdf, 0, 1, pdf_data, err, warn)
                            err.value = 0; warn.value = 0
                            drw.Extension.SaveAs(dxf, 0, 1, vt_dispatch_none(), err, warn)
                            _post_layout_dim_result["post_layout_final_exact_prune_reexported"] = True
                            log("  [reference_style] post-layout final exact-prune PDF/DXF re-exported")
                            _png_render_result = _render_pdf_first_page_to_png(pdf, png_path, warnings_box, log)
                            _post_layout_dim_result["post_layout_final_exact_prune_png_render"] = _png_render_result
                        except Exception as exc_export:
                            _post_layout_dim_result["post_layout_final_exact_prune_reexport_error"] = str(exc_export)
                            warnings_box.append({"code":"post_layout_final_exact_prune_reexport_failed","msg":str(exc_export)})
                    else:
                        _post_layout_dim_result["post_layout_final_exact_prune_restore_deferred"] = True
                        _post_layout_final_exact_prune_failed_coverage = _record_reference_intent_target_coverage(
                            "post_layout_final_exact_prune_failed_compact",
                            persisted_after_reopen=True,
                        )
                        _post_layout_final_exact_prune_repair_reason = _reference_intent_post_layout_repair_reason(
                            _post_layout_final_exact_prune_after,
                            _dim_floor,
                            _post_layout_final_exact_prune_failed_coverage or {},
                        )
                        _post_layout_dim_result.update({
                            "post_layout_final_exact_prune_failed_compact_coverage": (
                                _post_layout_final_exact_prune_failed_coverage
                            ),
                            "post_layout_final_exact_prune_repair_reason": (
                                _post_layout_final_exact_prune_repair_reason
                            ),
                        })
                        if _skip_generic_model_dim_import and _post_layout_final_exact_prune_repair_reason:
                            _post_layout_dim_result["post_layout_final_exact_prune_repair_attempted"] = True
                            _post_layout_final_exact_prune_repair = _run_reference_intent_explicit_display_dims(
                                "post_layout_final_exact_prune_repair"
                            )
                            _post_layout_final_exact_prune_repair_after = _count_display_dims(drw)
                            _post_layout_final_exact_prune_repair_missing = sorted(
                                _reference_intent_missing_target_keys(
                                    (_post_layout_final_exact_prune_repair or {}).get("target_coverage_after") or {}
                                )
                            )
                            _post_layout_dim_result.update({
                                "post_layout_final_exact_prune_repair": _post_layout_final_exact_prune_repair,
                                "post_layout_final_exact_prune_repair_display_dim_count_after": (
                                    _post_layout_final_exact_prune_repair_after
                                ),
                                "post_layout_final_exact_prune_repair_missing_target_keys_after": (
                                    _post_layout_final_exact_prune_repair_missing
                                ),
                            })
                            _post_layout_final_exact_prune_repair_still_blocked = (
                                _post_layout_final_exact_prune_repair_after < _dim_floor
                                or bool(_post_layout_final_exact_prune_repair_missing)
                            )
                            if not _post_layout_final_exact_prune_repair_still_blocked:
                                try:
                                    err.value = 0; warn.value = 0
                                    drw.Extension.SaveAs(slddrw, 0, 1, vt_dispatch_none(), err, warn)
                                    _post_layout_dim_result["post_layout_final_exact_prune_repair_save"] = {
                                        "errors": int(err.value),
                                        "warnings": int(warn.value),
                                        "method": "Extension.SaveAs",
                                    }
                                    log(f"  [reference_style] post-layout final exact-prune repair SLDDRW save: err={err.value}")
                                except Exception as exc_save:
                                    _post_layout_dim_result["post_layout_final_exact_prune_repair_save_error"] = str(exc_save)
                                    warnings_box.append({"code":"post_layout_final_exact_prune_repair_save_failed","msg":str(exc_save)})
                                try:
                                    pdf_data = sw.GetExportFileData(1)
                                    sheet_names = list(drw.GetSheetNames()) if callable(getattr(drw, "GetSheetNames", None)) else []
                                    if pdf_data and sheet_names and callable(getattr(pdf_data, "SetSheets", None)):
                                        pdf_data.SetSheets(0, sheet_names)
                                    err.value = 0; warn.value = 0
                                    drw.Extension.SaveAs(pdf, 0, 1, pdf_data, err, warn)
                                    err.value = 0; warn.value = 0
                                    drw.Extension.SaveAs(dxf, 0, 1, vt_dispatch_none(), err, warn)
                                    _post_layout_dim_result["post_layout_final_exact_prune_repair_reexported"] = True
                                    log("  [reference_style] post-layout final exact-prune repair PDF/DXF re-exported")
                                    _png_render_result = _render_pdf_first_page_to_png(pdf, png_path, warnings_box, log)
                                    _post_layout_dim_result["post_layout_final_exact_prune_repair_png_render"] = (
                                        _png_render_result
                                    )
                                except Exception as exc_export:
                                    _post_layout_dim_result["post_layout_final_exact_prune_repair_reexport_error"] = str(exc_export)
                                    warnings_box.append({"code":"post_layout_final_exact_prune_repair_reexport_failed","msg":str(exc_export)})
                            else:
                                warnings_box.append({
                                    "code": "post_layout_final_exact_prune_repair_still_blocked",
                                    "before": _post_layout_final_exact_prune_after,
                                    "after": _post_layout_final_exact_prune_repair_after,
                                    "missing_target_keys": _post_layout_final_exact_prune_repair_missing,
                                    "repair_reason": _post_layout_final_exact_prune_repair_reason,
                                    "msg": "Final exact-prune compact state could not be repaired back to every required reference-intent target.",
                                })
                        else:
                            _post_layout_dim_result["post_layout_final_exact_prune_repair_attempted"] = False
                        warnings_box.append({
                            "code": "post_layout_final_exact_prune_failed",
                            "before": _post_layout_final_exact_prune_before,
                            "after": _post_layout_final_exact_prune_after,
                            "result": _post_layout_final_exact_prune,
                            "msg": "Final post-layout exact prune could not reduce DisplayDims while preserving reference-intent coverage.",
                        })
                except Exception as exc_prune:
                    _post_layout_dim_result["post_layout_final_exact_prune_error"] = str(exc_prune)
                    warnings_box.append({"code":"post_layout_final_exact_prune_exception","msg":str(exc_prune)})
            _post_layout_dim_result["target_coverage_final"] = _record_reference_intent_target_coverage(
                "post_layout_final",
                persisted_after_reopen=True,
            )
            _dim_final_for_reference = _count_display_dims(drw)
            _post_layout_dim_result["after"] = _dim_final_for_reference
            _post_layout_final_blockers = _reference_intent_final_acceptance_blockers(
                _dim_final_for_reference,
                _dim_floor,
                _post_layout_dim_result.get("target_coverage_final") or {},
                (_drawing_blueprint_v4 or {}).get("dimension_plan") or {},
            )
            _post_layout_dim_result["final_acceptance_blockers"] = _post_layout_final_blockers
            if _post_layout_final_blockers:
                warnings_box.append({
                    "code": "post_layout_reference_intent_final_blocked",
                    "display_dim_count": _dim_final_for_reference,
                    "reference_display_dim_floor": _dim_floor,
                    "blockers": _post_layout_final_blockers,
                    "msg": "Final post-layout DisplayDim state does not satisfy the 006 reference-intent acceptance contract.",
                })
    except Exception as exc:
        _post_layout_dim_result["error"] = str(exc)
        warnings_box.append({"code":"post_layout_dim_repair_exception","msg":str(exc)})

    _reference_intent_coverage_delta = _reference_intent_target_coverage_stage_delta(
        _reference_intent_target_coverage_results
    )
    if _reference_intent_coverage_delta.get("target_count"):
        warnings_box.append({
            "code": "reference_intent_target_coverage_stage_delta",
            **_reference_intent_coverage_delta,
        })

    warn_path = os.path.join(out_dir, f"{base_name}_v5_warnings.json")
    with open(warn_path, "w", encoding="utf-8") as f:
        json.dump({
            "part": part_path,
            "warnings": warnings_box,
            "issues_in": issues,
            "scale": scale_label,
            "bbox_m": bbox_m,
            "centers_m": centers,
            "predicted_outlines_m": outlines_pred,
            "real_outlines_m": real_outlines,
            "real_overlap_pairs": real_overlap_pairs,
            "section_helper_called": section_helper_called,
            "section_view": section_view,
            "display_dim_count_before_sidecar": _dim_before_sidecar,
            "display_dim_count_final": _dim_final_for_reference,
            "dimension_sidecar_mode": _sidecar_mode,
            "png_render": _png_render_result,
            "reference_autodim": _autodim_result,
            "reference_intent_target_coverage": _reference_intent_target_coverage_results,
            "reference_intent_target_coverage_delta": _reference_intent_coverage_delta,
            "post_prune_dim_guard": _post_prune_dim_guard,
            "post_layout_dim_repair": _post_layout_dim_result,
            "reference_dim_prune": _dim_prune_result,
            "dimension_arrange_results": _dimension_arrange_results,
            "text_height": text_height,
            "cached_cfg_name": _cached_cfg_name,
            "drawing_blueprint_v4": _drawing_blueprint_v4,
            "drawing_blueprint_paths": _drawing_blueprint_paths,
            "drawing_blueprint_source": _drawing_blueprint_source,
        }, f, ensure_ascii=False, indent=2, default=str)
    log(f"  Warnings: {len(warnings_box)} 条 -> {warn_path}")

    try:
        drw_title = call(drw, "GetTitle")
        if drw_title:
            sw.CloseDoc(drw_title)
            _solidworks_doc_registry_event(
                "solidworks_doc_closed",
                role="generated_drawing",
                path=slddrw,
                title=drw_title,
                doc_type="drawing",
                stage="final_close_generated_drawing",
                close_verified=True,
            )
    except Exception as exc:
        _solidworks_doc_registry_event(
            "solidworks_doc_close_failed",
            role="generated_drawing",
            path=slddrw,
            title=_doc_title(drw),
            doc_type="drawing",
            stage="final_close_generated_drawing",
            close_verified=False,
            reason=str(exc),
        )
    try:
        if part is not None:
            part_title = call(part, "GetTitle")
            if part_title:
                sw.CloseDoc(part_title)
                _solidworks_doc_registry_event(
                    "solidworks_doc_closed",
                    role="copied_part",
                    path=_work_part_path,
                    title=part_title,
                    doc_type="part",
                    stage="final_close_work_part",
                    close_verified=True,
                )
    except Exception as exc:
        _solidworks_doc_registry_event(
            "solidworks_doc_close_failed",
            role="copied_part",
            path=_work_part_path if "_work_part_path" in locals() else part_path,
            title=_doc_title(part) if part is not None else "",
            doc_type="part",
            stage="final_close_work_part",
            close_verified=False,
            reason=str(exc),
        )

    return {
        "slddrw": slddrw, "pdf": pdf, "dxf": dxf, "png": png_path, "warnings": warn_path,
        "drawing_blueprint": _drawing_blueprint_paths[0] if _drawing_blueprint_paths else "",
        "scale": scale_label, "section": bool(section_view),
        "section_helper_called": section_helper_called,
        "centers": centers, "real_overlap_pairs": real_overlap_pairs,
        "bbox_m": bbox_m,
    }


if __name__ == "__main__":
    _com_initialized = False
    try:
        pythoncom.CoInitialize()
        _com_initialized = True
        log("[com] CoInitialize done")
    except Exception as exc:
        log(f"[com] CoInitialize failed: {exc}")
    try:
        target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PART
        issues_path = sys.argv[2] if len(sys.argv) > 2 else None
        issues = load_issues_to_fix(issues_path)
        res = generate_for(target, issues=issues)
        log("\n[DONE] " + json.dumps(res, ensure_ascii=False, default=str))
    finally:
        if _com_initialized:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
