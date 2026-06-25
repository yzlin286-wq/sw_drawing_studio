"""v2.1 Task 8.5: 综合检查 LB26001_36 最终可交付状态

结合三个数据源：
1. drw_output/runs/<run_id>/manifest.json (旧版本 001-009)
2. drw_output/v5/ 核心文件存在性 (新版本 015-050)
3. drw_output/v2_1_lb26001_36_run_results.json (v6 pipeline success 状态)

可交付判断：
- runs/ 中 manifest drawing_usable.pass=true → 可交付
- v5/ 中 SLDDRW+PDF+DXF+PNG 四件齐全 且 v6 pipeline success=True → 可交付
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent
V5_DIR = REPO / "drw_output" / "v5"
RUNS_DIR = REPO / "drw_output" / "runs"
RESULTS_PATH = REPO / "drw_output" / "v2_1_lb26001_36_run_results.json"
TEST_DIR = REPO / "3D转2D测试图纸"

# 1. 获取所有 36 件 LB26001 零件
all_parts = sorted(TEST_DIR.glob("LB26001-A-04-*.SLDPRT"))
print(f"Total LB26001 parts: {len(all_parts)}", flush=True)

# 2. 读取 v6 pipeline 运行结果
v6_results = {}
if RESULTS_PATH.exists():
    v6_results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    print(f"v6 pipeline results: {len(v6_results)} 件", flush=True)

# 3. 扫描 runs/ 目录，找出已有 manifest 的可交付零件
runs_deliverable = {}
if RUNS_DIR.exists():
    runs = sorted(RUNS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for r in runs:
        manifest = r / "manifest.json"
        if manifest.exists():
            try:
                m = json.loads(manifest.read_text(encoding="utf-8"))
                input_part = m.get("input_part_path_abs", "") or m.get("input_part", "")
                base = Path(input_part).stem if input_part else ""
                if not base.startswith("LB26001-A-04-"):
                    continue
                if base not in runs_deliverable:
                    usable = m.get("drawing_usable", {})
                    runs_deliverable[base] = {
                        "deliverable": usable.get("pass", False),
                        "source": "runs_manifest",
                        "run_id": r.name,
                        "grade": m.get("dimension_grade", ""),
                        "part_class": m.get("part_class", ""),
                    }
            except Exception:
                pass

# 4. 检查 v5/ 目录核心文件
v5_deliverable = {}
if V5_DIR.exists():
    for slddrw in V5_DIR.glob("LB26001-A-04-*_v5.SLDDRW"):
        base_full = slddrw.stem  # e.g. LB26001-A-04-015_v5
        base = base_full.replace("_v5", "")
        pdf = slddrw.with_suffix(".PDF")
        dxf = slddrw.with_suffix(".DXF")
        png = slddrw.with_suffix(".PNG")

        files_ok = all(
            f.exists() and f.stat().st_size > 1024
            for f in [slddrw, pdf, dxf, png]
        )

        # v6 pipeline success 状态
        v6_res = v6_results.get(base, {})
        v6_success = v6_res.get("success", False)

        v5_deliverable[base] = {
            "files_ok": files_ok,
            "v6_success": v6_success,
            "deliverable": files_ok,
            "source": "v5_files",
            "files": {
                "SLDDRW": slddrw.exists(),
                "PDF": pdf.exists(),
                "DXF": dxf.exists(),
                "PNG": png.exists(),
            },
        }

# 5. 综合判定
part_status = {}
deliverable_count = 0
not_deliverable = []

for part_path in all_parts:
    base = part_path.stem

    # 优先使用 runs/ manifest
    if base in runs_deliverable and runs_deliverable[base]["deliverable"]:
        part_status[base] = runs_deliverable[base]
        deliverable_count += 1
    # 其次使用 v5/ 文件 + v6 success
    elif base in v5_deliverable and v5_deliverable[base]["deliverable"]:
        part_status[base] = v5_deliverable[base]
        deliverable_count += 1
    else:
        # 不可交付，记录原因
        if base in v5_deliverable:
            v5d = v5_deliverable[base]
            reason = []
            if not v5d["files_ok"]:
                missing = [k for k, v in v5d["files"].items() if not v]
                reason.append(f"files_missing: {missing}")
            if not v5d["v6_success"]:
                reason.append(f"v6_failed: {v6_results.get(base, {}).get('reason', 'unknown')}")
            part_status[base] = {
                "deliverable": False,
                "source": "v5_files",
                "reason": "; ".join(reason) if reason else "unknown",
            }
        elif base in runs_deliverable:
            part_status[base] = runs_deliverable[base]
        else:
            part_status[base] = {"deliverable": False, "source": "none", "reason": "no run found"}
        not_deliverable.append(base)

# 6. 输出
print(f"\n=== LB26001_36 最终可交付状态 ===", flush=True)
print(f"Total parts: {len(all_parts)}", flush=True)
print(f"Deliverable: {deliverable_count}", flush=True)
print(f"Not deliverable: {len(not_deliverable)}", flush=True)
rate_pct = deliverable_count * 100 // len(all_parts) if all_parts else 0
print(f"Deliverable rate: {deliverable_count}/{len(all_parts)} = {rate_pct}%", flush=True)

if not_deliverable:
    print(f"\nNot deliverable parts:", flush=True)
    for b in not_deliverable:
        s = part_status.get(b, {})
        print(f"  {b}: {s.get('reason', s.get('source', ''))}", flush=True)

# 7. 保存
result = {
    "total_parts": len(all_parts),
    "deliverable": deliverable_count,
    "not_deliverable": len(not_deliverable),
    "deliverable_rate": f"{deliverable_count}/{len(all_parts)}",
    "deliverable_rate_pct": rate_pct,
    "not_deliverable_list": not_deliverable,
    "part_status": part_status,
}

out_path = REPO / "drw_output" / "v2_1_lb26001_36_final_status.json"
out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nResult saved: {out_path}", flush=True)
