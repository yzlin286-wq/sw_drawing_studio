"""标准件库查询接口"""
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "standard_parts.db"

def lookup(std_no: str, spec: str = None) -> dict | None:
    if not DB.exists(): return None
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    if spec:
        row = cur.execute(
            "SELECT std_no,category,name,spec,material,weight_g,price_cny,toolbox_path FROM parts WHERE std_no=? AND spec=?",
            (std_no, spec)).fetchone()
    else:
        row = cur.execute(
            "SELECT std_no,category,name,spec,material,weight_g,price_cny,toolbox_path FROM parts WHERE std_no=? LIMIT 1",
            (std_no,)).fetchone()
    conn.close()
    if not row: return None
    keys = ["std_no","category","name","spec","material","weight_g","price_cny","toolbox_path"]
    return dict(zip(keys, row))

def list_all() -> list[dict]:
    if not DB.exists(): return []
    conn = sqlite3.connect(DB)
    rows = conn.execute("SELECT std_no,category,name,spec,material,weight_g,price_cny,toolbox_path FROM parts").fetchall()
    conn.close()
    keys = ["std_no","category","name","spec","material","weight_g","price_cny","toolbox_path"]
    return [dict(zip(keys, r)) for r in rows]
