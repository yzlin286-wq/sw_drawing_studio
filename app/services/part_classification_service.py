"""v1.7 Task 2: 零件分类器

基于文件名、bbox、历史 dim_total、是否标准件来判断零件类别。

分类:
  feature_part      - 有特征的加工件（默认）
  imported_body     - 导入几何体（无特征）
  long_thin         - 长细件（长宽比 > 5）
  tiny_part         - 微小件（bbox < 30mm）
  fastener          - 标准紧固件（螺丝/螺栓/螺母/垫圈）
  spring            - 弹簧
  purchased_part    - 采购件（铜套/导柱等）
  sheet_like        - 钣金/板状件（厚度 < 5mm 且面积大）

输出 part_class.json
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from app.services.solidworks_global_lock import require_current_job_lock


# 文件名关键词 -> 类别（按优先级，先匹配先返回）
_FILENAME_RULES = [
    # fastener
    (r"螺丝|螺钉|螺栓|螺母|垫圈|bolt|screw|nut|washer|M\d+x\d+|M\d+×\d+", "fastener"),
    # spring
    (r"弹簧|spring|压簧|拉簧|扭簧", "spring"),
    # purchased_part
    (r"铜套|导柱|导套|轴承|bearing|LMK|LMF|直线轴承", "purchased_part"),
    # AC 系列（采购件）
    (r"AC-\d+", "purchased_part"),
]


@dataclass
class PartClassification:
    part_path: str
    part_name: str
    part_class: str  # feature_part / imported_body / long_thin / tiny_part / fastener / spring / purchased_part / sheet_like
    reason: str = ""
    bbox_mm: Optional[list] = None  # [length, width, height] in mm
    is_standard: bool = False
    std_no: str = ""
    std_spec: str = ""
    long_thin_ratio: Optional[float] = None
    is_tiny: bool = False
    is_sheet_like: bool = False
    has_features: Optional[bool] = None
    history_dim_total: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    def is_purchased_like(self) -> bool:
        """是否采购类（fastener/spring/purchased_part）"""
        return self.part_class in ("fastener", "spring", "purchased_part")


def _match_filename_rules(name: str) -> Optional[tuple[str, str]]:
    """返回 (类别, 匹配到的关键词) 或 None"""
    for pattern, cls in _FILENAME_RULES:
        m = re.search(pattern, name, re.IGNORECASE)
        if m:
            return cls, m.group(0)
    return None


def _lookup_standard_part(name: str) -> tuple[bool, str, str]:
    """查询标准件库，返回 (is_standard, std_no, std_spec)"""
    try:
        repo_root = Path(__file__).resolve().parent.parent.parent
        yaml_path = repo_root / "libs" / "standard_parts" / "parts.yaml"
        if not yaml_path.exists():
            return False, "", ""
        # 简单文本匹配（避免引入 yaml 依赖问题）
        text = yaml_path.read_text(encoding="utf-8")
        # 提取所有 spec 行
        specs = re.findall(r"spec:\s*(\S+)", text)
        std_nos = re.findall(r"std_no:\s*(\S+)", text)
        # 检查文件名是否包含某个 spec
        # v1.7 fix: 只匹配含字母的 spec（如 M3x8），跳过纯数字 spec（如 6001 轴承型号）
        #   原因：纯数字 spec 会误匹配零件编号（如 LB26001 中的 6001）
        name_norm = name.lower().replace("×", "x")
        for i, spec in enumerate(specs):
            spec_norm = spec.lower().replace("×", "x")
            if not spec_norm:
                continue
            # 跳过纯数字 spec（轴承型号等），避免误匹配零件编号
            if spec_norm.isdigit():
                continue
            # spec 必须包含字母（M3x8, LMK12 等）
            if not re.search(r"[a-zA-Z]", spec_norm):
                continue
            # 用词边界匹配，避免部分匹配
            if re.search(r"\b" + re.escape(spec_norm) + r"\b", name_norm):
                # 找对应的 std_no（同一记录块）
                std_no = std_nos[i] if i < len(std_nos) else ""
                return True, std_no, spec
        # 检查 M3x8 等模式
        m = re.search(r"M(\d+)x(\d+)", name, re.IGNORECASE)
        if m:
            spec = f"M{m.group(1)}x{m.group(2)}"
            return True, "GB/T 5783 或 GB/T 70.1", spec
    except Exception:
        pass
    return False, "", ""


def _get_bbox_mm(part_path: str) -> Optional[list]:
    """通过 SolidWorks GetPartBox 获取 bbox（mm）"""
    guard = require_current_job_lock("part_classification_service._get_bbox_mm")
    if not guard.get("ok"):
        return None
    try:
        import win32com.client
        import pythoncom
        sw = win32com.client.GetActiveObject("SldWorks.Application")
        if sw is None:
            return None
        # 尝试激活已打开的文档
        part = None
        try:
            part = sw.ActiveDoc
        except Exception:
            pass
        if part is None:
            return None
        # GetPartBox(True) 返回 [xmin, ymin, zmin, xmax, ymax, zmax]（米）
        try:
            box = part.GetPartBox(True)
            if box and len(box) >= 6:
                # 米 -> 毫米
                dx = abs(box[3] - box[0]) * 1000.0
                dy = abs(box[4] - box[1]) * 1000.0
                dz = abs(box[5] - box[2]) * 1000.0
                # 排序：length >= width >= height
                dims = sorted([dx, dy, dz], reverse=True)
                return dims
        except Exception:
            return None
    except Exception:
        return None
    return None


def _check_has_features(part_path: str) -> Optional[bool]:
    """检查是否有特征（FeatureManager.GetFeatureCount）"""
    guard = require_current_job_lock("part_classification_service._check_has_features")
    if not guard.get("ok"):
        return None
    try:
        import win32com.client
        sw = win32com.client.GetActiveObject("SldWorks.Application")
        part = sw.ActiveDoc
        if part is None:
            return None
        # GetFeatureCount 返回顶层特征数
        # imported_body 通常特征数很少（< 3）
        try:
            fm = part.FeatureManager
            if fm is None:
                return None
            count = fm.GetFeatureCount()
            return count >= 3
        except Exception:
            return None
    except Exception:
        return None


def classify_part(
    part_path: str,
    bbox_mm: Optional[list] = None,
    history_dim_total: int = 0,
    write_json: bool = True,
    out_dir: Optional[Path] = None,
) -> PartClassification:
    """分类零件

    Args:
        part_path: SLDPRT 绝对路径
        bbox_mm: 可选的 bbox [length, width, height] mm，None 则尝试从 SW 获取
        history_dim_total: 历史 dim_total（用于辅助判断 imported_body）
        write_json: 是否写 part_class.json
        out_dir: 输出目录（默认 part_path 同目录）
    """
    p = Path(part_path)
    name = p.name
    cls = PartClassification(
        part_path=str(p.resolve()),
        part_name=name,
        part_class="feature_part",  # 默认
        reason="default",
        history_dim_total=history_dim_total,
    )

    # 1) 文件名规则匹配（最高优先级）
    fn_match = _match_filename_rules(name)
    if fn_match:
        cls.part_class = fn_match[0]
        cls.reason = f"filename match: {fn_match[1]}"

    # 2) 标准件库查询
    is_std, std_no, std_spec = _lookup_standard_part(name)
    cls.is_standard = is_std
    cls.std_no = std_no
    cls.std_spec = std_spec
    if is_std and cls.part_class == "feature_part":
        # 文件名未匹配但标准件库匹配，归为 fastener
        cls.part_class = "fastener"
        cls.reason = f"standard part: {std_no} {std_spec}"

    # 3) bbox 分析
    if bbox_mm is None:
        bbox_mm = _get_bbox_mm(part_path)
    if bbox_mm and len(bbox_mm) >= 3:
        cls.bbox_mm = bbox_mm
        length, width, height = bbox_mm[0], bbox_mm[1], bbox_mm[2]
        # long_thin: 长宽比 > 5
        if width > 0:
            ratio = length / width
            cls.long_thin_ratio = round(ratio, 2)
            if ratio > 5.0 and cls.part_class == "feature_part":
                cls.part_class = "long_thin"
                cls.reason = f"long_thin ratio={ratio:.2f}"
        # tiny_part: 最大尺寸 < 30mm
        if length < 30.0:
            cls.is_tiny = True
            if cls.part_class == "feature_part":
                cls.part_class = "tiny_part"
                cls.reason = f"tiny_part length={length:.1f}mm"
        # sheet_like: 高度 < 5mm 且长宽面积 > 1000 mm²
        if height < 5.0 and length * width > 1000.0:
            cls.is_sheet_like = True
            if cls.part_class == "feature_part":
                cls.part_class = "sheet_like"
                cls.reason = f"sheet_like height={height:.1f}mm area={length*width:.0f}mm²"

    # 4) 特征数检查（辅助判断 imported_body）
    has_feat = _check_has_features(part_path)
    cls.has_features = has_feat
    if has_feat is False and cls.part_class == "feature_part":
        # 无特征且未被其他规则匹配 -> imported_body
        cls.part_class = "imported_body"
        cls.reason = "no features (imported body)"

    # 5) 历史 dim_total 辅助判断
    # 如果历史 dim_total=0 且不是采购类，可能是 imported_body
    if history_dim_total == 0 and cls.part_class == "feature_part":
        # 不直接改分类，但记录 reason
        cls.reason = f"{cls.reason}; history dim_total=0 (suspect imported_body)"

    # 写 part_class.json
    if write_json:
        if out_dir is None:
            out_dir = p.parent
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        json_path = out_dir / "part_class.json"
        json_path.write_text(json.dumps(cls.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    return cls


def main():
    """命令行测试"""
    import sys
    if len(sys.argv) < 2:
        print("Usage: python part_classification_service.py <part_path> [history_dim_total]")
        sys.exit(1)
    part_path = sys.argv[1]
    hist = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    cls = classify_part(part_path, history_dim_total=hist)
    print(json.dumps(cls.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
