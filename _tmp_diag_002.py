"""Quick diagnostic: run v2.1 on a single target and print seed details"""
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from app.services.sw_addin_client import ping, generate_dimensions_v3
from app.services.blueprint_decision_service import generate_blueprint_decision
from app.services.part_classification_service import classify_part


def close_all_docs():
    try:
        import win32com.client
        sw = win32com.client.Dispatch("SldWorks.Application")
        try:
            sw.UserControl = False
        except:
            pass
        try:
            docs = sw.GetDocuments
            if docs:
                for doc in docs:
                    try:
                        name = doc.GetTitle
                        sw.CloseDoc(name)
                    except:
                        pass
        except:
            pass
    except:
        pass


def main():
    # 支持命令行参数指定目标
    target = sys.argv[1] if len(sys.argv) > 1 else "002"

    ping_result = ping()
    print("Ping:", ping_result.get("ping_result"))

    close_all_docs()
    print("[pre] closed all docs")

    test_dir = REPO / "3D转2D测试图纸"
    part_path = test_dir / f"LB26001-A-04-{target}.SLDPRT"
    drw_path = test_dir / f"LB26001-A-04-{target}.SLDDRW"
    run_id = "v21_diag_" + str(int(time.time()))
    run_dir = REPO / "drw_output" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "qc").mkdir(exist_ok=True)

    cls = classify_part(str(part_path), write_json=True, out_dir=run_dir / "qc")
    bp = generate_blueprint_decision(run_dir, run_id=run_id)
    policy = {
        "part_class": cls.part_class,
        "dimension_policy": bp["dimension_policy"]["policy"],
        "required_dims": bp["dimension_policy"]["required_dims"],
    }

    dim_result = generate_dimensions_v3(
        drawing_path=str(drw_path),
        part_path=str(part_path),
        run_dir=run_dir,
        run_id=run_id,
        policy=policy,
    )

    # Print seed details
    import json
    print("\n=== Full strategy_log ===")
    print(json.dumps(dim_result.get("strategy_log", []), ensure_ascii=False, indent=2))

    for entry in dim_result.get("strategy_log", []):
        if isinstance(entry, dict) and entry.get("strategy") == "4_pmi_seed_copied_model":
            seed = entry.get("seed_details", {})
            print("\n=== PMI Seed Details ===")
            print("seed_part_path:", seed.get("seed_part_path"))
            print("seed_dim_count:", seed.get("seed_dim_count"))
            print("seed_dim_count_before_saveas:", seed.get("seed_dim_count_before_saveas"))
            print("saved:", seed.get("saved"))
            print("seed_reopened:", seed.get("seed_reopened"))
            print("saveas3_errors:", seed.get("saveas3_errors"))
            print("saveas3_warnings:", seed.get("saveas3_warnings"))
            print("success:", seed.get("success"))
            print("reason:", seed.get("reason"))
            print("seed_details:", seed.get("seed_details"))
            print("strategy_d_log:", seed.get("strategy_d_log"))
            print("imported_count:", entry.get("count"))
            break

    print("\n=== Summary ===")
    print("addin_created_dim_count:", dim_result.get("addin_created_dim_count"))
    print("existing_display_dim_count:", dim_result.get("existing_display_dim_count"))

    close_all_docs()
    print("[post] closed all docs")


if __name__ == "__main__":
    main()
