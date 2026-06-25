"""Minimal diagnostic: call generate_dimensions_v3 and print full result"""
import sys
import time
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from app.services.sw_addin_client import ping, generate_dimensions_v3, _get_sw_app, _find_addin
from app.services.blueprint_decision_service import generate_blueprint_decision
from app.services.part_classification_service import classify_part


def close_all_docs():
    try:
        import win32com.client
        sw = win32com.client.Dispatch("SldWorks.Application")
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
    target = sys.argv[1] if len(sys.argv) > 1 else "002"

    ping_result = ping()
    print("Ping:", ping_result.get("ping_result"), "method:", ping_result.get("method"))

    close_all_docs()
    print("[pre] closed all docs")

    test_dir = REPO / "3D转2D测试图纸"
    part_path = test_dir / f"LB26001-A-04-{target}.SLDPRT"
    drw_path = test_dir / f"LB26001-A-04-{target}.SLDDRW"
    run_id = "v21_min_" + str(int(time.time()))
    run_dir = REPO / "drw_output" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "qc").mkdir(exist_ok=True)

    # 检查 Add-in 是否可用
    try:
        sw = _get_sw_app()
        addin, method = _find_addin(sw)
        print(f"Add-in found: {addin is not None}, method: {method}")
        if addin is not None:
            # 检查 GenerateDimensionsV3 方法是否存在
            try:
                ret = getattr(addin, "GenerateDimensionsV3")
                print(f"GenerateDimensionsV3 method: exists")
            except Exception as e:
                print(f"GenerateDimensionsV3 method: NOT FOUND - {e}")
    except Exception as e:
        print(f"Add-in check failed: {e}")

    cls = classify_part(str(part_path), write_json=True, out_dir=run_dir / "qc")
    bp = generate_blueprint_decision(run_dir, run_id=run_id)
    policy = {
        "part_class": cls.part_class,
        "dimension_policy": bp["dimension_policy"]["policy"],
        "required_dims": bp["dimension_policy"]["required_dims"],
    }

    print(f"\nCalling generate_dimensions_v3 for {target}...")
    dim_result = generate_dimensions_v3(
        drawing_path=str(drw_path),
        part_path=str(part_path),
        run_dir=run_dir,
        run_id=run_id,
        policy=policy,
    )

    print("\n=== Full result ===")
    print(json.dumps(dim_result, ensure_ascii=False, indent=2, default=str))

    close_all_docs()
    print("\n[post] closed all docs")


if __name__ == "__main__":
    main()
