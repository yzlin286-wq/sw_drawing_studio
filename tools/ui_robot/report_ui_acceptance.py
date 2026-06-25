from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# UI Acceptance Report v3.0",
        "",
        f"Generated: {report.get('generated_at', '')}",
        f"Mode: {report.get('mode', '')}",
        f"Overall: {'PASS' if report.get('pass') else 'WARNING'}",
        "",
        "## Screenshots",
        "",
        "| screenshot | size | unique colors | pass |",
        "|---|---:|---:|---|",
    ]
    for item in report.get("screenshots", []):
        lines.append(
            f"| `{Path(item.get('path', '')).name}` | {item.get('size_bytes', 0)} | "
            f"{item.get('sample_unique_colors', 0)} | {'PASS' if item.get('pass') else 'FAIL'} |"
        )
    lines.extend([
        "",
        "## Job Operations",
        "",
    ])
    job_ops = report.get("job_operations", {})
    for key, value in job_ops.items():
        lines.append(f"- {key}: {value}")
    lines.extend([
        "",
        "## Artifacts",
        "",
    ])
    for key, value in report.get("artifacts", {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend([
        "",
        "## Remaining Gates",
        "",
    ])
    for item in report.get("remaining_gates", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def write_markdown(report_json: Path, out_path: Path | None = None) -> Path:
    report = json.loads(Path(report_json).read_text(encoding="utf-8"))
    out = out_path or Path(report_json).with_suffix(".md")
    out.write_text(build_markdown(report), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: report_ui_acceptance.py <ui_acceptance_report.json> [out.md]", file=sys.stderr)
        return 2
    report_json = Path(args[0])
    out = Path(args[1]) if len(args) > 1 else None
    path = write_markdown(report_json, out)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
