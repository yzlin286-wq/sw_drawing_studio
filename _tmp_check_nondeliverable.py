"""检查不可交付的 LB26001 runs 的失败原因"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent
runs_dir = REPO / "drw_output" / "runs"
runs = sorted(runs_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)

# 检查几个不可交付的零件
targets = ["LB26001-A-04-015", "LB26001-A-04-021", "LB26001-A-04-031", "LB26001-A-04-050"]

for target in targets:
    for r in runs:
        m_path = r / "manifest.json"
        if m_path.exists():
            try:
                m = json.loads(m_path.read_text(encoding="utf-8"))
                input_part = m.get("input_part_path_abs", "")
                base = Path(input_part).stem if input_part else ""
                if base == target:
                    print(f"=== {target} (run: {r.name}) ===")
                    du = m.get("drawing_usable", {})
                    print(f"  drawing_usable.pass: {du.get('pass', '')}")
                    print(f"  drawing_usable.criteria: {du.get('criteria', '')}")
                    print(f"  hard_fail: {m.get('hard_fail', '')}")
                    print(f"  warnings: {m.get('warnings', '')}")
                    print(f"  dimension_grade: {m.get('dimension_grade', '')}")
                    print(f"  part_class: {m.get('part_class', '')}")
                    print(f"  strategy: {m.get('strategy', '')}")
                    print(f"  app_version: {m.get('app_version', '')}")
                    print(f"  exception_summary: {m.get('exception_summary', '')}")
                    print(f"  dim_total: {m.get('dim_total', '')}")
                    print()
                    break
            except Exception as e:
                print(f"Error reading {r.name}: {e}")
                break
