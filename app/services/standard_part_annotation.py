"""v1.7 Task 4: 标准件/弹簧/采购件专用标注策略

对 fastener/spring/purchased_part 不强制 manufacturing 图纸标准。
生成:
  规格
  数量
  标准号/文件编号
  外形参考尺寸
  "按外购件图纸"

QC 允许这些零件达到 C 级采购/装配可用。
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


@dataclass
class StandardAnnotation:
    """标准件标注内容"""
    part_class: str
    spec: str = ""           # 规格，如 M3x8
    std_no: str = ""         # 标准号，如 GB/T 5783
    quantity: int = 1        # 数量
    overall_ref: str = ""    # 外形参考尺寸，如 3×8×5mm
    note: str = "按外购件图纸"
    file_no: str = ""        # 文件编号（可选）

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def standard_annotation_present(self) -> bool:
        """是否有有效的标准标注"""
        return bool(self.spec or self.std_no)


def parse_spec(part_name: str, part_class: str) -> str:
    """从文件名解析规格"""
    # M3x8十字螺丝 -> M3x8
    m = re.search(r"M(\d+)x(\d+)", part_name, re.IGNORECASE)
    if m:
        return f"M{m.group(1)}x{m.group(2)}"
    # M3×8
    m = re.search(r"M(\d+)×(\d+)", part_name, re.IGNORECASE)
    if m:
        return f"M{m.group(1)}x{m.group(2)}"
    if "弹簧" in part_name or part_class == "spring":
        return "弹簧"
    if "铜套" in part_name:
        return "铜套"
    if "导柱" in part_name:
        return "导柱"
    if part_class == "purchased_part":
        return "采购件"
    return ""


def lookup_std_no(part_name: str) -> str:
    """查询标准号"""
    if "螺丝" in part_name or "螺钉" in part_name or "螺栓" in part_name:
        # 十字螺丝 -> GB/T 818（十字槽盘头螺钉）
        if "十字" in part_name:
            return "GB/T 818"
        # 内六角 -> GB/T 70.1
        if "内六角" in part_name:
            return "GB/T 70.1"
        # 六角头 -> GB/T 5783
        return "GB/T 5783"
    if "弹簧" in part_name:
        return "GB/T 2089"
    if "铜套" in part_name:
        return "GB/T 10446"
    if "导柱" in part_name:
        return "GB/T 2861.1"
    if "垫圈" in part_name:
        return "GB/T 97.1"
    if "螺母" in part_name:
        return "GB/T 6170"
    return ""


def build_standard_annotation(
    part_path: str,
    part_class: str,
    bbox_mm: Optional[list] = None,
) -> StandardAnnotation:
    """构建标准件标注

    Args:
        part_path: SLDPRT 路径
        part_class: 零件类别
        bbox_mm: 可选 bbox [length, width, height] mm
    """
    p = Path(part_path)
    name = p.stem

    anno = StandardAnnotation(part_class=part_class)
    anno.spec = parse_spec(name, part_class)
    anno.std_no = lookup_std_no(name)
    anno.quantity = 1
    anno.note = "按外购件图纸"

    if bbox_mm and len(bbox_mm) >= 3:
        anno.overall_ref = f"{bbox_mm[0]:.1f}×{bbox_mm[1]:.1f}×{bbox_mm[2]:.1f}mm"

    return anno


def is_purchased_like(part_class: str) -> bool:
    """是否采购类（fastener/spring/purchased_part）"""
    return part_class in ("fastener", "spring", "purchased_part")


def write_standard_annotation_json(
    anno: StandardAnnotation,
    out_dir: Path,
) -> Path:
    """写 standard_annotation.json"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "standard_annotation.json"
    data = anno.to_dict()
    data["standard_annotation_present"] = anno.standard_annotation_present
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return json_path


def main():
    import sys
    if len(sys.argv) < 3:
        print("Usage: python standard_part_annotation.py <part_path> <part_class>")
        sys.exit(1)
    part_path = sys.argv[1]
    part_class = sys.argv[2]
    anno = build_standard_annotation(part_path, part_class)
    print(json.dumps(anno.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
