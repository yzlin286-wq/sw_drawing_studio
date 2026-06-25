"""Check SolidWorks + Add-in availability and run v2.1 services on 002/003/007/009"""
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))


def close_all_docs(sw_app=None):
    """关闭所有打开的文档，避免 SW 卡住"""
    try:
        if sw_app is None:
            import win32com.client
            sw_app = win32com.client.Dispatch("SldWorks.Application")
        # 设置 SW 为静默模式，禁止弹窗
        try:
            sw_app.UserControl = False
        except:
            pass
        try:
            sw_app.Visible = False
        except:
            pass
        # 获取所有打开的文档
        try:
            docs = sw_app.GetDocuments
            if docs:
                for doc in docs:
                    try:
                        name = doc.GetTitle
                        sw_app.CloseDoc(name)
                    except:
                        pass
        except:
            pass
        # 也尝试通过 GetOpenDocumentCount
        try:
            count = sw_app.GetOpenDocumentCount
            for _ in range(count + 5):
                try:
                    active = sw_app.ActiveDoc
                    if active is None:
                        break
                    name = active.GetTitle
                    sw_app.CloseDoc(name)
                except:
                    break
        except:
            pass
    except:
        pass


def main():
    print("=" * 60)
    print("v2.1 实际运行 002/003/007/009")
    print("=" * 60)

    # 1. Check SolidWorks + Add-in
    print("\n--- 1. Check SolidWorks + Add-in ---")
    try:
        from app.services.sw_addin_client import ping
        ping_result = ping()
        print(f"  SW running: {ping_result.get('sw_running')}")
        print(f"  Add-in loaded: {ping_result.get('addin_loaded')}")
        print(f"  Ping result: {ping_result.get('ping_result')}")
        print(f"  Method: {ping_result.get('method')}")
        print(f"  Reason: {ping_result.get('reason')}")

        if not ping_result.get("ping_result"):
            print("\n  Add-in 不可用，无法运行 v2.1 服务")
            return {"available": False, "reason": ping_result.get("reason")}
    except Exception as e:
        print(f"  FAIL: {e}")
        return {"available": False, "reason": str(e)}

    # 2. Find 002/003/007/009 parts
    print("\n--- 2. Find 002/003/007/009 parts ---")
    test_dir = REPO / "3D转2D测试图纸"
    if not test_dir.exists():
        print(f"  测试目录不存在: {test_dir}")
        return {"available": False, "reason": "test dir not found"}

    targets = ["002", "003", "007", "009"]
    target_parts = {}
    for t in targets:
        # LB26001-A-04-XXX.SLDPRT pattern
        matches = list(test_dir.glob(f"LB26001-A-04-{t}.SLDPRT"))
        if matches:
            target_parts[t] = matches[0]
            print(f"  {t}: {matches[0].name}")
        else:
            # Try broader search
            matches = list(test_dir.rglob(f"*-{t}.SLDPRT"))
            if matches:
                target_parts[t] = matches[0]
                print(f"  {t}: {matches[0].name} (rglob)")
            else:
                print(f"  {t}: NOT FOUND")

    if not target_parts:
        print("  未找到任何目标零件")
        return {"available": False, "reason": "no target parts found"}

    # 3. Run Dimension Engine v3 on each target
    print("\n--- 3. Run Dimension Engine v3 ---")
    from app.services.sw_addin_client import generate_dimensions_v3
    from app.services.blueprint_decision_service import generate_blueprint_decision
    from app.services.part_classification_service import classify_part

    results = {}
    for target_id, part_path in target_parts.items():
        print(f"\n  === {target_id}: {part_path.name} ===")

        # 每个目标前关闭所有文档
        close_all_docs()
        print(f"    [pre] closed all docs")

        run_id = f"v21_{target_id}_{int(time.time())}"
        run_dir = REPO / "drw_output" / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "qc").mkdir(exist_ok=True)
        (run_dir / "input").mkdir(exist_ok=True)
        (run_dir / "drawing").mkdir(exist_ok=True)

        # Find corresponding SLDDRW
        drw_path = part_path.with_suffix(".SLDDRW")
        if not drw_path.exists():
            # Try other patterns
            drw_candidates = list(part_path.parent.glob(f"{part_path.stem}*.SLDDRW"))
            if drw_candidates:
                drw_path = drw_candidates[0]
            else:
                print(f"    SLDDRW not found for {part_path.name}, skipping")
                continue

        # Classify part
        try:
            cls = classify_part(str(part_path), write_json=True, out_dir=run_dir / "qc")
            print(f"    part_class: {cls.part_class} ({cls.reason})")
        except Exception as e:
            print(f"    classify_part failed: {e}")

        # Generate blueprint decision
        try:
            bp = generate_blueprint_decision(run_dir, run_id=run_id)
            print(f"    blueprint: policy={bp['dimension_policy']['policy']}, required={len(bp['dimension_policy']['required_dims'])}")
        except Exception as e:
            print(f"    blueprint_decision failed: {e}")

        # Run Dimension Engine v3
        try:
            policy = {
                "part_class": cls.part_class if cls else "feature_part",
                "dimension_policy": bp.get("dimension_policy", {}).get("policy", "full"),
                "required_dims": bp.get("dimension_policy", {}).get("required_dims", []),
            }
            dim_result = generate_dimensions_v3(
                drawing_path=str(drw_path),
                part_path=str(part_path),
                run_dir=run_dir,
                run_id=run_id,
                policy=policy,
            )
            print(f"    success: {dim_result.get('success')}")
            print(f"    existing_display_dim_count: {dim_result.get('existing_display_dim_count', 0)}")
            print(f"    addin_created_dim_count: {dim_result.get('addin_created_dim_count', 0)}")
            print(f"    model_associative_dim_count: {dim_result.get('model_associative_dim_count', 0)}")
            print(f"    note_dim_count: {dim_result.get('note_dim_count', 0)}")
            print(f"    standard_annotation_count: {dim_result.get('standard_annotation_count', 0)}")
            print(f"    reason: {dim_result.get('reason', '')[:100]}")

            results[target_id] = {
                "part_path": str(part_path),
                "drw_path": str(drw_path),
                "run_dir": str(run_dir),
                "run_id": run_id,
                "success": dim_result.get("success", False),
                "existing_display_dim_count": dim_result.get("existing_display_dim_count", 0),
                "addin_created_dim_count": dim_result.get("addin_created_dim_count", 0),
                "model_associative_dim_count": dim_result.get("model_associative_dim_count", 0),
                "note_dim_count": dim_result.get("note_dim_count", 0),
                "standard_annotation_count": dim_result.get("standard_annotation_count", 0),
                "reason": dim_result.get("reason", ""),
                "strategy_log": dim_result.get("strategy_log", []),
            }
        except Exception as e:
            print(f"    generate_dimensions_v3 failed: {e}")
            results[target_id] = {"error": str(e)}

        # 每个目标后关闭所有文档
        close_all_docs()
        print(f"    [post] closed all docs")

    # 4. Summary
    print("\n" + "=" * 60)
    print("=== 002/003/007/009 v2.1 汇总 ===")
    print("=" * 60)
    display_dim_positive = 0
    addin_created_positive = 0
    for tid, r in results.items():
        if "error" in r:
            print(f"  {tid}: ERROR - {r['error']}")
        else:
            ddc = r.get("existing_display_dim_count", 0)
            adc = r.get("addin_created_dim_count", 0)
            if ddc > 0:
                display_dim_positive += 1
            if adc > 0:
                addin_created_positive += 1
            print(f"  {tid}: display_dim={ddc}, addin_created={adc}, success={r.get('success')}")

    print(f"\n  display_dim_positive: {display_dim_positive}/4")
    print(f"  addin_created_dim_positive: {addin_created_positive}/4")

    # Write results
    out_path = REPO / "drw_output" / "v2_1_002_003_007_009_result.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已写入: {out_path}")

    return results


if __name__ == "__main__":
    main()
