"""
drw_qc_loop.py — v5 生成 → quality_check → 不合格回传 issues → v5 改参重绘
迭代闭环（最多 max_rounds 轮）。

接口:
    run_qc_loop(part_path: str, max_rounds: int = 3) -> dict

CLI:
    python drw_qc_loop.py [part_path]
    默认 part_path = c:\\Users\\Vision\\Desktop\\SW 相关\\3D转2D测试图纸\\LB26001-A-04-001.SLDPRT
"""
import os
import sys
import json
import time
import subprocess
import traceback
from pathlib import Path

sys.stdout.reconfigure(line_buffering=True)


def log(*a, **kw):
    print(*a, **kw, flush=True)


_SCRIPT_PATH = Path(__file__).resolve()
_BUNDLE_ROOT = Path(os.environ.get("SW_DRAWING_STUDIO_BUNDLE_ROOT", _SCRIPT_PATH.parent.parent.parent.parent)).resolve()
_RUNTIME_ROOT = Path(os.environ.get("SW_DRAWING_STUDIO_RUNTIME_ROOT", _BUNDLE_ROOT)).resolve()
ROOT = str(_RUNTIME_ROOT)
SPEC_DIR = str(_BUNDLE_ROOT / ".trae" / "specs" / "enforce-drawing-quality")
V5_PATH = str(_BUNDLE_ROOT / ".trae" / "specs" / "enforce-drawing-quality" / "drw_generate_v5.py")
V5_OUT_DIR = str(_RUNTIME_ROOT / "drw_output" / "v5")
ISSUES_FILE = os.path.join(V5_OUT_DIR, "issues_to_fix.json")
QC_LOG_MD = os.path.join(SPEC_DIR, "qc_log.md")
DEFAULT_PART = str(_RUNTIME_ROOT / "3D转2D测试图纸" / "LB26001-A-04-001.SLDPRT")
SUBPROC_TIMEOUT = int(os.environ.get("V6_SUBPROC_TIMEOUT", "240"))
SAVE_FLUSH_WAIT = 1.5

sys.path.insert(0, SPEC_DIR)
try:
    import drw_quality_check  # noqa: E402
except Exception as exc:
    log(f"[FATAL] 导入 drw_quality_check 失败: {exc}")
    raise


def _expected_drw_path(part_path):
    base = os.path.splitext(os.path.basename(part_path))[0]
    return os.path.join(V5_OUT_DIR, f"{base}_v5.SLDDRW")


def _safe_issue_codes(qc_result):
    """从 qc 结果提炼 issue code 列表（与 12 项 check key 对齐）。"""
    codes = []
    try:
        order = qc_result.get("_check_order") or []
        checks = qc_result.get("checks") or {}
        for k in order:
            c = checks.get(k) or {}
            if not c.get("pass"):
                codes.append(k)
        if not codes:
            for s in (qc_result.get("issues") or []):
                if not isinstance(s, str):
                    continue
                head = s.split(":", 1)[0].strip()
                if head and head not in codes:
                    codes.append(head)
    except Exception:
        pass
    return codes


def _write_issues_to_fix(codes):
    os.makedirs(V5_OUT_DIR, exist_ok=True)
    payload = {"issues": list(codes)}
    try:
        with open(ISSUES_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return True
    except Exception as exc:
        log(f"[WARN] 写 issues_to_fix.json 失败: {exc}")
        return False


def _run_v5(part_path, issues_path=None):
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "--pipeline-script", "drw_generate_v5", part_path]
    else:
        cmd = [sys.executable, "-X", "utf8", "-u", V5_PATH, part_path]
    if issues_path:
        cmd.append(issues_path)
    log(f"[loop] subprocess: {cmd}")
    t0 = time.time()
    # v1.4 Task 1: 注入 PYTHONPATH 让子进程能 import app.services.*
    sub_env = dict(os.environ)
    sub_env["SW_DRAWING_STUDIO_BUNDLE_ROOT"] = str(_BUNDLE_ROOT)
    sub_env["SW_DRAWING_STUDIO_RUNTIME_ROOT"] = str(_RUNTIME_ROOT)
    sub_env["PYTHONPATH"] = str(_BUNDLE_ROOT) + os.pathsep + sub_env.get("PYTHONPATH", "")
    try:
        cp = subprocess.run(
            cmd,
            timeout=SUBPROC_TIMEOUT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=sub_env,
            cwd=ROOT,
        )
        dt = time.time() - t0
        log(f"[loop] v5 returncode={cp.returncode}  耗时 {dt:.1f}s")
        if cp.stdout:
            tail = "\n".join(cp.stdout.splitlines()[-20:])
            log(f"[loop] v5 stdout(tail):\n{tail}")
        if cp.returncode != 0 and cp.stderr:
            tail_e = "\n".join(cp.stderr.splitlines()[-10:])
            log(f"[loop] v5 stderr(tail):\n{tail_e}")
        return {"ok": cp.returncode == 0, "rc": cp.returncode, "timeout": False}
    except subprocess.TimeoutExpired:
        dt = time.time() - t0
        log(f"[loop] v5 超时 {dt:.1f}s (limit={SUBPROC_TIMEOUT}s)")
        return {"ok": False, "rc": None, "timeout": True}
    except Exception as exc:
        log(f"[loop] v5 调用异常: {exc}")
        log(traceback.format_exc())
        return {"ok": False, "rc": None, "timeout": False, "error": str(exc)}


def _do_quality_check(drw_path):
    if not drw_path or not os.path.exists(drw_path):
        return {
            "file": drw_path,
            "pass": False,
            "score_pass_count": 0,
            "issues": [f"file not found: {drw_path}"],
            "checks": {"__error__": "file not found"},
            "_check_order": [],
        }
    try:
        return drw_quality_check.quality_check(drw_path)
    except Exception as exc:
        log(f"[loop] quality_check 异常: {exc}")
        log(traceback.format_exc())
        return {
            "file": drw_path,
            "pass": False,
            "score_pass_count": 0,
            "issues": [f"quality_check exception: {exc}"],
            "checks": {"__error__": str(exc)},
            "_check_order": [],
        }


def _write_qc_log(part_path, rounds, final_pass, final_path):
    lines = []
    lines.append(f"# QC Loop 日志")
    lines.append("")
    lines.append(f"- 零件: `{part_path}`")
    lines.append(f"- v5 脚本: `{V5_PATH}`")
    lines.append(f"- 输出目录: `{V5_OUT_DIR}`")
    lines.append(f"- 反馈文件: `{ISSUES_FILE}`")
    lines.append(f"- 最大轮数: {len(rounds)}")
    lines.append(f"- 最终结果: **{'PASS' if final_pass else 'FAIL'}**")
    lines.append(f"- 最终图纸: `{final_path}`")
    lines.append("")
    for r in rounds:
        idx = r.get("round_idx")
        gpath = r.get("generated_path") or "(无)"
        psd = r.get("pass")
        pcnt = r.get("pass_count")
        codes = r.get("issues_codes") or []
        sub = r.get("subprocess") or {}
        lines.append(f"## 第 {idx} 轮")
        lines.append("")
        lines.append(f"- 生成文件: `{gpath}`")
        lines.append(f"- subprocess: ok={sub.get('ok')} rc={sub.get('rc')} timeout={sub.get('timeout')}")
        lines.append(f"- quality_check: pass={psd}  pass_count={pcnt}/12")
        if codes:
            lines.append(f"- 失败项 ({len(codes)}):")
            for c in codes:
                lines.append(f"  - `{c}`")
        else:
            lines.append("- 失败项: (无)")
        fed = r.get("feedback_codes")
        if fed is not None:
            if fed:
                lines.append(f"- 写入反馈 issues_to_fix.json: {fed}")
            else:
                lines.append("- 写入反馈 issues_to_fix.json: (空)")
        if r.get("note"):
            lines.append(f"- 备注: {r['note']}")
        lines.append("")
    lines.append(f"## 最终状态")
    lines.append("")
    if final_pass:
        lines.append("- 闭环成功：12 项质检全部通过 (或 score_pass_count ≥ 10)。")
    else:
        last = rounds[-1] if rounds else {}
        last_codes = last.get("issues_codes") or []
        lines.append(f"- 闭环结束但未达标，最终 pass_count={last.get('pass_count')}/12")
        if last_codes:
            lines.append("- 残留失败项:")
            for c in last_codes:
                lines.append(f"  - `{c}`")
    lines.append("")
    try:
        with open(QC_LOG_MD, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        log(f"[loop] qc_log.md 已写: {QC_LOG_MD}")
    except Exception as exc:
        log(f"[WARN] 写 qc_log.md 失败: {exc}")


def run_qc_loop(part_path: str, max_rounds: int = 3) -> dict:
    log(f"[loop] part_path = {part_path}")
    log(f"[loop] max_rounds = {max_rounds}")

    rounds = []
    final_pass = False
    expected_drw = _expected_drw_path(part_path)
    final_path = expected_drw

    issues_path_for_v5 = None

    for i in range(1, max_rounds + 1):
        log(f"\n========== 第 {i}/{max_rounds} 轮 ==========")
        round_rec = {
            "round_idx": i,
            "generated_path": None,
            "pass": False,
            "pass_count": 0,
            "issues_codes": [],
            "subprocess": {},
            "feedback_codes": None,
            "note": "",
        }

        sub_res = _run_v5(part_path, issues_path_for_v5 if i > 1 else None)
        round_rec["subprocess"] = sub_res

        if sub_res.get("timeout"):
            round_rec["note"] = "subprocess timeout, 视为本轮失败但继续"
            round_rec["issues_codes"] = ["__subprocess_timeout__"]
            rounds.append(round_rec)
            try:
                _write_issues_to_fix(round_rec["issues_codes"])
                round_rec["feedback_codes"] = round_rec["issues_codes"]
                issues_path_for_v5 = ISSUES_FILE
            except Exception:
                pass
            continue

        log(f"[loop] 等待 {SAVE_FLUSH_WAIT}s 让 SolidWorks 完成异步刷盘...")
        time.sleep(SAVE_FLUSH_WAIT)

        gpath = expected_drw if os.path.exists(expected_drw) else None
        round_rec["generated_path"] = gpath
        if not gpath:
            round_rec["note"] = f"未找到生成文件 {expected_drw}"
            round_rec["issues_codes"] = ["__file_missing__"]
            rounds.append(round_rec)
            try:
                _write_issues_to_fix(round_rec["issues_codes"])
                round_rec["feedback_codes"] = round_rec["issues_codes"]
                issues_path_for_v5 = ISSUES_FILE
            except Exception:
                pass
            continue

        qc_res = _do_quality_check(gpath)
        psd = bool(qc_res.get("pass"))
        pcnt = int(qc_res.get("score_pass_count") or 0)
        codes = _safe_issue_codes(qc_res)

        # 持久化：让外部 vision_loop 等读取到最新 qc 结果
        try:
            qc_json_path = os.path.splitext(gpath)[0] + "_qc.json"
            with open(qc_json_path, "w", encoding="utf-8") as f:
                json.dump(qc_res, f, ensure_ascii=False, indent=2, default=str)
            log(f"[loop] qc 写盘 -> {qc_json_path}")
        except Exception as exc:
            log(f"[WARN] 写 qc.json 失败: {exc}")

        round_rec["pass"] = psd
        round_rec["pass_count"] = pcnt
        round_rec["issues_codes"] = codes
        rounds.append(round_rec)

        log(f"[loop] 第 {i} 轮 QC: pass={psd}  pass_count={pcnt}/12  issues={codes}")

        if psd or pcnt >= 10:
            final_pass = psd or (pcnt >= 10)
            final_path = gpath
            log(f"[loop] 命中收敛条件 (pass={psd}, pcnt={pcnt}≥10)，终止循环")
            break

        if i < max_rounds:
            ok = _write_issues_to_fix(codes)
            round_rec["feedback_codes"] = codes if ok else None
            issues_path_for_v5 = ISSUES_FILE if ok else None
        else:
            round_rec["note"] = "已达最大轮数"
            final_path = gpath

    if rounds:
        last = rounds[-1]
        if last.get("generated_path"):
            final_path = last["generated_path"]
        if last.get("pass") or (last.get("pass_count") or 0) >= 10:
            final_pass = True

    _write_qc_log(part_path, rounds, final_pass, final_path)

    return {
        "rounds": rounds,
        "final_pass": final_pass,
        "final_path": final_path,
    }


def main():
    part_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PART
    log(f"[main] part_path = {part_path}")
    try:
        res = run_qc_loop(part_path, max_rounds=3)
    except Exception as exc:
        log(f"[FATAL] run_qc_loop 异常: {exc}")
        log(traceback.format_exc())
        return 1

    log("\n========== 汇总 ==========")
    log(f"final_pass = {res['final_pass']}")
    log(f"final_path = {res['final_path']}")
    for r in res["rounds"]:
        log(f"  round {r['round_idx']}: pass={r['pass']} "
            f"pass_count={r['pass_count']}/12 "
            f"issues={r['issues_codes']}")
    log(f"qc_log.md = {QC_LOG_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
