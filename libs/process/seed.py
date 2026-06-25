"""工艺库 seed → SQLite

运行：python libs/process/seed.py
输出：libs/process/process.db
"""
import sys, sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DB = ROOT / "libs" / "process" / "process.db"

PROCESSES = [
    ("CUT_LASER",  "激光切割",   "minute", 1.5,  90,  0.05),
    ("CUT_SHEAR",  "剪板",       "minute", 0.8,  48,  0.03),
    ("BEND",       "数控折弯",   "bend",   1.2,  72,  0.02),
    ("WELD",       "氩弧焊接",   "minute", 2.5,  150, 0.05),
    ("POLISH",     "抛光",       "minute", 0.6,  36,  0.02),
    ("PLATE",      "电镀",       "kg",     12.0, 0,   0.05),
    ("POWDER",     "脱脂磷化喷粉","kg",    8.0,  0,   0.04),
    ("TAP",        "攻丝",       "hole",   0.3,  18,  0.01),
    ("CNC_MILL",   "CNC 铣",     "minute", 2.0,  120, 0.03),
    ("DRILL",      "钻孔",       "hole",   0.5,  30,  0.01),
    ("GRIND",      "磨削",       "minute", 1.8,  108, 0.02),
    ("ASSEMBLE",   "装配",       "minute", 1.0,  60,  0.01),
]

def main():
    DB.parent.mkdir(parents=True, exist_ok=True)
    DB.unlink(missing_ok=True)
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE process(
        process_code TEXT PRIMARY KEY,
        name TEXT, unit TEXT,
        unit_price_cny REAL, hourly_rate REAL, scrap_factor REAL
    )""")
    for r in PROCESSES:
        conn.execute("INSERT INTO process VALUES (?,?,?,?,?,?)", r)
    conn.commit()
    cnt = conn.execute("SELECT COUNT(*) FROM process").fetchone()[0]
    print(f"[ok] inserted {cnt} processes → {DB}")
    conn.close()
    return 0

if __name__ == "__main__":
    sys.exit(main())
