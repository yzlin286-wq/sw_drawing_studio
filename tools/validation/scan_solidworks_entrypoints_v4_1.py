from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.solidworks_entrypoint_scanner import (  # noqa: E402
    DEFAULT_OUT_PATH as OUT_PATH,
    scan_solidworks_entrypoints,
    write_entrypoint_report,
)

OUT_PATH = ROOT / "drw_output" / "diagnostics" / "unguarded_solidworks_entrypoints.json"


def scan(root: Path = ROOT) -> dict:
    return scan_solidworks_entrypoints(root)


def write_report(out_path: Path = OUT_PATH) -> dict:
    return write_entrypoint_report(root=ROOT, out_path=out_path)


def main() -> int:
    report = write_report()
    print(json.dumps({
        "status": report["status"],
        "entrypoint_count": report["entrypoint_count"],
        "unguarded_or_unknown_count": report["unguarded_or_unknown_count"],
        "external_addin_needs_host_lock_count": report["external_addin_needs_host_lock_count"],
        "report_path": report["report_path"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
