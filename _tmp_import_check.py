"""Verify all v2.1 modules import correctly"""
import sys
sys.path.insert(0, r"c:\Users\Vision\Desktop\SW 相关")

modules = [
    # v2.1 new modules
    "app.services.pmi_seed_service",
    "app.services.blueprint_decision_service",
    # v2.1 updated modules
    "app.services.health_check",
    "app.services.vision_qc_v3",
    "app.services.docmgr_service",
    "app.services.sw_addin_client",
    "app.services.final_quality",
    "app.ui.drawing_review_workbench",
    # v2.0 modules (verify no regression)
    "app.services.pdf_render_service",
    "app.services.ocr_qc_service",
    "app.services.template_symbol_detector",
    "app.services.yolo_drawing_detector",
    "app.services.llm_visual_reviewer",
]

failed = []
for mod in modules:
    try:
        __import__(mod)
        print(f"OK: {mod}")
    except Exception as e:
        print(f"FAIL: {mod} - {e}")
        failed.append((mod, str(e)))

if failed:
    print(f"\n=== {len(failed)} modules failed to import ===")
    for mod, err in failed:
        print(f"  {mod}: {err}")
    sys.exit(1)
else:
    print(f"\n=== All {len(modules)} v2.1 modules imported successfully ===")
