"""BOM 抽取器：SLDPRT/SLDASM → list[dict] + CSV + XLSX

CLI: python libs/bom/extract_bom.py <sldprt|sldasm>
输出: <base>_bom.csv, <base>_bom.xlsx
"""
import sys, os, csv, json, argparse
from pathlib import Path

from app.services.solidworks_global_lock import require_current_job_lock

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

BOM_HEADERS = ["序号", "件号", "名称", "规格", "数量", "材质", "重量(g)", "备注"]

def _connect_sw():
    """尝试连 SolidWorks；连不上返回 None"""
    guard = require_current_job_lock("bom.extract_bom._connect_sw")
    if not guard.get("ok"):
        return None
    try:
        import win32com.client
        try:
            return win32com.client.GetActiveObject("SldWorks.Application")
        except Exception:
            return None
    except Exception:
        return None

def _read_props_via_sw(sldprt: Path) -> dict:
    """用 SW COM 读 13 个 CustomProperty；失败返回空 dict"""
    sw = _connect_sw()
    if sw is None: return {}
    try:
        import pythoncom
        from win32com.client import VARIANT
        err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        warn = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        # 1 = swDocPART; options 257 = Silent | DontDisplayReferenceWarnings
        model = sw.OpenDoc6(str(sldprt), 1, 257, "", err, warn)
        if model is None: return {}
        cpm = model.Extension.CustomPropertyManager("")
        keys = ["机型","品名","图号","类别","数量","材质","表面处理","比例","重量","UNIT_OF_MEASURE","设计","日期","重量"]
        out = {}
        for k in keys:
            try:
                val = cpm.Get5(k, False, "", "", False)
                if isinstance(val, tuple):
                    out[k] = val[2] if len(val) >= 3 else ""
                else:
                    out[k] = val or ""
            except Exception:
                out[k] = ""
        try: sw.CloseDoc(model.GetTitle())
        except Exception: pass
        return out
    except Exception:
        return {}

def _read_props_fallback(sldprt: Path) -> dict:
    """SW 不可用时的降级：从文件名推断"""
    base = sldprt.stem
    return {
        "机型": "通用",
        "品名": base,
        "图号": base,
        "类别": "A",
        "数量": "1",
        "材质": "Q235",
        "表面处理": "脱脂磷化喷粉",
        "比例": "1:1",
        "重量": "0",
        "UNIT_OF_MEASURE": "mm",
        "设计": "auto",
        "日期": "",
    }

def extract(file_path: str | Path) -> list[dict]:
    """主抽取函数：单件返回 1 行 BOM；装配体递归（mock）"""
    file_path = Path(file_path).resolve()
    suffix = file_path.suffix.lower()
    
    props = _read_props_via_sw(file_path)
    if not props or not props.get("品名"):
        props = _read_props_fallback(file_path)
    
    rows: list[dict] = []
    
    if suffix == ".sldprt":
        # 单件
        rows.append({
            "序号": 1,
            "件号": props.get("图号") or file_path.stem,
            "名称": props.get("品名") or file_path.stem,
            "规格": props.get("机型") or "",
            "数量": props.get("数量") or 1,
            "材质": props.get("材质") or "",
            "重量(g)": float(props.get("重量") or 0) or 0,
            "备注": props.get("表面处理") or "",
            # 额外字段（不在 8 列里但 Pricing 用）
            "类别": props.get("类别") or "钣金件",
            "weight_g": float(props.get("重量") or 0) or 0,
        })
    elif suffix == ".sldasm":
        # 装配体：mock 一个父件 + 2 个标准件子项（避免真递归 SW）
        rows.append({
            "序号": 1, "件号": file_path.stem, "名称": file_path.stem, "规格": "ASM",
            "数量": 1, "材质": props.get("材质","Q235"), "重量(g)": float(props.get("重量") or 0),
            "备注": "装配体父件", "类别": "装配", "weight_g": float(props.get("重量") or 0),
        })
        # mock 子标准件
        from libs.standard_parts import lookup
        for i, (std, spec) in enumerate([("GB/T 70.1","M5x16"),("GB/T 6170","M5")], start=2):
            sp = lookup(std, spec) or {}
            rows.append({
                "序号": i, "件号": std, "名称": sp.get("name",""), "规格": spec,
                "数量": 4, "材质": sp.get("material",""), "重量(g)": sp.get("weight_g",0),
                "备注": "标准件", "类别": "标准件", "weight_g": sp.get("weight_g",0),
            })
    else:
        raise ValueError(f"unsupported file: {suffix}")
    
    return rows

def write_csv(rows: list[dict], out_path: Path):
    fields = BOM_HEADERS + ["类别", "weight_g", "price_cny_per_kg", "price_cny"]
    out_path.write_text("", encoding="utf-8-sig")
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            r2 = dict(r)
            # 默认材质单价（从 rules.yaml）
            try:
                import yaml
                rules = yaml.safe_load((REPO_ROOT / "libs" / "pricing" / "rules.yaml").read_text(encoding="utf-8"))
                m = r.get("材质")
                if m and not r.get("price_cny_per_kg"):
                    r2["price_cny_per_kg"] = rules.get("material_price_cny_per_kg", {}).get(m, 6.0)
            except Exception: r2["price_cny_per_kg"] = 6.0
            w.writerow(r2)

def write_xlsx(rows: list[dict], out_path: Path):
    try:
        from openpyxl import Workbook
    except Exception as e:
        print(f"[xlsx] openpyxl 缺失，跳过 xlsx: {e}")
        return
    wb = Workbook()
    ws = wb.active
    ws.title = "BOM"
    ws.append(BOM_HEADERS)
    for r in rows:
        ws.append([r.get(h, "") for h in BOM_HEADERS])
    wb.save(out_path)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()
    fp = Path(args.file).resolve()
    if not fp.exists():
        print(f"[ERR] {fp} not found"); return 2
    sys.path.insert(0, str(REPO_ROOT))
    rows = extract(fp)
    out_dir = Path(args.out_dir) if args.out_dir else fp.parent
    base = out_dir / fp.stem
    csv_out = Path(str(base) + "_bom.csv")
    xlsx_out = Path(str(base) + "_bom.xlsx")
    write_csv(rows, csv_out)
    write_xlsx(rows, xlsx_out)
    print(f"[ok] csv={csv_out}\n     xlsx={xlsx_out}\n     rows={len(rows)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
