import os, sys, json, time, subprocess, argparse, datetime
from pathlib import Path

REPO_ROOT = Path(r"c:\Users\Vision\Desktop\SW 相关")
sys.path.insert(0, str(REPO_ROOT))

def check_sw_alive():
    try:
        import win32com.client
        sw = win32com.client.GetActiveObject("SldWorks.Application")
        return sw is not None
    except Exception:
        return False

def run_v5_qc_loop(sldprt: Path, vision_issues_json: Path | None) -> tuple[Path, Path]:
    """调 drw_qc_loop.py 子进程，返回 (slddrw_path, qc_json_path)"""
    env = os.environ.copy()
    if vision_issues_json and vision_issues_json.exists():
        env["VISION_ISSUES_JSON"] = str(vision_issues_json)
    cmd = [sys.executable, "-X", "utf8", "-u",
           r".trae/specs/enforce-drawing-quality/drw_qc_loop.py", str(sldprt)]
    subprocess.run(cmd, cwd=REPO_ROOT, env=env, check=False, timeout=600)
    base = sldprt.stem
    out_dir = REPO_ROOT / "drw_output" / "v5"
    return out_dir / f"{base}_v5.SLDDRW", out_dir / f"{base}_v5_qc.json"

def write_log(log_path: Path, line: str):
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sldprt")
    ap.add_argument("--max-rounds", type=int, default=3)
    ap.add_argument("--threshold", type=int, default=80)
    args = ap.parse_args()

    sldprt = Path(args.sldprt).resolve()
    if not sldprt.exists():
        print(f"[ERR] sldprt not found: {sldprt}", flush=True)
        return 3

    if not check_sw_alive():
        print("[ERR] SolidWorks 进程未运行。请先启动 SolidWorks 2025 后重试。", flush=True)
        return 2

    log_path = REPO_ROOT / ".trae" / "specs" / "harden-v5-and-vision-loop" / "vision_loop_log.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(f"# Vision Loop Log\n\n- 零件: `{sldprt.name}`\n- 开始: {datetime.datetime.now()}\n- 阈值: {args.threshold}\n\n", encoding="utf-8")

    from app.services import build_default_client, vision_score, slddrw_to_png

    llm = build_default_client()
    best_score = -1
    best_slddrw = None
    best_vision_json = None
    final_qc_pass = 0
    issues_json = REPO_ROOT / "drw_output" / "v5" / "vision_issues.json"

    for r in range(1, args.max_rounds + 1):
        write_log(log_path, f"\n## 第 {r} 轮\n")

        # 1) 出图
        slddrw, qc_json = run_v5_qc_loop(sldprt, issues_json if r > 1 else None)
        write_log(log_path, f"- SLDDRW: `{slddrw}`")
        write_log(log_path, f"- qc.json: `{qc_json}`")
        if not slddrw.exists():
            write_log(log_path, "- ❌ SLDDRW 不存在，闭环终止")
            return 3

        # 2) 读 quality_check
        qc_pass = 0
        try:
            qc_data = json.loads(qc_json.read_text(encoding="utf-8"))
            qc_pass = qc_data.get("score_pass_count", 0)
            write_log(log_path, f"- quality_check: {qc_pass}/12")
        except Exception as e:
            write_log(log_path, f"- quality_check 读取失败: {e}")

        # 3) vision_score
        try:
            vresult = vision_score(str(slddrw), str(qc_json), llm)
            score = int(vresult.get("score", 0))
            write_log(log_path, f"- vision_score: **{score}/100**")
            issues_summary = "\n".join(
                f"  - `{i.get('key','?')}`: {i.get('desc','')}"
                for i in vresult.get("issues", [])
            )
            if issues_summary:
                write_log(log_path, f"- issues:\n{issues_summary}")
            write_log(log_path, f"- summary: {vresult.get('summary','')}")
        except Exception as e:
            write_log(log_path, f"- vision_score 调用失败: {e}")
            score = -1
            vresult = None

        if score > best_score:
            best_score = score
            best_slddrw = slddrw
            best_vision_json = REPO_ROOT / "drw_output" / "v5" / f"{sldprt.stem}_v5_vision.json"
            final_qc_pass = qc_pass

        if score >= args.threshold:
            write_log(log_path, f"\n- ✅ 已达阈值 {args.threshold}，闭环成功")
            break

        # 4) 写反馈给下一轮
        if vresult and r < args.max_rounds:
            issues_json.write_text(
                json.dumps(vresult, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            write_log(log_path, f"- 已写 vision_issues.json，准备下一轮")

    # 收尾
    write_log(log_path, f"\n---\n\n## 最终结果\n")
    write_log(log_path, f"- best_score: **{best_score}/100**")
    write_log(log_path, f"- best_slddrw: `{best_slddrw}`")
    write_log(log_path, f"- best_vision_json: `{best_vision_json}`")
    write_log(log_path, f"- quality_check 通过项数: {final_qc_pass}/12")
    write_log(log_path, f"- 状态: **{'PASS' if best_score >= args.threshold else 'FAIL（已达上限）'}**")
    write_log(log_path, f"- 结束时间: {datetime.datetime.now()}")

    if best_score >= args.threshold:
        return 0
    return 1

if __name__ == "__main__":
    sys.exit(main())
