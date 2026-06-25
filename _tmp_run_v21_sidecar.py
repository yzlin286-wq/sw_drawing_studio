"""v2.1 批量运行 002/003/007/009 的 sheet sketch dimension"""
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from app.services.sheet_sketch_dimension_service import create_sheet_sketch_dimension
from app.services.sw_addin_client import ping, generate_dimensions_v3
from app.services.blueprint_decision_service import generate_blueprint_decision
from app.services.part_classification_service import classify_part


def close_all_docs():
    try:
        import win32com.client
        sw = win32com.client.Dispatch("SldWorks.Application")
        try:
            sw.Visible = False
        except Exception:
            pass
        try:
            sw.UserControl = False
        except Exception:
            pass
        try:
            docs = sw.GetDocuments
            if docs:
                for doc in docs:
                    try:
                        name = doc.GetTitle
                        sw.CloseDoc(name)
                    except Exception:
                        pass
        except Exception:
            pass
    except Exception:
        pass


def main():
    print("=" * 60)
    print("v2.1 批量运行 002/003/007/009")
    print("=" * 60)

    # 1. Check SW + Add-in
    ping_result = ping()
    print(f"\nPing: {ping_result.get('ping_result')}, method: {ping_result.get('method')}")

    # 2. Find targets
    test_dir = REPO / "3D转2D测试图纸"
    targets = ["002", "003", "007", "009"]
    target_parts = {}
    for t in targets:
        matches = list(test_dir.glob(f"LB26001-A-04-{t}.SLDPRT"))
        if matches:
            target_parts[t] = matches[0]
            print(f"  {t}: {matches[0].name}")

    # 3. Run on each target
    results = {}
    for target_id, part_path in target_parts.items():
        print(f"\n  === {target_id}: {part_path.name} ===")

        # 关闭所有文档
        close_all_docs()
        print(f"    [pre] closed all docs")

        run_id = f"v21_{target_id}_{int(time.time())}"
        run_dir = REPO / "drw_output" / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "qc").mkdir(exist_ok=True)

        drw_path = part_path.with_suffix(".SLDDRW")
        if not drw_path.exists():
            print(f"    SLDDRW not found, skipping")
            continue

        # Classify part
        try:
            cls = classify_part(str(part_path), write_json=True, out_dir=run_dir / "qc")
        except Exception as e:
            print(f"    classify_part failed: {e}")
            cls = None

        # Generate blueprint decision
        try:
            bp = generate_blueprint_decision(run_dir, run_id=run_id)
        except Exception as e:
            print(f"    blueprint_decision failed: {e}")
            bp = None

        # Run Dimension Engine v3 (C# Add-in)
        try:
            policy = {
                "part_class": cls.part_class if cls else "feature_part",
                "dimension_policy": bp.get("dimension_policy", {}).get("policy", "full") if bp else "full",
                "required_dims": bp.get("dimension_policy", {}).get("required_dims", []) if bp else [],
            }
            dim_result = generate_dimensions_v3(
                drawing_path=str(drw_path),
                part_path=str(part_path),
                run_dir=run_dir,
                run_id=run_id,
                policy=policy,
            )
            print(f"    [Add-in] success: {dim_result.get('success')}")
            print(f"    [Add-in] existing_display_dim_count: {dim_result.get('existing_display_dim_count', 0)}")
            print(f"    [Add-in] addin_created_dim_count: {dim_result.get('addin_created_dim_count', 0)}")
        except Exception as e:
            print(f"    [Add-in] failed: {e}")
            dim_result = {"success": False, "addin_created_dim_count": 0, "existing_display_dim_count": 0}

        # 关闭所有文档
        close_all_docs()

        # Run Python sidecar (sheet sketch dimension)
        sidecar_result = {"addin_created_dim_count": 0}
        if dim_result.get("addin_created_dim_count", 0) == 0:
            print(f"    [Sidecar] running sheet sketch dimension...")
            try:
                sidecar_result = create_sheet_sketch_dimension(str(drw_path), run_dir, run_id)
                print(f"    [Sidecar] success: {sidecar_result.get('success')}")
                print(f"    [Sidecar] addin_created_dim_count: {sidecar_result.get('addin_created_dim_count', 0)}")
            except Exception as e:
                print(f"    [Sidecar] failed: {e}")
                sidecar_result = {"success": False, "addin_created_dim_count": 0, "reason": str(e)}

        # 合并结果
        addin_created = dim_result.get("addin_created_dim_count", 0) + sidecar_result.get("addin_created_dim_count", 0)
        existing_display = dim_result.get("existing_display_dim_count", 0)

        results[target_id] = {
            "part_path": str(part_path),
            "drw_path": str(drw_path),
            "run_dir": str(run_dir),
            "run_id": run_id,
            "addin_success": dim_result.get("success", False),
            "sidecar_success": sidecar_result.get("success", False),
            "existing_display_dim_count": existing_display,
            "addin_created_dim_count": addin_created,
            "model_associative_dim_count": dim_result.get("model_associative_dim_count", 0),
            "note_dim_count": dim_result.get("note_dim_count", 0),
            "standard_annotation_count": dim_result.get("standard_annotation_count", 0),
            "reason": dim_result.get("reason", "") + " | " + sidecar_result.get("reason", ""),
        }

        # 关闭所有文档
        close_all_docs()
        print(f"    [post] closed all docs")

    # 4. Summary
    print("\n" + "=" * 60)
    print("=== 002/003/007/009 v2.1 汇总 ===")
    print("=" * 60)
    display_dim_positive = 0
    addin_created_positive = 0
    for tid, r in results.items():
        ddc = r.get("existing_display_dim_count", 0)
        adc = r.get("addin_created_dim_count", 0)
        if ddc > 0:
            display_dim_positive += 1
        if adc > 0:
            addin_created_positive += 1
        print(f"  {tid}: display_dim={ddc}, addin_created={adc}, addin_success={r.get('addin_success')}, sidecar_success={r.get('sidecar_success')}")

    print(f"\n  display_dim_positive: {display_dim_positive}/4")
    print(f"  addin_created_dim_positive: {addin_created_positive}/4")

    # Write results
    out_path = REPO / "drw_output" / "v2_1_002_003_007_009_result.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已写入: {out_path}")

    return results


if __name__ == "__main__":
    main()
