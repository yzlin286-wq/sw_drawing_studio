"""Diagnose Add-in COM object: list available methods and test v2.1 methods"""
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))


def main():
    print("=" * 60)
    print("Add-in COM 诊断")
    print("=" * 60)

    # 1. Get SW
    sw = None
    try:
        import win32com.client as wc
        sw = wc.Dispatch("SldWorks.Application")
        rev = sw.RevisionNumber()
        print(f"  SW running: {rev}")
    except Exception as e:
        # Try alternative
        try:
            sw = wc.GetActiveObject("SldWorks.Application")
            print(f"  SW running (GetActiveObject): {sw.RevisionNumber}")
        except Exception as e2:
            print(f"  SW not running: {e} / {e2}")
            return

    # 2. Dispatch Add-in
    ADDIN_PROGID = "SwDrawingStudioAddin.AddinAPI"
    try:
        addin = wc.Dispatch(ADDIN_PROGID)
        print(f"  Add-in dispatched: {addin}")
    except Exception as e:
        print(f"  Dispatch failed: {e}")
        return

    # 3. Connect to SW
    try:
        if not addin.Ping():
            ok = addin.ConnectToSW(sw, 88001)
            print(f"  ConnectToSW: {ok}")
        else:
            print(f"  Ping=True (already connected)")
    except Exception as e:
        print(f"  ConnectToSW exception: {e}")

    # 4. List available methods via IDispatch
    print("\n--- 4. List available methods ---")
    # Try to get type info
    try:
        type_lib = addin._oleobj_.GetTypeInfo()
        type_info = type_lib.GetTypeComp()
        print(f"  TypeLib available")
    except Exception as e:
        print(f"  No TypeLib: {e}")

    # 5. Test each known method
    print("\n--- 5. Test known methods ---")
    test_methods = [
        "Ping",
        "ProbeContext",
        "GenerateDimensionsV3",
        "SeedPMI",
        "ExtractViewEntitiesV2",
        "GenerateAssociativeDimensions",
    ]
    for method_name in test_methods:
        try:
            # Check if method exists via getattr
            attr = getattr(addin, method_name)
            print(f"  {method_name}: FOUND (callable={callable(attr)})")
        except AttributeError as e:
            print(f"  {method_name}: NOT FOUND - {e}")
        except Exception as e:
            print(f"  {method_name}: ERROR - {type(e).__name__}: {e}")

    # 6. Try dynamic dispatch
    print("\n--- 6. Try dynamic dispatch ---")
    try:
        addin_dyn = wc.dynamic.Dispatch(ADDIN_PROGID)
        if not addin_dyn.Ping():
            addin_dyn.ConnectToSW(sw, 88002)
        for method_name in ["GenerateDimensionsV3", "SeedPMI", "ExtractViewEntitiesV2"]:
            try:
                attr = getattr(addin_dyn, method_name)
                print(f"  dynamic.{method_name}: FOUND (callable={callable(attr)})")
            except AttributeError as e:
                print(f"  dynamic.{method_name}: NOT FOUND - {e}")
            except Exception as e:
                print(f"  dynamic.{method_name}: ERROR - {type(e).__name__}: {e}")
    except Exception as e:
        print(f"  dynamic dispatch failed: {e}")

    # 7. Check DLL file details
    print("\n--- 7. DLL file details ---")
    dll_path = REPO / "tools" / "SwDrawingStudioAddin" / "bin" / "SwDrawingStudioAddin.dll"
    if dll_path.exists():
        stat = dll_path.stat()
        print(f"  Path: {dll_path}")
        print(f"  Size: {stat.st_size} bytes")
        print(f"  Modified: {time.ctime(stat.st_mtime)}")

    # 8. Check registry CodeBase
    print("\n--- 8. Registry CodeBase ---")
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Classes\CLSID\{B8F3E2A1-7C4D-4E5F-9A6B-1D2E3F4A5B6C}\InprocServer32",
        )
        codebase, _ = winreg.QueryValueEx(key, "CodeBase")
        print(f"  CodeBase: {codebase}")
        winreg.CloseKey(key)
    except Exception as e:
        print(f"  Registry read failed: {e}")

    # 9. Try calling GenerateDimensionsV3 with minimal args to see exact error
    print("\n--- 9. Direct call test ---")
    try:
        # Use IDispatch directly
        disp = addin._oleobj_
        # Try GetIDsOfNames
        try:
            dispid = disp.GetIDsOfNames("GenerateDimensionsV3")
            print(f"  GetIDsOfNames('GenerateDimensionsV3') = {dispid}")
        except Exception as e:
            print(f"  GetIDsOfNames failed: {e}")

        try:
            dispid = disp.GetIDsOfNames("SeedPMI")
            print(f"  GetIDsOfNames('SeedPMI') = {dispid}")
        except Exception as e:
            print(f"  GetIDsOfNames('SeedPMI') failed: {e}")

        try:
            dispid = disp.GetIDsOfNames("ExtractViewEntitiesV2")
            print(f"  GetIDsOfNames('ExtractViewEntitiesV2') = {dispid}")
        except Exception as e:
            print(f"  GetIDsOfNames('ExtractViewEntitiesV2') failed: {e}")

        try:
            dispid = disp.GetIDsOfNames("Ping")
            print(f"  GetIDsOfNames('Ping') = {dispid}")
        except Exception as e:
            print(f"  GetIDsOfNames('Ping') failed: {e}")
    except Exception as e:
        print(f"  Direct call test failed: {e}")

    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
