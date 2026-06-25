"""v2.2 Task 7.1: 运行 024/040 通过 v6 pipeline

增加 timeout 到 600s，通过 SW Session Supervisor 监控
验收: 024/040 至少 1 件恢复可交付
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"c:\Users\Vision\Desktop\SW 相关")
sys.path.insert(0, str(ROOT))

V6_LOOP = ROOT / ".trae/specs/build-v6-and-validate-exe-ui/drw_qc_loop_v6.py"
V5_OUT_DIR = ROOT / "drw_output/v5"

parts = [
    ROOT / "3D转2D测试图纸/LB26001-A-04-024.SLDPRT",
    ROOT / "3D转2D测试图纸/LB26001-A-04-040.SLDPRT",
]

# v2.2 验证输出目录
v22_dir = ROOT / "drw_output/v22_validation"
v22_dir.mkdir(parents=True, exist_ok=True)

results = []
for i, part_path in enumerate(parts, 1):
    base = part_path.stem
    print(f"\n{'='*60}")
    print(f"[{i}/2] Running v6 pipeline: {base}")
    print(f"{'='*60}")

    if not part_path.exists():
        print(f"  SKIP: {part_path} not found")
        results.append({"base": base, "status": "skip", "reason": "part not found"})
        continue

    cmd = [sys.executable, "-X", "utf8", "-u", str(V6_LOOP), str(part_path)]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["QC_LOOP_MAX_ROUNDS"] = "3"
    env["V6_SUBPROC_TIMEOUT"] = "600"

    t0 = time.time()
    try:
        cp = subprocess.run(
            cmd,
            timeout=1800,  # 30 min overall timeout
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            cwd=str(ROOT),
        )
        dt = time.time() - t0
        print(f"  returncode={cp.returncode}  elapsed={dt:.1f}s")

        # 输出最后 30 行 stdout
        if cp.stdout:
            lines = cp.stdout.splitlines()
            tail = "\n".join(lines[-30:])
            print(f"  stdout tail:\n{tail}")

        if cp.returncode != 0 and cp.stderr:
            lines = cp.stderr.splitlines()
            tail = "\n".join(lines[-10:])
            print(f"  stderr tail:\n{tail}")

        # 检查输出文件
        slddrw = V5_OUT_DIR / f"{base}_v5.SLDDRW"
        pdf = V5_OUT_DIR / f"{base}_v5.PDF"
        dxf = V5_OUT_DIR / f"{base}_v5.DXF"
        png = V5_OUT_DIR / f"{base}_v5.PNG"
        qc_json = V5_OUT_DIR / f"{base}_v5_qc.json"

        files_exist = {
            "slddrw": slddrw.exists(),
            "pdf": pdf.exists(),
            "dxf": dxf.exists(),
            "png": png.exists(),
            "qc_json": qc_json.exists(),
        }
        print(f"  files: {files_exist}")

        # 检查 QC pass
        qc_pass = False
        qc_data = {}
        if qc_json.exists():
            try:
                with open(qc_json, "r", encoding="utf-8") as f:
                    qc_data = json.load(f)
                qc_pass = bool(qc_data.get("pass"))
                print(f"  qc_pass={qc_pass} score={qc_data.get('score_pass_count')}/12")
            except Exception as e:
                print(f"  qc_json read error: {e}")

        # 可交付条件: 4 件核心文件齐全
        core_files_ok = all([files_exist["slddrw"], files_exist["pdf"], files_exist["dxf"], files_exist["png"]])
        deliverable = core_files_ok

        results.append({
            "base": base,
            "status": "deliverable" if deliverable else "not_deliverable",
            "returncode": cp.returncode,
            "elapsed_s": round(dt, 1),
            "files": files_exist,
            "core_files_ok": core_files_ok,
            "deliverable": deliverable,
            "qc_pass": qc_pass,
            "qc_score": qc_data.get("score_pass_count"),
        })

    except subprocess.TimeoutExpired:
        dt = time.time() - t0
        print(f"  TIMEOUT after {dt:.1f}s")
        results.append({"base": base, "status": "timeout", "elapsed_s": round(dt, 1)})
    except Exception as e:
        dt = time.time() - t0
        print(f"  ERROR: {e}")
        results.append({"base": base, "status": "error", "reason": str(e), "elapsed_s": round(dt, 1)})

# 汇总
print(f"\n{'='*60}")
print("=== 024/040 验证汇总 ===")
print(f"{'='*60}")
deliverable_count = sum(1 for r in results if r.get("deliverable"))
for r in results:
    print(f"  {r['base']}: {r['status']} deliverable={r.get('deliverable', False)}")
print(f"\n可交付: {deliverable_count}/2")
print(f"验收 (>=1/2): {'PASS' if deliverable_count >= 1 else 'FAIL'}")

# 保存结果
out_file = v22_dir / "024_040_result.json"
with open(out_file, "w", encoding="utf-8") as f:
    json.dump({
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": results,
        "deliverable_count": deliverable_count,
        "pass": deliverable_count >= 1,
    }, f, ensure_ascii=False, indent=2)
print(f"Saved: {out_file}")
