"""
SolidWorks 本地连接探针
- 检查 Python 位数
- 检查 pywin32 / comtypes 是否就绪
- 尝试 GetActiveObject 已运行实例 -> 否则 Dispatch 启动新实例
- 列出 SolidWorks 版本、ActiveDoc、API 关键能力点
"""
import os
import sys
import platform
import traceback

print("=== Python 环境 ===")
print(f"executable     : {sys.executable}")
print(f"version        : {platform.python_version()}  ({platform.architecture()[0]})")
print(f"cwd            : {os.getcwd()}")

deps_ok = True
try:
    import win32com.client as win32com_client
    import pythoncom
    from pywintypes import com_error
    print("pywin32         : OK")
except Exception as exc:
    deps_ok = False
    print(f"pywin32         : MISSING ({exc})")

try:
    import comtypes  # noqa: F401
    print("comtypes        : OK")
except Exception as exc:
    print(f"comtypes        : MISSING ({exc})  -> 不影响基本 COM，但 Skill 需要")

if not deps_ok:
    print("\n[STOP] 需要先 pip install \"pywin32>=305\" \"comtypes>=1.2.0\"")
    sys.exit(2)

print("\n=== 注册表中的 SolidWorks 安装 ===")
try:
    import winreg
    found_any = False
    for hive, sub in [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\SolidWorks"),
        (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\SolidWorks"),
    ]:
        try:
            with winreg.OpenKey(hive, sub) as key:
                i = 0
                while True:
                    try:
                        sub_name = winreg.EnumKey(key, i)
                        if "SOLIDWORKS" in sub_name.upper() or sub_name.startswith("SOLIDWORKS"):
                            print(f"  {sub}\\{sub_name}")
                            found_any = True
                        i += 1
                    except OSError:
                        break
        except OSError:
            continue
    if not found_any:
        print("  (未在 HKLM/HKCU SOFTWARE\\SolidWorks 下发现版本子键)")
except Exception as exc:
    print(f"  注册表查询失败: {exc}")

print("\n=== 尝试连接 SolidWorks COM ===")
sw = None
try:
    sw = win32com_client.GetActiveObject("SldWorks.Application")
    print("[OK] 已经连接到运行中的 SolidWorks")
except Exception as exc:
    print(f"[INFO] 没有运行中的实例: {exc}")
    print("[..]  尝试 Dispatch('SldWorks.Application') 启动新实例")
    try:
        sw = win32com_client.Dispatch("SldWorks.Application")
        sw.Visible = True
        print("[OK] 启动新实例成功")
    except Exception as exc2:
        print(f"[FAIL] Dispatch 失败: {exc2}")
        traceback.print_exc()
        sys.exit(3)

print("\n=== SolidWorks 版本信息 ===")
try:
    rev = sw.RevisionNumber() if callable(getattr(sw, "RevisionNumber", None)) else sw.RevisionNumber
except Exception:
    rev = "?"
try:
    major = int(str(rev).split(".")[0])
    year = major - 8 + 2000
    print(f"RevisionNumber : {rev}  (~SolidWorks {year})")
except Exception:
    print(f"RevisionNumber : {rev}")

try:
    print(f"Visible        : {sw.Visible}")
except Exception:
    pass

print("\n=== 当前活动文档 ===")
try:
    model = sw.ActiveDoc
except Exception:
    model = None
if model is None:
    print("  (没有打开的文档)")
else:
    try:
        title = model.GetTitle() if callable(getattr(model, "GetTitle", None)) else model.GetTitle
    except Exception:
        title = "?"
    try:
        path = model.GetPathName() if callable(getattr(model, "GetPathName", None)) else model.GetPathName
    except Exception:
        path = "?"
    try:
        dt = model.GetType() if callable(getattr(model, "GetType", None)) else model.GetType
    except Exception:
        dt = "?"
    label = {1: "Part", 2: "Assembly", 3: "Drawing"}.get(dt, str(dt))
    print(f"Title          : {title}")
    print(f"PathName       : {path}")
    print(f"Type           : {label}")

print("\n=== 关键 API 能力点探测 ===")
def probe(obj, name):
    try:
        m = getattr(obj, name)
        return "OK" if m is not None else "None"
    except Exception as exc:
        return f"FAIL ({exc.__class__.__name__})"

for name in ["NewDocument", "OpenDoc6", "CloseDoc",
             "GetUserPreferenceStringValue", "GetExportFileData",
             "ActivateDoc3", "FrameWidth", "RevisionNumber"]:
    print(f"  ISldWorks.{name:30s} {probe(sw, name)}")

print("\n=== 已可用功能预览 ===")
print(" - 新建/打开/保存/关闭 零件/装配/工程图")
print(" - 草图与基础特征 (拉伸/切除/旋转/倒圆/倒角/阵列/抽壳/镜像/筋)")
print(" - 装配体加件 + Mate (重合/距离/同心/Gear/Hinge)")
print(" - Motion Study + 旋转马达 + Calculate/Play")
print(" - 工程图 三视图/剖视/局部放大/BOM/PDF")
print(" - 文件导出 STEP/STL/IGES/Parasolid/PDF/DXF/DWG (单件 + 批量)")
print(" - 自定义属性 / 配置 / 设计表 (需扩展)")
print(" - 多视角 BMP 预览 + JSON/MD 自审查报告")
print("\nDONE.")
