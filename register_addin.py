"""v1.9 Task 2: SOLIDWORKS Add-in 注册工具

将 SwDrawingStudioAddin.dll 注册到:
1. Windows COM (regasm)
2. SOLIDWORKS Add-in Manager (注册表 HKLM\\SOFTWARE\\SolidWorks\\AddIns\\{CLSID})

使用方法:
  python register_addin.py register <dll_path>
  python register_addin.py unregister <dll_path>
  python register_addin.py probe
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
ADDIN_DLL = REPO_ROOT / "tools" / "SwDrawingStudioAddin" / "bin" / "SwDrawingStudioAddin.dll"
ADDIN_CLSID = "{B8F3E2A1-7C4D-4E5F-9A6B-1D2E3F4A5B6C}"
ADDIN_PROGID = "SwDrawingStudioAddin.AddinAPI"

# regasm 路径
REGASM_PATHS = [
    r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\regasm.exe",
    r"C:\Windows\Microsoft.NET\Framework\v4.0.30319\regasm.exe",
]


def find_regasm() -> str:
    for p in REGASM_PATHS:
        if Path(p).exists():
            return p
    return ""


def register_com(dll_path: Path) -> tuple:
    """注册 COM（regasm）"""
    regasm = find_regasm()
    if not regasm:
        return False, "未找到 regasm.exe"

    cmd = [regasm, "/codebase", str(dll_path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, f"regasm 失败 (rc={result.returncode}): {result.stderr}"
    except Exception as e:
        return False, f"regasm 异常: {e}"


def unregister_com(dll_path: Path) -> tuple:
    """注销 COM"""
    regasm = find_regasm()
    if not regasm:
        return False, "未找到 regasm.exe"

    cmd = [regasm, "/u", str(dll_path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, f"regasm /u 失败 (rc={result.returncode}): {result.stderr}"
    except Exception as e:
        return False, f"regasm /u 异常: {e}"


def register_sw_addin() -> tuple:
    """注册到 SOLIDWORKS Add-in Manager（注册表）"""
    import winreg

    # 注册表路径: HKLM\SOFTWARE\SolidWorks\AddIns\{CLSID}
    # 32-bit SW: HKLM\SOFTWARE\SolidWorks\AddIns
    # 64-bit SW: HKLM\SOFTWARE\SolidWorks\AddIns
    reg_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\SolidWorks\AddIns\\" + ADDIN_CLSID),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\SolidWorks\AddIns\\" + ADDIN_CLSID),
    ]

    success_count = 0
    messages = []

    for hive, path in reg_paths:
        try:
            key = winreg.CreateKey(hive, path)
            # 默认值 = 0 (启用)
            winreg.SetValueEx(key, None, 0, winreg.REG_DWORD, 0)
            # Title
            winreg.SetValueEx(key, "Title", 0, winreg.REG_SZ, "SW Drawing Studio Add-in")
            # Description
            winreg.SetValueEx(key, "Description", 0, winreg.REG_SZ, "v1.9 CAD Core Add-in for associative dimensions and reference relink")
            winreg.CloseKey(key)
            success_count += 1
            messages.append(f"注册成功: {path}")
        except PermissionError:
            messages.append(f"权限不足（需管理员）: {path}")
        except Exception as e:
            messages.append(f"注册失败 {path}: {e}")

    return success_count > 0, "; ".join(messages)


def unregister_sw_addin() -> tuple:
    """从 SOLIDWORKS Add-in Manager 注销"""
    import winreg

    reg_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\SolidWorks\AddIns\\" + ADDIN_CLSID),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\SolidWorks\AddIns\\" + ADDIN_CLSID),
    ]

    success_count = 0
    messages = []

    for hive, path in reg_paths:
        try:
            winreg.DeleteKey(hive, path)
            success_count += 1
            messages.append(f"注销成功: {path}")
        except FileNotFoundError:
            messages.append(f"键不存在: {path}")
        except Exception as e:
            messages.append(f"注销失败 {path}: {e}")

    return success_count > 0, "; ".join(messages)


def probe_addin() -> dict:
    """探测 Add-in 是否可用"""
    result = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dll_exists": ADDIN_DLL.exists(),
        "dll_path": str(ADDIN_DLL),
        "com_registered": False,
        "sw_addin_registered": False,
        "sw_running": False,
        "addin_loaded": False,
        "ping_result": False,
        "method": "none",
        "reason": "",
    }

    # 检查 COM 注册
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, ADDIN_PROGID)
        winreg.CloseKey(key)
        result["com_registered"] = True
    except FileNotFoundError:
        # 也检查 HKCU
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\\" + ADDIN_PROGID)
            winreg.CloseKey(key)
            result["com_registered"] = True
        except FileNotFoundError:
            result["reason"] = "COM 未注册"
        except Exception as e:
            result["reason"] = f"COM 检查异常: {e}"
    except Exception as e:
        result["reason"] = f"COM 检查异常: {e}"

    # 检查 SW Add-in 注册
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\SolidWorks\AddIns\\" + ADDIN_CLSID)
        winreg.CloseKey(key)
        result["sw_addin_registered"] = True
    except FileNotFoundError:
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\SolidWorks\AddIns\\" + ADDIN_CLSID)
            winreg.CloseKey(key)
            result["sw_addin_registered"] = True
        except FileNotFoundError:
            if not result["reason"]:
                result["reason"] = "SW Add-in 未注册（HKLM/HKCU 均无）"
        except Exception:
            pass
    except Exception:
        pass

    # 使用 sw_addin_client.ping() 进行完整探测（支持 Dispatch + ConnectToSW）
    try:
        # 添加项目根目录到 sys.path
        import sys
        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        from app.services.sw_addin_client import ping as addin_ping
        ping_result = addin_ping()
        result["sw_running"] = ping_result.get("sw_running", False)
        result["addin_loaded"] = ping_result.get("addin_loaded", False)
        result["ping_result"] = ping_result.get("ping_result", False)
        result["method"] = ping_result.get("method", "none")
        result["available"] = ping_result.get("available", False)
        if ping_result.get("reason"):
            result["reason"] = ping_result["reason"]
    except Exception as e:
        result["reason"] = f"ping 异常: {e}"

    # 写入 probe 结果
    probe_path = REPO_ROOT / "drw_output" / "addin_probe_result.json"
    probe_path.parent.mkdir(parents=True, exist_ok=True)
    probe_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python register_addin.py register [dll_path]")
        print("  python register_addin.py unregister [dll_path]")
        print("  python register_addin.py probe")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "register":
        dll = Path(sys.argv[2]) if len(sys.argv) > 2 else ADDIN_DLL
        if not dll.exists():
            print(f"FAIL: DLL 不存在: {dll}")
            sys.exit(1)

        print(f"注册 COM: {dll}")
        ok, msg = register_com(dll)
        print(f"  COM: {'OK' if ok else 'FAIL'} - {msg[:200]}")

        print("注册 SW Add-in Manager...")
        ok2, msg2 = register_sw_addin()
        print(f"  SW: {'OK' if ok2 else 'FAIL'} - {msg2[:200]}")

        if ok and ok2:
            print("\n注册成功，请重启 SolidWorks 使 Add-in 生效")
        else:
            print("\n注册部分失败，请检查消息")

    elif cmd == "unregister":
        dll = Path(sys.argv[2]) if len(sys.argv) > 2 else ADDIN_DLL

        print("注销 SW Add-in Manager...")
        ok, msg = unregister_sw_addin()
        print(f"  SW: {'OK' if ok else 'FAIL'} - {msg[:200]}")

        print(f"注销 COM: {dll}")
        ok2, msg2 = unregister_com(dll)
        print(f"  COM: {'OK' if ok2 else 'FAIL'} - {msg2[:200]}")

    elif cmd == "probe":
        result = probe_addin()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
