"""核价引擎

CLI: python libs/pricing/quote.py <bom_csv> [--profit 0.15] [--tax 0.13]
返回 dict 含 total_cny + breakdown
"""
import sys, os, csv, json, argparse, datetime, yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RULES = Path(__file__).resolve().parent / "rules.yaml"

def _load_rules() -> dict:
    if not RULES.exists():
        return {"profit": 0.15, "tax": 0.13, "packing_factor": 0.02, "moq": 10, "moq_factor": 1.2}
    return yaml.safe_load(RULES.read_text(encoding="utf-8")) or {}

def calculate(bom: list[dict], route: list[dict], profit: float = None, tax: float = None) -> dict:
    """核价
    
    bom: list of {name, qty, weight_g, material, price_cny_per_kg}
    route: list of {process_code, name, qty, minutes, cny, scrap_factor}
    """
    rules = _load_rules()
    profit = profit if profit is not None else rules.get("profit", 0.15)
    tax = tax if tax is not None else rules.get("tax", 0.13)
    packing_factor = rules.get("packing_factor", 0.02)
    moq = rules.get("moq", 10)
    moq_factor = rules.get("moq_factor", 1.2)
    
    # 1. 材料费
    material_cny = 0.0
    for row in bom:
        weight_kg = float(row.get("weight_g", 0) or 0) / 1000.0
        ppk = float(row.get("price_cny_per_kg", 0) or 0)
        qty = float(row.get("qty", 1) or 1)
        # 标准件用价格直接 = price_cny × qty
        if row.get("price_cny"):
            material_cny += float(row["price_cny"]) * qty
        else:
            material_cny += weight_kg * ppk * qty * (1 + 0.05)  # +5% 损耗
    
    # 2. 加工费
    process_cny = 0.0
    surface_cny = 0.0
    for r in route:
        c = float(r.get("cny", 0) or 0)
        if r.get("process_code") in ("PLATE", "POWDER"):
            surface_cny += c
        else:
            process_cny += c
    
    # 3. 包装费
    packing_cny = (material_cny + process_cny + surface_cny) * packing_factor
    
    # 4. 小计
    subtotal = material_cny + process_cny + surface_cny + packing_cny
    
    # 5. 起订量加价
    total_qty = sum(float(r.get("qty", 1) or 1) for r in bom) or 1
    if total_qty < moq:
        subtotal *= moq_factor
    
    # 6. 利润 + 税
    after_profit = subtotal * (1 + profit)
    total = after_profit * (1 + tax)
    
    return {
        "total_cny": round(total, 2),
        "breakdown": {
            "material_cny": round(material_cny, 2),
            "process_cny": round(process_cny, 2),
            "surface_cny": round(surface_cny, 2),
            "packing_cny": round(packing_cny, 2),
            "subtotal_cny": round(subtotal, 2),
            "profit_rate": profit,
            "tax_rate": tax,
            "moq_applied": total_qty < moq,
        },
        "input": {"bom_count": len(bom), "route_count": len(route)},
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }

def write_quote_md(result: dict, bom: list[dict], route: list[dict], out: Path):
    lines = [
        "# 核价单",
        "",
        f"- 生成时间: {result['generated_at']}",
        f"- BOM 行数: {result['input']['bom_count']}",
        f"- 工艺路线: {result['input']['route_count']} 道",
        "",
        "## BOM",
        "",
        "| 名称 | 规格 | 数量 | 材质 | 重量(g) | 单价(元) |",
        "|---|---|---|---|---|---|",
    ]
    for r in bom:
        lines.append(f"| {r.get('name','')} | {r.get('spec','')} | {r.get('qty',1)} | {r.get('material','')} | {r.get('weight_g',0)} | {r.get('price_cny','-')} |")
    lines += [
        "",
        "## 工艺路线",
        "",
        "| 工序 | 数量 | 工时(min) | 金额(元) |",
        "|---|---|---|---|",
    ]
    for r in route:
        lines.append(f"| {r.get('name','')} | {r.get('qty',1)} | {r.get('minutes',0)} | {r.get('cny',0)} |")
    lines += [
        "",
        "## 报价明细",
        "",
        f"- 材料费: ¥{result['breakdown']['material_cny']}",
        f"- 加工费: ¥{result['breakdown']['process_cny']}",
        f"- 表面处理: ¥{result['breakdown']['surface_cny']}",
        f"- 包装费: ¥{result['breakdown']['packing_cny']}",
        f"- 小计: ¥{result['breakdown']['subtotal_cny']}",
        f"- 利润率: {result['breakdown']['profit_rate']*100:.1f}%",
        f"- 税率: {result['breakdown']['tax_rate']*100:.1f}%",
        "",
        f"## 总价 = ¥{result['total_cny']}",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bom_csv")
    ap.add_argument("--profit", type=float, default=None)
    ap.add_argument("--tax", type=float, default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    
    bom_path = Path(args.bom_csv).resolve()
    if not bom_path.exists():
        print(f"[ERR] {bom_path} not found"); return 2
    
    # 读 BOM
    bom = []
    with open(bom_path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            bom.append(r)
    
    # 推断工艺路线
    sys.path.insert(0, str(ROOT))
    try:
        from libs.process import suggest_route
    except Exception:
        suggest_route = None
    
    if suggest_route:
        first = bom[0] if bom else {}
        meta = {"类别": first.get("类别") or first.get("category") or "钣金件",
                "weight_g": float(first.get("weight_g") or 100)}
        route = suggest_route(meta)
    else:
        route = []
    
    result = calculate(bom, route, profit=args.profit, tax=args.tax)
    
    out_base = Path(args.out) if args.out else bom_path.with_suffix("")
    json_out = Path(str(out_base) + "_quote.json")
    md_out = Path(str(out_base) + "_quote.md")
    
    json_out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    write_quote_md(result, bom, route, md_out)
    
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n[ok] json={json_out}\n     md={md_out}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
