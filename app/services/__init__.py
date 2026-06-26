from app.services.llm_client import LLMClient, build_default_client
from app.services.sw_runner import SwRunner
from app.services.vision_qc import slddrw_to_png, vision_score
from app.services.bom_service import extract_bom, write_bom
from app.services.pricing_service import suggest_route, calculate_quote, write_quote
from app.services.run_manager import RunContext, new_run, list_recent_runs
from app.services.diagnostics import build_diagnostics_zip, list_diagnostics
from app.services.refdoc_relink_service import relink_refdoc
from app.services.case_library import (
    build_case_library,
    find_case_png,
    list_case_library,
    CASE_DIR,
    LIB_DIR,
)
from app.services.batch_validator import (
    run_batch_validation,
    write_batch_report,
    BATCH_DIR,
)
from app.services.scale_advisor import (
    advise_scale,
    is_gb_standard_scale,
    GB_STANDARD_SCALES,
)

__all__ = [
    "LLMClient",
    "build_default_client",
    "SwRunner",
    "slddrw_to_png",
    "vision_score",
    "extract_bom",
    "write_bom",
    "suggest_route",
    "calculate_quote",
    "write_quote",
    "RunContext",
    "new_run",
    "list_recent_runs",
    "build_diagnostics_zip",
    "list_diagnostics",
    "relink_refdoc",
    "build_case_library",
    "find_case_png",
    "list_case_library",
    "CASE_DIR",
    "LIB_DIR",
    "run_batch_validation",
    "write_batch_report",
    "BATCH_DIR",
    "advise_scale",
    "is_gb_standard_scale",
    "GB_STANDARD_SCALES",
]

from app.services.model_compare import (
    compare_model_2d,
    MODEL_PNG_DIR,
)
