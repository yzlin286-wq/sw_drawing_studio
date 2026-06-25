"""refdoc relink 服务 — 5 策略接口（Spec enhance-v1-1 Task 9）

为 v1.2 refdoc 强修预留的统一接口。
当前默认关闭；UI 通过设置中"实验性 refdoc 强修"开关开启。

策略：
1. pywin32_late          — 已实现（沿用 v6 [9.8/9] ReplaceViewModel 路径）
2. pywin32_ensure_dispatch — not_implemented
3. vba_macro             — not_implemented（占位，等待 relink_refdoc.swp）
4. dotnet_sidecar        — not_implemented（占位，等待 SwRelink.exe）
5. auto                  — 顺序尝试 pywin32_late → vba_macro → dotnet_sidecar
"""
from __future__ import annotations
from pathlib import Path
from typing import Any

from app.services.solidworks_global_lock import require_current_job_lock

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

VALID_STRATEGIES = ("auto", "pywin32_late", "pywin32_ensure_dispatch", "vba_macro", "dotnet_sidecar")


def _lock_blocked_payload(guard: dict[str, Any], view_names: list[str], strategy: str) -> dict:
    return {
        "ok": False,
        "strategy_used": strategy,
        "attempts": [{
            "strategy": strategy,
            "ok": False,
            "message": "blocked_by_solidworks_lock",
            "lock_conflict": guard,
        }],
        "name_match_count": 0,
        "ref_present_count": 0,
        "bad_ref_count": len(view_names),
        "severity": "warning",
        "status": "blocked_by_solidworks_lock",
        "failure_bucket": "solidworks_lock_conflict",
        "lock_conflict": guard,
    }


def _lock_blocked_attempt(guard: dict[str, Any]) -> dict:
    return {
        "ok": False,
        "message": "blocked_by_solidworks_lock",
        "status": "blocked_by_solidworks_lock",
        "failure_bucket": "solidworks_lock_conflict",
        "lock_conflict": guard,
    }


def _strategy_pywin32_late(drawing_path: str, part_path: str, view_names: list[str]) -> dict:
    """复用 v6 [9.8/9] 路径：drw.ReplaceViewModel(part_abs, names_arr, inst_arr)"""
    guard = require_current_job_lock("refdoc_relink_service._strategy_pywin32_late")
    if not guard.get("ok"):
        return _lock_blocked_attempt(guard)
    try:
        import win32com.client
        from win32com.client import VARIANT
        import pythoncom
        sw = win32com.client.GetActiveObject("SldWorks.Application")
        if sw is None:
            return {"ok": False, "message": "SolidWorks 未启动"}
        # 取当前活动 drawing
        drw = sw.ActiveDoc
        if drw is None:
            return {"ok": False, "message": "无活动 drawing 文档"}
        # 调 ReplaceViewModel
        try:
            names_arr = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, view_names)
            inst_arr = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, [None] * len(view_names))
            ok = drw.ReplaceViewModel(str(Path(part_path).resolve()), names_arr, inst_arr)
            return {"ok": bool(ok), "message": f"ReplaceViewModel returned {ok}"}
        except Exception as e:
            try:
                ok = drw.ReplaceViewModel(str(Path(part_path).resolve()), view_names, None)
                return {"ok": bool(ok), "message": f"ReplaceViewModel(plain) returned {ok}"}
            except Exception as e2:
                return {"ok": False, "message": f"ReplaceViewModel failed: {e2}"}
    except Exception as e:
        return {"ok": False, "message": f"pywin32_late attempt failed: {e}"}


def _strategy_ensure_dispatch(*args, **kwargs) -> dict:
    return {"ok": False, "message": "not_implemented (early-binding via gencache.EnsureDispatch 暂未实现)"}


def _strategy_vba_macro(drawing_path: str, part_path: str, view_names: list[str]) -> dict:
    guard = require_current_job_lock("refdoc_relink_service._strategy_vba_macro")
    if not guard.get("ok"):
        return _lock_blocked_attempt(guard)
    swp = REPO_ROOT / "templates" / "macros" / "relink_refdoc.swp"
    if not swp.exists():
        return {"ok": False, "message": f"not_implemented (relink_refdoc.swp 缺失: {swp})"}
    try:
        import win32com.client
        sw = win32com.client.GetActiveObject("SldWorks.Application")
        ok = sw.RunMacro2(str(swp), "relink_refdoc", "main", 1, 0)
        return {"ok": bool(ok), "message": f"RunMacro2 returned {ok}"}
    except Exception as e:
        return {"ok": False, "message": f"VBA macro attempt failed: {e}"}


def _strategy_dotnet_sidecar(drawing_path: str, part_path: str, view_names: list[str]) -> dict:
    guard = require_current_job_lock("refdoc_relink_service._strategy_dotnet_sidecar")
    if not guard.get("ok"):
        return _lock_blocked_attempt(guard)
    exe = REPO_ROOT / "tools" / "SwRelink" / "SwRelink.exe"
    if not exe.exists():
        return {"ok": False, "message": f"not_implemented (SwRelink.exe 缺失: {exe})"}
    try:
        import subprocess
        cmd = [str(exe), "--drawing", drawing_path, "--part", part_path, "--views", ",".join(view_names)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return {
            "ok": r.returncode == 0,
            "message": f"SwRelink.exe rc={r.returncode}; stdout={r.stdout[:200]}",
        }
    except Exception as e:
        return {"ok": False, "message": f"dotnet sidecar attempt failed: {e}"}


def _verify_after_relink(drawing_path: str, part_path: str, view_names: list[str]) -> dict:
    """SaveAs/refresh 后检查视图引用是否落到位"""
    guard = require_current_job_lock("refdoc_relink_service._verify_after_relink")
    if not guard.get("ok"):
        return {
            "name_match_count": 0,
            "ref_present_count": 0,
            "bad_ref_count": len(view_names),
            "status": "blocked_by_solidworks_lock",
            "failure_bucket": "solidworks_lock_conflict",
            "lock_conflict": guard,
        }
    name_match = 0
    ref_present = 0
    bad_ref = 0
    expected_name = Path(part_path).name.lower()
    try:
        import win32com.client
        sw = win32com.client.GetActiveObject("SldWorks.Application")
        drw = sw.ActiveDoc
        sheet_view = drw.GetFirstView() if drw else None
        cur = sheet_view.GetNextView() if sheet_view else None
        while cur:
            try: vname = cur.Name
            except Exception: vname = ""
            if vname not in view_names:
                try: cur = cur.GetNextView()
                except Exception: break
                continue
            try:
                rd = cur.ReferencedDocument
                if rd:
                    ref_present += 1
            except Exception: pass
            try:
                ref_path = ""
                try:
                    rd = cur.ReferencedDocument
                    if rd: ref_path = rd.GetPathName() or ""
                except Exception: pass
                if not ref_path:
                    try: ref_path = cur.GetReferencedModelName() or ""
                    except Exception: pass
                if ref_path and Path(ref_path).name.lower() == expected_name:
                    name_match += 1
                else:
                    bad_ref += 1
            except Exception:
                bad_ref += 1
            try: cur = cur.GetNextView()
            except Exception: break
    except Exception:
        bad_ref = len(view_names)
    return {
        "name_match_count": name_match,
        "ref_present_count": ref_present,
        "bad_ref_count": bad_ref,
    }


def relink_refdoc(
    drawing_path: str,
    part_path: str,
    view_names: list[str],
    strategy: str = "auto",
) -> dict:
    """重新绑定工程图视图的模型引用
    
    返回 {ok, strategy_used, attempts, name_match_count, ref_present_count, bad_ref_count, severity}
    """
    if strategy not in VALID_STRATEGIES:
        return {
            "ok": False,
            "strategy_used": strategy,
            "attempts": [{"strategy": strategy, "ok": False, "message": "invalid strategy"}],
            "name_match_count": 0,
            "ref_present_count": 0,
            "bad_ref_count": len(view_names),
            "severity": "warning",
        }
    guard = require_current_job_lock("refdoc_relink_service.relink_refdoc")
    if not guard.get("ok"):
        return _lock_blocked_payload(guard, view_names, strategy)
    
    attempts = []
    strategies_to_try: list[str]
    if strategy == "auto":
        strategies_to_try = ["pywin32_late", "vba_macro", "dotnet_sidecar"]
    else:
        strategies_to_try = [strategy]
    
    final_ok = False
    strategy_used = ""
    for s in strategies_to_try:
        if s == "pywin32_late":
            r = _strategy_pywin32_late(drawing_path, part_path, view_names)
        elif s == "pywin32_ensure_dispatch":
            r = _strategy_ensure_dispatch(drawing_path, part_path, view_names)
        elif s == "vba_macro":
            r = _strategy_vba_macro(drawing_path, part_path, view_names)
        elif s == "dotnet_sidecar":
            r = _strategy_dotnet_sidecar(drawing_path, part_path, view_names)
        else:
            r = {"ok": False, "message": "unknown strategy"}
        attempts.append({"strategy": s, **r})
        if r.get("ok"):
            final_ok = True
            strategy_used = s
            break
    
    if not strategy_used:
        strategy_used = strategies_to_try[-1] if strategies_to_try else strategy
    
    verify = _verify_after_relink(drawing_path, part_path, view_names)
    
    severity = "ok" if final_ok else "warning"
    return {
        "ok": final_ok,
        "strategy_used": strategy_used,
        "attempts": attempts,
        "name_match_count": verify["name_match_count"],
        "ref_present_count": verify["ref_present_count"],
        "bad_ref_count": verify["bad_ref_count"],
        "severity": severity,
    }


if __name__ == "__main__":
    import json
    # 静态自检：不实际跑（需要 SW 在线 + 真实 drawing 才能跑）
    print(f"VALID_STRATEGIES = {VALID_STRATEGIES}")
    # 调用 invalid strategy 测试结构
    r = relink_refdoc("dummy.SLDDRW", "dummy.SLDPRT", ["v1"], strategy="bogus")
    print(json.dumps(r, ensure_ascii=False, indent=2))
