"""v2.1 单目标运行 - 在独立进程中运行 Add-in + sidecar

每个目标运行流程:
  1. Add-in generate_dimensions_v3 (v3.2 SaveAs3 PMI Seed)
  2. 杀掉 SW
  3. Sidecar sheet_sketch_dimension (AddDimension2)
  4. 保存结果到 drw_output/v2_1_{target}_result.json
"""
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from app.services.sw_addin_client import generate_dimensions_v3
from app.services.sheet_sketch_dimension_service import create_sheet_sketch_dimension
from app.services.blueprint_decision_service import generate_blueprint_decision
from app.services.part_classification_service import classify_part


def kill_sw():
    """杀掉所有 SW 进程"""
    for proc_name in ["SLDWORKS.exe", "SLDEXITAPP.exe"]:
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", proc_name, "/T"],
                capture_output=True, timeout=30,
            )
        except Exception:
            pass
    time.sleep(5)


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "002"

    test_dir = REPO / "3D转2D测试图纸"
    part_path = test_dir / f"LB26001-A-04-{target}.SLDPRT"
    drw_path = test_dir / f"LB26001-A-04-{target}.SLDDRW"

    run_id = f"v21iso_{target}_{int(time.time())}"
    run_dir = REPO / "drw_output" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "qc").mkdir(exist_ok=True)

    print(f"Target: {target}")
    print(f"Part: {part_path.name}")
    print(f"Drawing: {drw_path.name}")
    print(f"RunID: {run_id}")

    # 1. Classify part
    try:
        cls = classify_part(str(part_path), write_json=True, out_dir=run_dir / "qc")
        part_class = cls.part_class
    except Exception as e:
        print(f"classify_part failed: {e}")
        part_class = "feature_part"

    # 2. Blueprint decision
    try:
        bp = generate_blueprint_decision(run_dir, run_id=run_id)
        dim_policy = bp.get("dimension_policy", {}).get("policy", "full")
        required_dims = bp.get("dimension_policy", {}).get("required_dims", [])
    except Exception as e:
        print(f"blueprint_decision failed: {e}")
        dim_policy = "full"
        required_dims = []

    policy = {
        "part_class": part_class,
        "dimension_policy": dim_policy,
        "required_dims": required_dims,
    }

    # 3. Add-in generate_dimensions_v3
    print("\n--- Add-in generate_dimensions_v3 ---")
    try:
        dim_result = generate_dimensions_v3(
            drawing_path=str(drw_path),
            part_path=str(part_path),
            run_dir=run_dir,
            run_id=run_id,
            policy=policy,
        )
        addin_created = dim_result.get("addin_created_dim_count", 0)
        existing_display = dim_result.get("existing_display_dim_count", 0)
        print(f"Add-in: success={dim_result.get('success')}, addin_created={addin_created}, existing_display={existing_display}")
        # Print strategy summary
        for entry in dim_result.get("strategy_log", []):
            if isinstance(entry, dict):
                sname = entry.get("strategy", entry.get("action", ""))
                scount = entry.get("count", "")
                ssuccess = entry.get("success", "")
                sreason = entry.get("reason", "")[:80]
                print(f"  {sname}: count={scount}, success={ssuccess}, reason={sreason}")
    except Exception as e:
        print(f"Add-in failed: {e}")
        dim_result = {
            "success": False, "addin_created_dim_count": 0,
            "existing_display_dim_count": 0, "reason": str(e),
            "strategy_log": [],
        }
        addin_created = 0
        existing_display = 0

    # 4. 杀掉 SW (Add-in 后、Sidecar 前)
    print("\n--- Killing SW before sidecar ---")
    kill_sw()

    # 5. Sidecar (if Add-in didn't create dims)
    sidecar_result = {"addin_created_dim_count": 0, "success": False, "reason": "skipped"}
    if addin_created == 0:
        print("\n--- Sidecar sheet_sketch_dimension ---")
        try:
            sidecar_result = create_sheet_sketch_dimension(str(drw_path), run_dir, run_id)
            print(f"Sidecar: success={sidecar_result.get('success')}, addin_created={sidecar_result.get('addin_created_dim_count', 0)}")
            if sidecar_result.get("reason"):
                print(f"Sidecar reason: {sidecar_result.get('reason')[:120]}")
        except Exception as e:
            print(f"Sidecar failed: {e}")
            sidecar_result = {"success": False, "addin_created_dim_count": 0, "reason": str(e)}
    else:
        print(f"\n--- Sidecar skipped (Add-in already created {addin_created} dims) ---")

    # 6. 合并结果
    total_addin_created = addin_created + sidecar_result.get("addin_created_dim_count", 0)

    result = {
        "target": target,
        "part_path": str(part_path),
        "drw_path": str(drw_path),
        "run_dir": str(run_dir),
        "run_id": run_id,
        "addin_success": dim_result.get("success", False),
        "sidecar_success": sidecar_result.get("success", False),
        "existing_display_dim_count": existing_display,
        "addin_created_dim_count": total_addin_created,
        "addin_only_dim_count": addin_created,
        "sidecar_only_dim_count": sidecar_result.get("addin_created_dim_count", 0),
        "model_associative_dim_count": dim_result.get("model_associative_dim_count", 0),
        "note_dim_count": dim_result.get("note_dim_count", 0),
        "standard_annotation_count": dim_result.get("standard_annotation_count", 0),
        "addin_reason": dim_result.get("reason", ""),
        "sidecar_reason": sidecar_result.get("reason", ""),
        "strategy_log": dim_result.get("strategy_log", []),
        "engine_version": dim_result.get("engine_version", ""),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    # 7. 保存单目标结果
    out_path = REPO / "drw_output" / f"v2_1_{target}_result.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResult saved: {out_path}")
    print(f"  addin_created_dim_count: {total_addin_created}")
    print(f"  existing_display_dim_count: {existing_display}")

    # 8. 最后再杀一次 SW
    kill_sw()


if __name__ == "__main__":
    main()
