"""v1.9 Task 4: Document Manager 引用修复服务

使用 SOLIDWORKS Document Manager API 读取 SLDDRW external references
尝试 ReplaceReference old→new
没有 license key 时返回 warning，不阻断主流程

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
SWDM_FACTORY_PROGID = "SwDocumentMgr.SwDMClassFactory"

# 默认 license key（空字符串表示无 license）
# 实际使用时需要从环境变量或配置文件读取
DM_LICENSE_KEY = os.environ.get("SW_DM_LICENSE_KEY", "")


def probe_docmgr() -> dict:
    """探测 Document Manager 是否可用

    Returns:
        {
            "available": bool,
            "dll_found": bool,
            "dll_path": str,
            "com_registered": bool,
            "license_key_available": bool,
            "reason": str,
            "timestamp": str,
        }
    """
    result = {
        "available": False,
        "dll_found": False,
        "dll_path": "",
        "com_registered": False,
        "license_key_available": False,
        "reason": "",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    # 检查 DLL
    dll_paths = [
        r"C:\Program Files\SOLIDWORKS Corp25\SOLIDWORKS\SolidWorks.Interop.swdocumentmgr.dll",
        r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\SolidWorks.Interop.swdocumentmgr.dll",
        r"C:\Program Files\SolidWorks Corp\SolidWorks\SolidWorks.Interop.swdocumentmgr.dll",
    ]
    for p in dll_paths:
        if Path(p).exists():
            result["dll_found"] = True
            result["dll_path"] = p
            break

    # 检查 COM 注册
    try:
        import win32com.client as wc
        factory = wc.Dispatch(SWDM_FACTORY_PROGID)
        result["com_registered"] = True
    except Exception as e:
        result["reason"] = f"SwDocumentMgr COM 未注册: {e}"

    # 检查 license key
    if DM_LICENSE_KEY:
        result["license_key_available"] = True
    else:
        if not result["reason"]:
            result["reason"] = "无 Document Manager license key（设置 SW_DM_LICENSE_KEY 环境变量）"

    # 综合判断
    result["available"] = result["dll_found"] and result["com_registered"] and result["license_key_available"]

    return result


def read_drawing_references(drawing_path: str) -> dict:
    """读取 SLDDRW 的 external references

    Returns:
        {
            "success": bool,
            "references": list,
            "reason": str,
            "timestamp": str,
        }
    """
    result = {
        "success": False,
        "references": [],
        "reason": "",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    drawing_path = str(Path(drawing_path).resolve())

    # 检查 Document Manager 是否可用
    probe = probe_docmgr()
    if not probe["available"]:
        result["reason"] = f"Document Manager 不可用: {probe['reason']}"
        result["probe"] = probe
        return result

    try:
        import win32com.client as wc

        # 创建 ClassFactory
        factory = wc.Dispatch(SWDM_FACTORY_PROGID)

        # 创建 Application
        dm_app = factory.CreateInstance(DM_LICENSE_KEY)

        # 打开文档
        # SwDMDocumentOpenType: 1=ReadOnly, 2=ReadWrite
        dm_doc = dm_app.GetDocument(drawing_path, 3, True)  # swDocDRAWING=3, ReadOnly=True

        if dm_doc is None:
            result["reason"] = "GetDocument 返回 null"
            return result

        # 获取外部引用
        refs = dm_doc.GetExternalReferences()
        if refs:
            result["references"] = list(refs)

        result["success"] = True
        result["reason"] = f"读取到 {len(result['references'])} 个引用"

        # 关闭文档
        dm_doc.Close()

    except Exception as e:
        result["reason"] = f"读取引用异常: {e}"

    return result


def replace_reference(drawing_path: str, old_path: str, new_path: str) -> dict:
    """替换引用

    Returns:
        {
            "success": bool,
            "replaced": bool,
            "reason": str,
            "timestamp": str,
        }
    """
    result = {
        "success": False,
        "replaced": False,
        "reason": "",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    drawing_path = str(Path(drawing_path).resolve())
    old_path = str(Path(old_path).resolve())
    new_path = str(Path(new_path).resolve())

    probe = probe_docmgr()
    if not probe["available"]:
        result["reason"] = f"Document Manager 不可用: {probe['reason']}"
        result["probe"] = probe
        return result

    try:
        import win32com.client as wc

        factory = wc.Dispatch(SWDM_FACTORY_PROGID)
        dm_app = factory.CreateInstance(DM_LICENSE_KEY)

        # 以读写方式打开
        dm_doc = dm_app.GetDocument(drawing_path, 3, False)  # ReadOnly=False

        if dm_doc is None:
            result["reason"] = "GetDocument 返回 null"
            return result

        # ReplaceReference
        replaced = dm_doc.ReplaceReference(old_path, new_path)
        result["replaced"] = bool(replaced)
        result["success"] = bool(replaced)
        result["reason"] = "成功" if replaced else "替换失败"

        dm_doc.Close()

    except Exception as e:
        result["reason"] = f"替换引用异常: {e}"

    return result


def relink_drawing_references(
    drawing_path: str,
    expected_part_path: str,
    run_dir: Path,
    run_id: str = "",
) -> dict:
    """修复 drawing 引用（主入口）

    Args:
        drawing_path: SLDDRW 绝对路径
        expected_part_path: 期望的 SLDPRT 绝对路径
        run_dir: run_dir 根目录
        run_id: run_id

    Returns:
        {
            "success": bool,
            "method": str,
            "references_before": list,
            "references_after": list,
            "replaced_count": int,
            "reason": str,
            "timestamp": str,
            "probe": dict,
        }
    """
    result = {
        "success": False,
        "method": "docmgr",
        "references_before": [],
        "references_after": [],
        "replaced_count": 0,
        "reason": "",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "probe": {},
    }

    drawing_path = str(Path(drawing_path).resolve())
    expected_part_path = str(Path(expected_part_path).resolve())

    # 探测 Document Manager
    probe = probe_docmgr()
    result["probe"] = probe

    if not probe["available"]:
        result["reason"] = f"Document Manager 不可用（warning，不阻断）: {probe['reason']}"
        result["method"] = "docmgr_unavailable"
        return result

    # 读取引用前
    refs_before = read_drawing_references(drawing_path)
    result["references_before"] = refs_before.get("references", [])

    # 检查是否需要替换
    need_replace = False
    old_path = ""
    for ref in result["references_before"]:
        if ref != expected_part_path:
            need_replace = True
            old_path = ref
            break

    if need_replace:
        # 尝试替换
        replace_result = replace_reference(drawing_path, old_path, expected_part_path)
        if replace_result.get("replaced"):
            result["replaced_count"] = 1
            result["success"] = True
            result["reason"] = f"替换成功: {old_path} -> {expected_part_path}"
        else:
            result["reason"] = f"替换失败: {replace_result.get('reason', '')}"
    else:
        result["success"] = True
        result["reason"] = "引用已正确，无需替换"

    # 读取引用后
    refs_after = read_drawing_references(drawing_path)
    result["references_after"] = refs_after.get("references", [])

    return result


def write_docmgr_result(run_dir: Path, result: dict) -> Path:
    """写入 docmgr_relink_result.json"""
    qc_dir = run_dir / "qc"
    qc_dir.mkdir(parents=True, exist_ok=True)
    out_path = qc_dir / "docmgr_relink_result.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def main():
    """CLI: python sw_docmgr_relink.py probe|read <drawing_path>"""
    import sys
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python sw_docmgr_relink.py probe")
        print("  python sw_docmgr_relink.py read <drawing_path>")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "probe":
        result = probe_docmgr()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif cmd == "read":
        if len(sys.argv) < 3:
            print("Usage: python sw_docmgr_relink.py read <drawing_path>")
            sys.exit(1)
        result = read_drawing_references(sys.argv[2])
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
