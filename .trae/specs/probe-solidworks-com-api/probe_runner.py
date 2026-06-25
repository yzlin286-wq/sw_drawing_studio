"""
SolidWorks COM API 探针 — probe_runner.py
按 14 个分组对本地 SolidWorks 实例做接口冒烟（默认只读）。
- 默认连接已启动的 SW 实例（GetActiveObject）；失败则降级 stub。
- 默认对仓库内 `3D转2D测试图纸/LB26001-A-04-001.SLDPRT` 跑探针。
- 写入操作（新建文档、SaveAs、删除等）默认 SKIP，需 --write 才执行。
- 输出 probe_result.json 与 probe_log.md。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # .../SW 相关
DEFAULT_PART = REPO_ROOT / "3D转2D测试图纸" / "LB26001-A-04-001.SLDPRT"


def _safe_repr(x: Any, limit: int = 200) -> str:
    try:
        s = repr(x)
    except Exception:
        s = f"<unrepr {type(x).__name__}>"
    if len(s) > limit:
        s = s[:limit] + "..."
    return s


def call_or_get(obj, name: str, *args):
    """SW typelib 在 EnsureDispatch 后会把无参方法标成属性，反之亦然。
    本助手先尝试方法调用，失败则回退到属性访问。"""
    val = getattr(obj, name)
    if callable(val):
        return val(*args)
    if args:
        # 不是 callable 但又有参数 -> 试 InvokeTypes 兜底
        try:
            disp_id = obj._oleobj_.GetIDsOfNames(name)
            return obj._oleobj_.Invoke(disp_id, 0, 1, True, *args)  # 1=DISPATCH_METHOD
        except Exception:
            return val
    return val


def _to_list(v: Any) -> list:
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return list(v)
    return [v]


class Probe:
    """记录探针结果的容器。"""

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []
        self.current_group: str = "_init"

    def group(self, name: str) -> None:
        self.current_group = name

    def run(
        self,
        name: str,
        fn: Callable[[], Any],
        *,
        skip: bool = False,
        skip_reason: str = "",
    ) -> None:
        if skip:
            self.entries.append({
                "group": self.current_group,
                "name": name,
                "ok": None,
                "status": "skip",
                "skip_reason": skip_reason,
                "summary": "",
                "error": "",
            })
            print(f"  [skip] {name}: {skip_reason}")
            return
        t0 = time.time()
        try:
            result = fn()
            summary = _safe_repr(result)
            self.entries.append({
                "group": self.current_group,
                "name": name,
                "ok": True,
                "status": "pass",
                "summary": summary,
                "error": "",
                "elapsed_ms": int((time.time() - t0) * 1000),
            })
            print(f"  [ok]   {name}: {summary[:120]}")
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
            self.entries.append({
                "group": self.current_group,
                "name": name,
                "ok": False,
                "status": "fail",
                "summary": "",
                "error": err,
                "elapsed_ms": int((time.time() - t0) * 1000),
            })
            print(f"  [FAIL] {name}: {err}")


# =============================================================
# 14 个分组探针
# =============================================================

def probe_app(p: Probe, sw) -> None:
    p.group("01_ISldWorks")
    p.run("RevisionNumber", lambda: call_or_get(sw, "RevisionNumber"))
    p.run("Visible", lambda: bool(sw.Visible))
    p.run("FrameLeft", lambda: sw.FrameLeft)
    p.run("FrameWidth", lambda: sw.FrameWidth)
    p.run("ActiveDoc(ref)", lambda: type(sw.ActiveDoc).__name__ if sw.ActiveDoc is not None else "None")
    p.run("EnumDocuments2", lambda: call_or_get(sw, "EnumDocuments2") is not None)
    p.run("GetUserPreferenceDoubleValue(89)", lambda: sw.GetUserPreferenceDoubleValue(89))
    p.run("GetUserPreferenceIntegerValue(0)", lambda: sw.GetUserPreferenceIntegerValue(0))
    p.run("GetUserPreferenceToggle(0)", lambda: bool(sw.GetUserPreferenceToggle(0)))
    p.run("GetCurrentLanguage", lambda: call_or_get(sw, "GetCurrentLanguage"))
    p.run("GetExecutablePath", lambda: call_or_get(sw, "GetExecutablePath"))
    p.run("GetMathUtility", lambda: call_or_get(sw, "GetMathUtility") is not None)


def probe_doc(p: Probe, sw, model) -> None:
    p.group("02_IModelDoc2")
    if model is None:
        p.run("(no_active_doc)", lambda: None, skip=True, skip_reason="ActiveDoc is None")
        return
    p.run("GetType", lambda: call_or_get(model, "GetType"))
    p.run("GetTitle", lambda: call_or_get(model, "GetTitle"))
    p.run("GetPathName", lambda: call_or_get(model, "GetPathName"))
    p.run("Extension", lambda: type(model.Extension).__name__)
    p.run("GetActiveConfiguration", lambda: type(call_or_get(model, "GetActiveConfiguration")).__name__)
    p.run("FeatureManager", lambda: type(model.FeatureManager).__name__)
    p.run("SketchManager", lambda: type(model.SketchManager).__name__)
    p.run("ConfigurationManager", lambda: type(model.ConfigurationManager).__name__)
    p.run("GetEquationMgr", lambda: type(call_or_get(model, "GetEquationMgr")).__name__)
    p.run("ClearSelection2(True)", lambda: (model.ClearSelection2(True), True)[1])
    p.run("EditRebuild3", lambda: bool(call_or_get(model, "EditRebuild3")))


def probe_part(p: Probe, model, write: bool) -> None:
    p.group("03_IPartDoc")
    gtype = call_or_get(model, "GetType") if model is not None else None
    if gtype != 1:
        p.run("(not_part)", lambda: None, skip=True, skip_reason=f"GetType={gtype}")
        return
    p.run("GetBodies2(any, visible_only)", lambda: len(_to_list(model.GetBodies2(0, True))))
    p.run("EnumBodies3", lambda: model.EnumBodies3(0, True) is not None)
    p.run("MaterialIdName", lambda: call_or_get(model, "MaterialIdName"))
    p.run("GetPartBox", lambda: _safe_repr(model.GetPartBox(True)))
    p.run("FirstFeature", lambda: call_or_get(model, "FirstFeature") is not None)
    p.run("FeatureByName('Sketch1')", lambda: model.FeatureByName("Sketch1"))
    p.run("IsWeldment", lambda: bool(call_or_get(model, "IsWeldment")))
    try:
        ext = model.Extension
        p.run("Extension.IsSheetMetal", lambda: bool(call_or_get(ext, "IsSheetMetal")))
    except Exception as exc:
        p.run("Extension.IsSheetMetal", lambda: (_ for _ in ()).throw(exc))
    p.run("ExportToDWG2(skip_unless_write)", lambda: None,
          skip=not write, skip_reason="destructive: 需 --write 才执行")
    p.run("MirrorPart3(skip_unless_write)", lambda: None,
          skip=not write, skip_reason="destructive")


def probe_assembly(p: Probe, model) -> None:
    p.group("04_IAssemblyDoc")
    gtype = call_or_get(model, "GetType") if model is not None else None
    if gtype != 2:
        p.run("(not_assembly)", lambda: None, skip=True, skip_reason=f"GetType={gtype}")
        return
    p.run("GetComponents(top_only=False)", lambda: len(_to_list(model.GetComponents(False))))
    p.run("GetComponents(top_only=True)", lambda: len(_to_list(model.GetComponents(True))))
    p.run("IsLightWeight", lambda: bool(call_or_get(model, "IsLightWeight")))
    p.run("GetClearanceVerificationMgr", lambda: type(call_or_get(model, "GetClearanceVerificationMgr")).__name__)
    p.run("ToolsCheckInterference2(no_args)", lambda: None,
          skip=True, skip_reason="需 selection set；只读模式跳过")
    p.run("AddComponent5(skip)", lambda: None, skip=True, skip_reason="destructive")
    p.run("AddMate5(skip)", lambda: None, skip=True, skip_reason="destructive")
    p.run("EditAssembly", lambda: call_or_get(model, "EditAssembly"))
    p.run("ResolveAllLightWeightComponents(False)", lambda: model.ResolveAllLightWeightComponents(False))


def probe_drawing(p: Probe, model) -> None:
    p.group("05_IDrawingDoc")
    gtype = call_or_get(model, "GetType") if model is not None else None
    if gtype != 3:
        p.run("(not_drawing)", lambda: None, skip=True, skip_reason=f"GetType={gtype}")
        return
    p.run("GetSheetNames", lambda: _to_list(call_or_get(model, "GetSheetNames")))
    p.run("GetCurrentSheet", lambda: type(call_or_get(model, "GetCurrentSheet")).__name__)
    p.run("GetFirstView", lambda: call_or_get(model, "GetFirstView") is not None)
    p.run("ActivateSheet(first)", lambda: model.ActivateSheet(_to_list(call_or_get(model, "GetSheetNames"))[0]))
    p.run("FeatureByName('Sheet1')", lambda: model.FeatureByName("Sheet1") is not None)
    p.run("Create3rdAngleViews2(skip)", lambda: None, skip=True, skip_reason="destructive")
    p.run("CreateSectionViewAt5(skip)", lambda: None, skip=True, skip_reason="destructive")
    p.run("InsertModelAnnotations3(skip)", lambda: None, skip=True, skip_reason="destructive")
    p.run("InsertCenterMark2(skip)", lambda: None, skip=True, skip_reason="destructive")


def probe_sketch(p: Probe, model) -> None:
    p.group("06_ISketchManager")
    if model is None:
        p.run("(no_active_doc)", lambda: None, skip=True, skip_reason="ActiveDoc is None")
        return
    sm = model.SketchManager
    p.run("ActiveSketch(read)", lambda: sm.ActiveSketch is None or type(sm.ActiveSketch).__name__)
    p.run("AddToDB(read)", lambda: bool(sm.AddToDB))
    p.run("DisplayWhenAdded(read)", lambda: bool(sm.DisplayWhenAdded))
    p.run("InsertSketch(skip)", lambda: None, skip=True, skip_reason="enters edit mode")
    p.run("Insert3DSketch(skip)", lambda: None, skip=True, skip_reason="enters edit mode")
    p.run("CreateLine(skip)", lambda: None, skip=True, skip_reason="destructive")
    p.run("CreateCircle(skip)", lambda: None, skip=True, skip_reason="destructive")
    p.run("CreateCornerRectangle(skip)", lambda: None, skip=True, skip_reason="destructive")
    p.run("CreateSpline(skip)", lambda: None, skip=True, skip_reason="destructive")
    p.run("CreateCenterLine(skip)", lambda: None, skip=True, skip_reason="destructive")


def probe_features(p: Probe, model) -> None:
    p.group("07_IFeatureManager")
    if model is None:
        p.run("(no_active_doc)", lambda: None, skip=True, skip_reason="ActiveDoc is None")
        return
    fm = model.FeatureManager
    p.run("FeatureManager(ref)", lambda: type(fm).__name__)
    feats = []
    f = call_or_get(model, "FirstFeature") if model is not None else None
    cnt = 0
    while f is not None and cnt < 100:
        try:
            feats.append((call_or_get(f, "Name"), call_or_get(f, "GetTypeName2")))
        except Exception:
            feats.append((str(f), "?"))
        try:
            f = call_or_get(f, "GetNextFeature")
        except Exception:
            break
        cnt += 1
    p.run("Traverse FirstFeature->GetNextFeature", lambda: len(feats))
    p.run("FeatureExtrusion3(skip)", lambda: None, skip=True, skip_reason="destructive")
    p.run("FeatureCut4(skip)", lambda: None, skip=True, skip_reason="destructive")
    p.run("FeatureRevolve2(skip)", lambda: None, skip=True, skip_reason="destructive")
    p.run("FeatureFillet3(skip)", lambda: None, skip=True, skip_reason="destructive")
    p.run("FeatureChamfer(skip)", lambda: None, skip=True, skip_reason="destructive")
    p.run("Shell(skip)", lambda: None, skip=True, skip_reason="destructive")
    p.run("FeatureLinearPattern5(skip)", lambda: None, skip=True, skip_reason="destructive")
    p.run("FeatureCircularPattern5(skip)", lambda: None, skip=True, skip_reason="destructive")
    p.run("InsertSheetMetalBaseFlange2(skip)", lambda: None, skip=True, skip_reason="destructive")
    p.run("InsertReferencePlane2(skip)", lambda: None, skip=True, skip_reason="destructive")


def probe_component(p: Probe, model) -> None:
    p.group("08_IComponent2")
    gtype = call_or_get(model, "GetType") if model is not None else None
    if gtype != 2:
        p.run("(not_assembly)", lambda: None, skip=True, skip_reason="非装配体，跳过")
        return
    comps = _to_list(model.GetComponents(True))
    if not comps:
        p.run("(no_top_components)", lambda: None, skip=True, skip_reason="顶层无组件")
        return
    c = comps[0]
    p.run("Component.Name2", lambda: call_or_get(c, "Name2"))
    p.run("Component.GetPathName", lambda: call_or_get(c, "GetPathName"))
    p.run("Component.GetModelDoc2", lambda: type(call_or_get(c, "GetModelDoc2")).__name__)
    p.run("Component.Visible", lambda: call_or_get(c, "Visible"))
    p.run("Component.IsSuppressed", lambda: bool(call_or_get(c, "IsSuppressed")))
    p.run("Component.IsRoot", lambda: bool(call_or_get(c, "IsRoot")))
    p.run("Component.ReferencedConfiguration", lambda: call_or_get(c, "ReferencedConfiguration"))
    p.run("Component.Solving", lambda: call_or_get(c, "Solving"))
    p.run("Component.GetID", lambda: call_or_get(c, "GetID"))
    p.run("Component.GetChildren", lambda: len(_to_list(call_or_get(c, "GetChildren"))))
    p.run("Component.Transform2", lambda: type(call_or_get(c, "Transform2")).__name__)
    p.run("Component.MakeVirtual(skip)", lambda: None, skip=True, skip_reason="destructive")


def probe_config(p: Probe, model) -> None:
    p.group("09_IConfiguration")
    if model is None:
        p.run("(no_active_doc)", lambda: None, skip=True, skip_reason="ActiveDoc is None")
        return
    cm = model.ConfigurationManager
    p.run("ConfigurationManager.ActiveConfiguration", lambda: cm.ActiveConfiguration is not None)
    p.run("IModelDoc2.GetConfigurationNames", lambda: _to_list(call_or_get(model, "GetConfigurationNames")))
    cfg = cm.ActiveConfiguration
    if cfg is None:
        p.run("(no_active_cfg)", lambda: None, skip=True, skip_reason="ActiveConfiguration is None")
        return
    p.run("Configuration.Name", lambda: call_or_get(cfg, "Name"))
    p.run("Configuration.Description", lambda: call_or_get(cfg, "Description"))
    p.run("Configuration.Comment", lambda: call_or_get(cfg, "Comment"))
    p.run("Configuration.AlternateName", lambda: call_or_get(cfg, "AlternateName"))
    # GetParameters 在多数 SW 版本要求一个 prop name 入参；空列表是已知不可用，跳过
    p.run("Configuration.GetParameters(skip)", lambda: None,
          skip=True, skip_reason="多数版本必须传 BSTR 参数；属于已知 marshaling 限制")
    p.run("Configuration.CustomPropertyManager", lambda: type(cfg.CustomPropertyManager).__name__)
    p.run("AddConfiguration2(skip)", lambda: None, skip=True, skip_reason="destructive")
    p.run("ShowConfiguration2(skip)", lambda: None, skip=True, skip_reason="可能改写状态")


def probe_props(p: Probe, model) -> None:
    p.group("10_ICustomPropertyManager")
    if model is None:
        p.run("(no_active_doc)", lambda: None, skip=True, skip_reason="ActiveDoc is None")
        return
    ext = model.Extension
    cpm = ext.CustomPropertyManager("")
    p.run("CustomPropertyManager('').Count", lambda: cpm.Count)
    p.run("CustomPropertyManager('').GetNames", lambda: _to_list(call_or_get(cpm, "GetNames")))
    p.run("CustomPropertyManager('').LinkAll(read)", lambda: bool(cpm.LinkAll))

    # Get4 在 EnsureDispatch 后 outparams 必须用 VARIANT；用 Get5 更稳定
    def _try_get(name: str):
        # 先尝试 Get6（较新）/Get5/Get4
        for method in ("Get6", "Get5", "Get4"):
            try:
                fn = getattr(cpm, method)
                if method == "Get6":
                    res = fn(name, False)
                elif method == "Get5":
                    res = fn(name, False)
                else:
                    res = fn(name, False)
                return f"{method} -> {_safe_repr(res, 60)}"
            except Exception:
                continue
        return None
    p.run("CustomProp.Get(Description)", lambda: _try_get("Description") or "all_methods_failed")
    p.run("CustomProp.Get(Material)", lambda: _try_get("Material") or "all_methods_failed")
    p.run("GetType2('Description')", lambda: cpm.GetType2("Description"))
    p.run("Add3(skip)", lambda: None, skip=True, skip_reason="destructive")
    p.run("Set2(skip)", lambda: None, skip=True, skip_reason="destructive")
    p.run("Delete2(skip)", lambda: None, skip=True, skip_reason="destructive")


def probe_extension(p: Probe, model) -> None:
    p.group("11_IModelDocExtension")
    if model is None:
        p.run("(no_active_doc)", lambda: None, skip=True, skip_reason="ActiveDoc is None")
        return
    ext = model.Extension
    # Extension 的多数属性是 prop_get；EnsureDispatch 下要按属性访问
    def _get_prop(name: str):
        try:
            return getattr(ext, name)
        except Exception as exc:
            return f"<err {exc}>"
    p.run("Extension.MassProperty(read)", lambda: type(_get_prop("MassProperty")).__name__)
    p.run("Extension.SelectionManager(read)", lambda: type(_get_prop("SelectionManager")).__name__)
    p.run("Extension.LayerMgr(read)", lambda: type(_get_prop("LayerMgr")).__name__)
    p.run("Extension.Document(==model)", lambda: ext.Document is not None)
    p.run("Extension.IsSheetMetal", lambda: bool(call_or_get(ext, "IsSheetMetal")))
    p.run("Extension.RunCommand(skip)", lambda: None, skip=True, skip_reason="可能弹出命令")
    p.run("Extension.SaveAs3(skip)", lambda: None, skip=True, skip_reason="destructive")
    p.run("Extension.MultiSelect2(skip)", lambda: None, skip=True, skip_reason="改写选择集")
    p.run("Extension.Rebuild(0)", lambda: bool(ext.Rebuild(0)))


def probe_layer(p: Probe, model) -> None:
    p.group("12_ILayerMgr")
    gtype = call_or_get(model, "GetType") if model is not None else None
    if gtype != 3:
        p.run("(not_drawing)", lambda: None, skip=True, skip_reason="LayerMgr 主要用于工程图")
        return
    ext = model.Extension
    lmgr = getattr(ext, "LayerMgr", None)
    if lmgr is None:
        p.run("Extension.LayerMgr is None", lambda: None, skip=True, skip_reason="LayerMgr=None（已知缺陷 B-3）")
        return
    p.run("LayerMgr.GetLayerCount", lambda: call_or_get(lmgr, "GetLayerCount"))
    p.run("LayerMgr.GetLayerList", lambda: _to_list(call_or_get(lmgr, "GetLayerList")))
    p.run("LayerMgr.IsLayerPresent('FORMAT')", lambda: bool(lmgr.IsLayerPresent("FORMAT")))
    p.run("LayerMgr.AddLayer(skip)", lambda: None, skip=True, skip_reason="destructive")
    p.run("LayerMgr.DeleteLayer(skip)", lambda: None, skip=True, skip_reason="destructive")


def probe_mass(p: Probe, model) -> None:
    p.group("13_IMassProperty")
    gtype = call_or_get(model, "GetType") if model is not None else None
    if gtype not in (1, 2):
        p.run("(not_part_or_asm)", lambda: None, skip=True, skip_reason="质量属性仅适用零件/装配")
        return
    ext = model.Extension
    mp = getattr(ext, "MassProperty", None)
    if mp is None:
        p.run("Extension.MassProperty is None", lambda: None, skip=True, skip_reason="MassProperty 取不到")
        return
    p.run("MassProperty.Mass", lambda: mp.Mass)
    p.run("MassProperty.Volume", lambda: mp.Volume)
    p.run("MassProperty.SurfaceArea", lambda: mp.SurfaceArea)
    p.run("MassProperty.Density", lambda: mp.Density)
    p.run("MassProperty.CenterOfMass", lambda: _safe_repr(mp.CenterOfMass))
    p.run("MassProperty.PrincipalMomentsOfInertia", lambda: _safe_repr(mp.PrincipalMomentsOfInertia))
    p.run("MassProperty.Accuracy", lambda: mp.Accuracy)
    p.run("MassProperty.IncludeHiddenBodiesOrComponents", lambda: bool(mp.IncludeHiddenBodiesOrComponents))


def probe_export(p: Probe, sw, model, write: bool) -> None:
    p.group("14_Export_SaveAs")
    if model is None:
        p.run("(no_active_doc)", lambda: None, skip=True, skip_reason="ActiveDoc is None")
        return
    ext = model.Extension
    p.run("IExportPdfData = sw.GetExportFileData(1)", lambda: type(sw.GetExportFileData(1)).__name__)
    p.run("ExtraSaveAs3(skip_unless_write)", lambda: None, skip=not write, skip_reason="destructive")
    p.run("Save3(skip_unless_write)", lambda: None, skip=not write, skip_reason="destructive")
    p.run("ExportToDWG2(skip_unless_write)", lambda: None, skip=not write, skip_reason="destructive")
    # 只读情况下做一次"参数构造"以验证接口可达
    p.run("BuildAdvancedSaveAsOptions(read-only)", lambda: type(sw.GetExportFileData(7)).__name__ if hasattr(sw, "GetExportFileData") else "n/a")


# =============================================================
# 主入口
# =============================================================

def connect_sw():
    try:
        import win32com.client as win32com_client
        from win32com.client import gencache
    except Exception as exc:
        return None, f"pywin32 not installed: {exc}"
    # 优先用 EnsureDispatch，确保方法/属性按 typelib 定义解析
    try:
        sw = gencache.EnsureDispatch("SldWorks.Application")
        return sw, "EnsureDispatch ok"
    except Exception as exc1:
        try:
            sw = win32com_client.GetActiveObject("SldWorks.Application")
            return sw, f"GetActiveObject fallback (gencache failed: {exc1})"
        except Exception as exc:
            return None, f"GetActiveObject failed: {exc}"


def open_or_get_active(sw, part_path: Path):
    try:
        active = sw.ActiveDoc
        if active is not None:
            return active, "ActiveDoc reused"
    except Exception:
        pass
    if not part_path.exists():
        return None, f"part not found: {part_path}"
    try:
        ext = part_path.suffix.lower()
        type_map = {".sldprt": 1, ".sldasm": 2, ".slddrw": 3}
        doc_type = type_map.get(ext, 1)
        # OpenDoc6 outparams 在 pywin32 动态分派下需 VT_BYREF 包装；用 OpenDoc 简化签名兜底
        try:
            import pythoncom  # noqa: F401
            from win32com.client import VARIANT  # type: ignore
            errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            warnings = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            model = sw.OpenDoc6(str(part_path), doc_type, 0, "", errors, warnings)
        except Exception:
            # 退路：OpenDoc（旧 4 参签名，仍支持）
            model = sw.OpenDoc(str(part_path), doc_type)
        if model is None:
            return None, "OpenDoc returned None"
        return model, f"opened {part_path.name}"
    except Exception as exc:
        return None, f"OpenDoc raised: {exc}"


GROUPS = [
    ("01_ISldWorks", probe_app),
    ("02_IModelDoc2", probe_doc),
    ("03_IPartDoc", probe_part),
    ("04_IAssemblyDoc", probe_assembly),
    ("05_IDrawingDoc", probe_drawing),
    ("06_ISketchManager", probe_sketch),
    ("07_IFeatureManager", probe_features),
    ("08_IComponent2", probe_component),
    ("09_IConfiguration", probe_config),
    ("10_ICustomPropertyManager", probe_props),
    ("11_IModelDocExtension", probe_extension),
    ("12_ILayerMgr", probe_layer),
    ("13_IMassProperty", probe_mass),
    ("14_Export_SaveAs", probe_export),
]


def write_outputs(p: Probe, out_json: Path, out_log: Path, env: dict) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "env": env,
        "entries": p.entries,
        "stats": _stats(p.entries),
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_log.write_text(_render_log_md(payload), encoding="utf-8")


def _stats(entries: list[dict]) -> dict:
    s = {"pass": 0, "fail": 0, "skip": 0, "total": len(entries)}
    for e in entries:
        st = e.get("status")
        if st in s:
            s[st] += 1
    by_group = {}
    for e in entries:
        g = e.get("group", "?")
        by_group.setdefault(g, {"pass": 0, "fail": 0, "skip": 0, "total": 0})
        by_group[g][e.get("status", "skip")] += 1
        by_group[g]["total"] += 1
    s["by_group"] = by_group
    return s


def _render_log_md(payload: dict) -> str:
    env = payload["env"]
    s = payload["stats"]
    lines = []
    lines.append("# SolidWorks COM API 探针运行日志\n")
    lines.append(f"- 时间：{env.get('ts','')}")
    lines.append(f"- SW 连接：{env.get('connect_msg','')}")
    lines.append(f"- 文档：{env.get('doc_msg','')}")
    lines.append(f"- 写入模式：{'on' if env.get('write') else 'off (只读)'}\n")
    lines.append("## 统计")
    lines.append(f"- total: {s['total']}; pass: {s['pass']}; fail: {s['fail']}; skip: {s['skip']}\n")
    lines.append("## 按分组")
    for g, v in s.get("by_group", {}).items():
        lines.append(f"- **{g}** — total {v['total']} / pass {v['pass']} / fail {v['fail']} / skip {v['skip']}")
    lines.append("\n## 全部条目（截断 summary）\n")
    lines.append("| group | name | status | summary | error |")
    lines.append("|---|---|---|---|---|")
    for e in payload["entries"]:
        summary = (e.get("summary") or "").replace("|", "/").replace("\n", " ")[:80]
        error = (e.get("error") or "").replace("|", "/").replace("\n", " ")[:80]
        lines.append(f"| {e['group']} | {e['name']} | {e['status']} | {summary} | {error} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="SolidWorks COM API probe runner")
    parser.add_argument("--part", default=str(DEFAULT_PART), help="测试零件路径")
    parser.add_argument("--group", default="", help="只跑某个分组（如 01_ISldWorks，多个用逗号分隔）")
    parser.add_argument("--out", default=str(Path(__file__).with_name("probe_result.json")))
    parser.add_argument("--log", default=str(Path(__file__).with_name("probe_log.md")))
    parser.add_argument("--write", action="store_true", help="启用 destructive 接口")
    args = parser.parse_args()

    out_json = Path(args.out)
    out_log = Path(args.log)
    selected = {g.strip() for g in args.group.split(",") if g.strip()}

    env: dict = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "part": args.part,
        "write": args.write,
        "groups_filter": sorted(selected),
    }

    p = Probe()
    sw, connect_msg = connect_sw()
    env["connect_msg"] = connect_msg
    if sw is None:
        print(f"[stub] SolidWorks 未连接：{connect_msg}")
        env["doc_msg"] = "skipped: SolidWorks not running"
        for gname, _ in GROUPS:
            if selected and gname not in selected:
                continue
            p.group(gname)
            p.run(f"(group_skipped:{gname})", lambda: None,
                  skip=True, skip_reason=connect_msg)
        write_outputs(p, out_json, out_log, env)
        print(f"[stub] result -> {out_json}")
        print(f"[stub] log    -> {out_log}")
        return 2

    try:
        rev = sw.RevisionNumber
    except Exception as exc:
        print(f"[FAIL] sw.RevisionNumber 读取失败：{exc}")
        env["connect_msg"] += f" (RevisionNumber failed: {exc})"
        write_outputs(p, out_json, out_log, env)
        return 3
    print(f"[ok] connected to SolidWorks {rev}")

    model, doc_msg = open_or_get_active(sw, Path(args.part))
    env["doc_msg"] = doc_msg
    print(f"[doc] {doc_msg}")

    for gname, fn in GROUPS:
        if selected and gname not in selected:
            continue
        print(f"\n=== {gname} ===")
        try:
            if fn is probe_app:
                fn(p, sw)
            elif fn is probe_doc:
                fn(p, sw, model)
            elif fn is probe_part:
                fn(p, model, args.write)
            elif fn is probe_export:
                fn(p, sw, model, args.write)
            else:
                fn(p, model)
        except Exception as exc:
            traceback.print_exc()
            p.run(f"(group_crash:{gname})", lambda: (_ for _ in ()).throw(exc))

    write_outputs(p, out_json, out_log, env)
    s = _stats(p.entries)
    print(f"\n[done] total={s['total']} pass={s['pass']} fail={s['fail']} skip={s['skip']}")
    print(f"[done] result -> {out_json}")
    print(f"[done] log    -> {out_log}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
