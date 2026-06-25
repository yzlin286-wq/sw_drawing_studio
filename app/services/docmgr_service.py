"""v2.0 Task 4: Document Manager Probe / Relink Service

检测 SW_DM_LICENSE_KEY 和 COM Factory，使用 Document Manager API
读取 SLDDRW external references 并尝试 ReplaceReference。

无 license key 时返回 warning，不阻断主流程。

输出: docmgr_relink_result.json
"""
from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Any

# Document Manager COM ProgID
SWDM_PROGID = "SwDocumentMgr.SwDMApplication"
SWDM_CLASS_FACTORY_PROGID = "SwDocumentMgr.SwDMClassFactory"

# 默认 DLL 路径
SWDM_DLL_CANDIDATES = [
    r"C:\Program Files\SOLIDWORKS Corp25\SOLIDWORKS\SolidWorks.Interop.swdocumentmgr.dll",
    r"C:\Program Files\SOLIDWORKS Corp 2025\SOLIDWORKS\SolidWorks.Interop.swdocumentmgr.dll",
    r"C:\Program Files\SOLIDWORKS Corp24\SOLIDWORKS\SolidWorks.Interop.swdocumentmgr.dll",
]


def find_swdm_dll() -> str:
    """查找 SolidWorks Document Manager DLL"""
    for candidate in SWDM_DLL_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return ""


def get_license_key() -> str:
    """获取 Document Manager license key

    优先级:
    1. 环境变量 SW_DM_LICENSE_KEY
    2. config/docmgr.yaml 中的 license_key
    3. config/app.yaml 中的 sw_dm_license_key
    """
    # 1. 环境变量
    key = os.environ.get("SW_DM_LICENSE_KEY", "")
    if key:
        return key

    # 2. config/docmgr.yaml (v2.1)
    try:
        import yaml
        docmgr_yaml = Path(__file__).resolve().parents[2] / "config" / "docmgr.yaml"
        if docmgr_yaml.exists():
            with open(docmgr_yaml, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            key = cfg.get("license_key", "")
            if key:
                return key
    except Exception:
        pass

    # 3. config/app.yaml
    try:
        import yaml
        app_yaml = Path(__file__).resolve().parents[2] / "config" / "app.yaml"
        if app_yaml.exists():
            with open(app_yaml, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            key = cfg.get("sw_dm_license_key", "")
            if key:
                return key
    except Exception:
        pass

    return ""


def load_docmgr_config() -> dict:
    """v2.1: 加载 config/docmgr.yaml 配置

    Returns:
        {
            "license_key": str,
            "default_mode": str,  # "dry_run" / "apply"
            "dll_path": str,
            "com_progid": str,
            "class_factory_progid": str,
            "relink": dict,
            "output": dict,
        }
    """
    default_cfg = {
        "license_key": "",
        "default_mode": "dry_run",
        "dll_path": "",
        "com_progid": SWDM_PROGID,
        "class_factory_progid": SWDM_CLASS_FACTORY_PROGID,
        "relink": {"enabled": True, "backup_before_replace": True, "backup_dir": "input_work"},
        "output": {"result_file": "docmgr_result.json", "write_manifest": True},
    }

    try:
        import yaml
        docmgr_yaml = Path(__file__).resolve().parents[2] / "config" / "docmgr.yaml"
        if docmgr_yaml.exists():
            with open(docmgr_yaml, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            # 合并配置
            for k, v in cfg.items():
                if k in default_cfg and isinstance(default_cfg[k], dict) and isinstance(v, dict):
                    default_cfg[k].update(v)
                else:
                    default_cfg[k] = v
    except Exception:
        pass

    # 如果配置中没有 license_key，从环境变量获取
    if not default_cfg["license_key"]:
        default_cfg["license_key"] = os.environ.get("SW_DM_LICENSE_KEY", "")

    return default_cfg


def probe_docmgr() -> dict:
    """探测 Document Manager 可用性

    Returns:
        {
            "available": bool,
            "dll_found": bool,
            "dll_path": str,
            "license_key_present": bool,
            "com_factory_registered": bool,
            "reason": str,
        }
    """
    result = {
        "available": False,
        "dll_found": False,
        "dll_path": "",
        "license_key_present": False,
        "com_factory_registered": False,
        "reason": "",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    # 检测 DLL
    dll_path = find_swdm_dll()
    if dll_path:
        result["dll_found"] = True
        result["dll_path"] = dll_path
    else:
        result["reason"] = "SolidWorks.Interop.swdocumentmgr.dll 未找到"
        return result

    # 检测 license key
    key = get_license_key()
    if key:
        result["license_key_present"] = True
    else:
        result["reason"] = "SW_DM_LICENSE_KEY 未设置（Document Manager 需要 license key）"
        return result

    # 检测 COM Factory
    try:
        import win32com.client as wc
        factory = wc.Dispatch(SWDM_CLASS_FACTORY_PROGID)
        result["com_factory_registered"] = True

        # 尝试创建 Application
        try:
            app = factory.GetApplication(key)
            if app is not None:
                result["available"] = True
                result["reason"] = "Document Manager 可用"
            else:
                result["reason"] = "GetApplication 返回 null（license key 无效）"
        except Exception as e:
            result["reason"] = f"GetApplication 失败: {e}"
    except Exception as e:
        result["reason"] = f"SwDMClassFactory COM 未注册: {e}"

    return result


def read_drawing_references(drawing_path: str) -> dict:
    """使用 Document Manager 读取 drawing 的 external references

    Returns:
        {
            "success": bool,
            "references": list,
            "reference_count": int,
            "reason": str,
        }
    """
    drawing_path = str(Path(drawing_path).resolve())
    result = {
        "success": False,
        "references": [],
        "reference_count": 0,
        "reason": "",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    # 先探测
    probe = probe_docmgr()
    if not probe["available"]:
        result["reason"] = f"Document Manager 不可用: {probe['reason']}"
        return result

    try:
        import win32com.client as wc
        factory = wc.Dispatch(SWDM_CLASS_FACTORY_PROGID)
        app = factory.GetApplication(get_license_key())

        # 打开 document
        # SwDMDocumentType: swDmDocumentDrawing=3
        doc = app.GetDocument(drawing_path, 3, False)
        if doc is None:
            result["reason"] = "GetDocument 返回 null"
            return result

        # GetAllExternalReferences5
        try:
            refs = doc.GetAllExternalReferences5()
            if refs:
                refs_list = list(refs)
                result["references"] = refs_list
                result["reference_count"] = len(refs_list)
                result["success"] = True
                result["reason"] = "成功读取引用"
        except Exception as e:
            # 回退到 GetAllExternalReferences4
            try:
                refs = doc.GetAllExternalReferences4()
                if refs:
                    refs_list = list(refs)
                    result["references"] = refs_list
                    result["reference_count"] = len(refs_list)
                    result["success"] = True
                    result["reason"] = "成功读取引用 (v4)"
            except Exception as e2:
                result["reason"] = f"GetAllExternalReferences 失败: {e}; v4: {e2}"

        try:
            doc.Close()
        except Exception:
            pass

    except Exception as e:
        result["reason"] = f"read_drawing_references 异常: {e}"

    return result


def replace_reference(
    drawing_path: str,
    old_ref_path: str,
    new_ref_path: str,
) -> dict:
    """使用 Document Manager ReplaceReference 替换引用

    Returns:
        {
            "success": bool,
            "replaced": bool,
            "reason": str,
        }
    """
    drawing_path = str(Path(drawing_path).resolve())
    old_ref_path = str(Path(old_ref_path).resolve())
    new_ref_path = str(Path(new_ref_path).resolve())

    result = {
        "success": False,
        "replaced": False,
        "reason": "",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    probe = probe_docmgr()
    if not probe["available"]:
        result["reason"] = f"Document Manager 不可用: {probe['reason']}"
        return result

    try:
        import win32com.client as wc
        factory = wc.Dispatch(SWDM_CLASS_FACTORY_PROGID)
        app = factory.GetApplication(get_license_key())

        # 打开 document（可写）
        doc = app.GetDocument(drawing_path, 3, True)
        if doc is None:
            result["reason"] = "GetDocument 返回 null"
            return result

        # ReplaceReference
        try:
            ret = doc.ReplaceReference(old_ref_path, new_ref_path)
            result["replaced"] = bool(ret)
            result["success"] = True
            result["reason"] = "成功" if ret else "替换失败"
        except Exception as e:
            result["reason"] = f"ReplaceReference 失败: {e}"

        try:
            doc.Close()
        except Exception:
            pass

    except Exception as e:
        result["reason"] = f"replace_reference 异常: {e}"

    return result


def relink_drawing_references(
    drawing_path: str,
    part_path: str,
    run_dir: Path = None,
    run_id: str = "",
    mode: str = "",
) -> dict:
    """v2.1 Task 4: Document Manager 引用修复（支持 dry_run / apply）

    Args:
        drawing_path: SLDDRW 绝对路径
        part_path: 期望的 SLDPRT 绝对路径
        run_dir: run_dir 根目录
        run_id: run_id
        mode: "dry_run" (仅读取引用) / "apply" (执行 ReplaceReference)
              空字符串则使用 config/docmgr.yaml 的 default_mode

    Returns:
        {
            "success": bool,
            "overall_status": str,  # "success" / "warning" / "error"
            "mode": str,  # "dry_run" / "apply"
            "probe": dict,
            "references": list,
            "reference_count": int,
            "replaced_count": int,
            "reason": str,
        }
    """
    drawing_path = str(Path(drawing_path).resolve())
    part_path = str(Path(part_path).resolve())

    # 加载配置
    cfg = load_docmgr_config()
    if not mode:
        mode = cfg.get("default_mode", "dry_run")

    result = {
        "success": False,
        "overall_status": "warning",
        "mode": mode,
        "probe": {},
        "references": [],
        "reference_count": 0,
        "replaced_count": 0,
        "reason": "",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "method": "docmgr",
        "config": {
            "default_mode": cfg.get("default_mode", ""),
            "relink_enabled": cfg.get("relink", {}).get("enabled", True),
            "backup_before_replace": cfg.get("relink", {}).get("backup_before_replace", True),
        },
    }

    # 探测
    probe = probe_docmgr()
    result["probe"] = probe

    if not probe["available"]:
        result["overall_status"] = "warning"
        result["reason"] = f"Document Manager 不可用: {probe['reason']}"
        result["success"] = False

        # 写入结果
        if run_dir is not None:
            _write_result(run_dir, result, cfg)
        return result

    # 读取引用
    refs_result = read_drawing_references(drawing_path)
    result["references"] = refs_result.get("references", [])
    result["reference_count"] = refs_result.get("reference_count", 0)

    if not refs_result["success"]:
        result["overall_status"] = "warning"
        result["reason"] = f"读取引用失败: {refs_result['reason']}"
        result["success"] = False
        if run_dir is not None:
            _write_result(run_dir, result, cfg)
        return result

    # 检查是否需要替换
    needs_replace = False
    old_ref = ""
    for ref in result["references"]:
        if not str(ref).lower().endswith(part_path.lower()):
            needs_replace = True
            old_ref = ref
            break

    if not needs_replace:
        result["overall_status"] = "success"
        result["success"] = True
        result["reason"] = "引用已正确，无需替换"
        if run_dir is not None:
            _write_result(run_dir, result, cfg)
        return result

    # dry_run 模式：仅报告，不执行替换
    if mode == "dry_run":
        result["overall_status"] = "warning"
        result["success"] = False
        result["reason"] = f"dry_run 模式：检测到需要替换的引用 ({old_ref} -> {part_path})，但未执行"
        result["would_replace"] = {"old_ref": old_ref, "new_ref": part_path}
        if run_dir is not None:
            _write_result(run_dir, result, cfg)
        return result

    # apply 模式：执行替换
    # 备份
    if cfg.get("relink", {}).get("backup_before_replace", True) and run_dir is not None:
        try:
            import shutil
            backup_dir = Path(run_dir) / cfg.get("relink", {}).get("backup_dir", "input_work")
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / (Path(drawing_path).name + ".bak")
            shutil.copy2(drawing_path, backup_path)
            result["backup_path"] = str(backup_path)
        except Exception as e:
            result["backup_error"] = str(e)

    # 替换引用
    replace_result = replace_reference(drawing_path, old_ref, part_path)
    result["replaced_count"] = 1 if replace_result.get("replaced") else 0
    result["overall_status"] = "success" if replace_result.get("replaced") else "warning"
    result["success"] = replace_result.get("replaced", False)
    result["reason"] = replace_result.get("reason", "")

    if run_dir is not None:
        _write_result(run_dir, result, cfg)

    return result


def _write_result(run_dir: Path, result: dict, cfg: dict = None) -> Path:
    """写入 docmgr_result.json（v2.1 重命名）"""
    try:
        qc_dir = Path(run_dir) / "qc"
        qc_dir.mkdir(parents=True, exist_ok=True)
        # v2.1: 文件名改为 docmgr_result.json（同时保留 docmgr_relink_result.json 兼容）
        result_file = "docmgr_result.json"
        if cfg and cfg.get("output", {}).get("result_file"):
            result_file = cfg["output"]["result_file"]
        out_path = qc_dir / result_file
        out_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        # 同时写入兼容文件名
        compat_path = qc_dir / "docmgr_relink_result.json"
        compat_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return out_path
    except Exception:
        return None


def main():
    """CLI: python docmgr_service.py probe|read <drawing_path>"""
    import sys
    if len(sys.argv) < 2:
        print("Usage: python docmgr_service.py probe|read <drawing_path>")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "probe":
        result = probe_docmgr()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif cmd == "read":
        if len(sys.argv) < 3:
            print("Usage: read <drawing_path>")
            sys.exit(1)
        result = read_drawing_references(sys.argv[2])
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
