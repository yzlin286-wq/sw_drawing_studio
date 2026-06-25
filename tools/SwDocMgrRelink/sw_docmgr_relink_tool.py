"""v1.9 Task 4: SwDocMgrRelink C# 工具

使用 SOLIDWORKS Document Manager API 读取/替换 SLDDRW 引用
需要 SolidWorks.Interop.swdocumentmgr.dll 和 license key

编译:
  csc.exe /nologo /platform:anycpu /target:library /out:bin/SwDocMgrRelink.dll ^
    /reference:"C:\Program Files\SOLIDWORKS Corp25\SOLIDWORKS\SolidWorks.Interop.swdocumentmgr.dll" ^
    /reference:System.dll /reference:System.Runtime.InteropServices.dll ^
    SwDocMgrRelink.cs

使用 (Python COM):
  import win32com.client as wc
  factory = wc.Dispatch('SwDocumentMgr.SwDMClassFactory')
  dm_app = factory.CreateInstance(license_key)
  dm_doc = dm_app.GetDocument(drawing_path, 3, True)  # ReadOnly
  refs = dm_doc.GetExternalReferences()
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TOOL_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = REPO_ROOT / "drw_output" / "v1_9_docmgr"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Document Manager DLL
DM_DLL_CANDIDATES = [
    r"C:\Program Files\SOLIDWORKS Corp25\SOLIDWORKS\SolidWorks.Interop.swdocumentmgr.dll",
    r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\SolidWorks.Interop.swdocumentmgr.dll",
]


def find_dm_dll() -> str:
    for p in DM_DLL_CANDIDATES:
        if Path(p).exists():
            return p
    return ""


def probe() -> dict:
    """探测 Document Manager 环境"""
    result = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dm_dll_found": False,
        "dm_dll_path": "",
        "license_key_available": False,
        "com_factory_available": False,
        "available": False,
        "reason": "",
    }

    # 检查 DLL
    dll = find_dm_dll()
    if dll:
        result["dm_dll_found"] = True
        result["dm_dll_path"] = dll
    else:
        result["reason"] = "SolidWorks.Interop.swdocumentmgr.dll 未找到"

    # 检查 license key
    license_key = os.environ.get("SW_DM_LICENSE_KEY", "")
    if license_key:
        result["license_key_available"] = True
    else:
        if not result["reason"]:
            result["reason"] = "无 SW_DM_LICENSE_KEY 环境变量（Document Manager license key）"

    # 检查 COM Factory
    try:
        import win32com.client as wc
        factory = wc.Dispatch("SwDocumentMgr.SwDMClassFactory")
        result["com_factory_available"] = True
    except Exception as e:
        if not result["reason"]:
            result["reason"] = f"SwDocumentMgr.SwDMClassFactory COM 未注册: {e}"

    # 综合判断
    result["available"] = (
        result["dm_dll_found"]
        and result["license_key_available"]
        and result["com_factory_available"]
    )

    if result["available"]:
        result["reason"] = "Document Manager 可用"

    return result


def read_references(drawing_path: str) -> dict:
    """读取 drawing 引用"""
    result = {
        "success": False,
        "references": [],
        "reason": "",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    probe_result = probe()
    if not probe_result["available"]:
        result["reason"] = f"Document Manager 不可用: {probe_result['reason']}"
        result["probe"] = probe_result
        return result

    try:
        import win32com.client as wc

        license_key = os.environ.get("SW_DM_LICENSE_KEY", "")
        factory = wc.Dispatch("SwDocumentMgr.SwDMClassFactory")
        dm_app = factory.CreateInstance(license_key)

        drawing_path = str(Path(drawing_path).resolve())
        # swDocDRAWING=3, ReadOnly=True
        dm_doc = dm_app.GetDocument(drawing_path, 3, True)

        if dm_doc is None:
            result["reason"] = "GetDocument 返回 null"
            return result

        refs = dm_doc.GetExternalReferences()
        if refs:
            if isinstance(refs, (list, tuple)):
                result["references"] = list(refs)
            else:
                result["references"] = [str(refs)]

        result["success"] = True
        result["reason"] = f"读取到 {len(result['references'])} 个引用"

        dm_doc.Close()

    except Exception as e:
        result["reason"] = f"读取引用异常: {e}"

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python sw_docmgr_relink_tool.py probe")
        print("  python sw_docmgr_relink_tool.py read <drawing_path>")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "probe":
        result = probe()
        print(json.dumps(result, ensure_ascii=False, indent=2))

        # 写入结果
        out_path = OUTPUT_DIR / "docmgr_relink_result.json"
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nResult written to: {out_path}")

    elif cmd == "read":
        if len(sys.argv) < 3:
            print("Usage: python sw_docmgr_relink_tool.py read <drawing_path>")
            sys.exit(1)
        result = read_references(sys.argv[2])
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
