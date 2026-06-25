"""工艺库查询 + 路线推断"""
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent / "process.db"

DEFAULT_ROUTE_TEMPLATES = {
    "钣金件": [
        ("CUT_LASER", 1.0,  3.0),
        ("BEND",      1.0,  4.0),
        ("TAP",       1.0,  4.0),
        ("POWDER",    1.0,  0.0),
        ("ASSEMBLE",  1.0,  2.0),
    ],
    "机加件": [
        ("CNC_MILL",  1.0,  20.0),
        ("DRILL",     1.0,  6.0),
        ("TAP",       1.0,  4.0),
        ("GRIND",     1.0,  5.0),
        ("PLATE",     1.0,  0.0),
    ],
}

def get_process(code: str) -> dict | None:
    if not DB.exists(): return None
    conn = sqlite3.connect(DB)
    row = conn.execute(
        "SELECT process_code,name,unit,unit_price_cny,hourly_rate,scrap_factor FROM process WHERE process_code=?",
        (code,)).fetchone()
    conn.close()
    if not row: return None
    keys = ["process_code","name","unit","unit_price_cny","hourly_rate","scrap_factor"]
    return dict(zip(keys, row))

def list_all() -> list[dict]:
    if not DB.exists(): return []
    conn = sqlite3.connect(DB)
    rows = conn.execute("SELECT process_code,name,unit,unit_price_cny,hourly_rate,scrap_factor FROM process").fetchall()
    conn.close()
    keys = ["process_code","name","unit","unit_price_cny","hourly_rate","scrap_factor"]
    return [dict(zip(keys, r)) for r in rows]

def suggest_route(part_meta: dict) -> list[dict]:
    """根据零件元数据推断工艺路线
    
    part_meta keys: 类别 (钣金件/机加件/...), weight_g, ...
    """
    cat = part_meta.get("类别") or part_meta.get("category") or "钣金件"
    if cat not in DEFAULT_ROUTE_TEMPLATES:
        cat = "钣金件"
    template = DEFAULT_ROUTE_TEMPLATES[cat]
    weight_g = part_meta.get("weight_g") or part_meta.get("重量") or 100
    
    route = []
    for code, qty, minutes in template:
        proc = get_process(code)
        if not proc: continue
        if proc["unit"] == "kg":
            cny = proc["unit_price_cny"] * (weight_g / 1000.0)
        elif proc["unit"] == "minute":
            cny = proc["unit_price_cny"] * minutes
        elif proc["unit"] == "bend":
            cny = proc["unit_price_cny"] * minutes
        elif proc["unit"] == "hole":
            cny = proc["unit_price_cny"] * minutes
        else:
            cny = proc["unit_price_cny"] * qty
        route.append({
            "process_code": code,
            "name": proc["name"],
            "qty": qty,
            "minutes": minutes,
            "cny": round(cny, 2),
            "scrap_factor": proc["scrap_factor"],
        })
    return route
