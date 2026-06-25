"""核价服务包装层"""
import sys, json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

def suggest_route(part_meta: dict) -> list[dict]:
    from libs.process import suggest_route as _sr
    return _sr(part_meta)

def calculate_quote(bom: list[dict], route: list[dict], profit: float = 0.15, tax: float = 0.13) -> dict:
    from libs.pricing import calculate
    return calculate(bom, route, profit=profit, tax=tax)

def write_quote(result: dict, bom: list[dict], route: list[dict], out_base: str):
    from libs.pricing import write_quote_md
    md = Path(out_base + "_quote.md")
    js = Path(out_base + "_quote.json")
    write_quote_md(result, bom, route, md)
    js.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return js, md
