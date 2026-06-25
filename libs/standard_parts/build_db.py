"""标准件库 YAML → SQLite 索引

运行：python libs/standard_parts/build_db.py
输出：libs/standard_parts.db
"""
import sys, sqlite3, yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
YAML = ROOT / "libs" / "standard_parts" / "parts.yaml"
DB = ROOT / "libs" / "standard_parts.db"

def main():
    if not YAML.exists():
        print(f"[ERR] {YAML} not found"); return 2
    parts = yaml.safe_load(YAML.read_text(encoding="utf-8"))
    DB.unlink(missing_ok=True)
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE parts(
        std_no TEXT, category TEXT, name TEXT, spec TEXT,
        material TEXT, weight_g REAL, price_cny REAL, toolbox_path TEXT,
        PRIMARY KEY(std_no, spec)
    )""")
    for p in parts:
        cur.execute("INSERT OR REPLACE INTO parts VALUES (?,?,?,?,?,?,?,?)",
            (p.get("std_no"), p.get("category"), p.get("name"), p.get("spec"),
             p.get("material"), p.get("weight_g"), p.get("price_cny"), p.get("toolbox_path")))
    conn.commit()
    cnt = cur.execute("SELECT COUNT(*) FROM parts").fetchone()[0]
    cats = cur.execute("SELECT COUNT(DISTINCT category) FROM parts").fetchone()[0]
    print(f"[ok] inserted {cnt} parts, {cats} categories → {DB}")
    conn.close()
    return 0

if __name__ == "__main__":
    sys.exit(main())
