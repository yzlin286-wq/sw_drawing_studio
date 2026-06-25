"""BOM 服务包装层"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

def extract_bom(file_path: str) -> list[dict]:
    from libs.bom import extract
    return extract(file_path)

def write_bom(rows: list[dict], out_base: str):
    from libs.bom import write_csv, write_xlsx
    csv_path = Path(out_base + "_bom.csv")
    xlsx_path = Path(out_base + "_bom.xlsx")
    write_csv(rows, csv_path)
    write_xlsx(rows, xlsx_path)
    return csv_path, xlsx_path
