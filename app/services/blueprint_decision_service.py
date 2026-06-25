"""v2.1 Task 7: Blueprint Decision Service - 蓝图可解释化

读取 part_class.json + drawing_blueprints.yaml，生成 blueprint_decision.json

输出解释:
  - 为什么选择该 part_class（基于 filename/bbox/standard_part/feature_count）
  - 为什么选择该 dimension_policy（基于 part_class 的 dimension_policy_detail）
  - 为什么选择该 vision_policy（基于 part_class 的 vision_policy）
  - required/optional dimension 列表
  - 预期 min_display_dim_count
  - 策略顺序（strategy_order）

输出文件: run_dir/qc/blueprint_decision.json
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BLUEPRINT_YAML = REPO_ROOT / "config" / "drawing_blueprints.yaml"


def _load_blueprints() -> dict:
    """加载 drawing_blueprints.yaml"""
    try:
        import yaml
        if not BLUEPRINT_YAML.exists():
            return {}
        with open(BLUEPRINT_YAML, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        return {"_load_error": str(e)}


def _load_part_class(run_dir: Path) -> dict:
    """加载 part_class.json"""
    candidates = [
        run_dir / "qc" / "part_class.json",
        run_dir / "part_class.json",
    ]
    for c in candidates:
        if c.exists():
            try:
                return json.loads(c.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {}


def _explain_part_class(part_class_data: dict) -> str:
    """解释为什么选择该 part_class"""
    if not part_class_data:
        return "未找到 part_class.json，使用默认 part_class=feature_part"

    part_class = part_class_data.get("part_class", "feature_part")
    reason = part_class_data.get("reason", "")
    bbox_mm = part_class_data.get("bbox_mm")
    is_standard = part_class_data.get("is_standard", False)
    long_thin_ratio = part_class_data.get("long_thin_ratio")
    is_tiny = part_class_data.get("is_tiny", False)
    is_sheet_like = part_class_data.get("is_sheet_like", False)
    has_features = part_class_data.get("has_features")

    parts = [f"part_class={part_class}"]

    if "filename match" in reason:
        parts.append(f"文件名匹配规则 ({reason})")
    if is_standard:
        std_no = part_class_data.get("std_no", "")
        std_spec = part_class_data.get("std_spec", "")
        parts.append(f"标准件库匹配 (std_no={std_no}, spec={std_spec})")
    if bbox_mm and len(bbox_mm) >= 3:
        parts.append(f"bbox=[L={bbox_mm[0]:.1f}, W={bbox_mm[1]:.1f}, H={bbox_mm[2]:.1f}]mm")
    if long_thin_ratio is not None and long_thin_ratio > 5.0:
        parts.append(f"长宽比={long_thin_ratio:.2f} > 5.0 (细长件)")
    if is_tiny:
        parts.append("最大尺寸 < 30mm (微小件)")
    if is_sheet_like:
        parts.append("高度 < 5mm 且面积 > 1000mm² (板状件)")
    if has_features is False:
        parts.append("无特征 (导入几何体)")

    parts.append(f"reason={reason}")
    return "; ".join(parts)


def _explain_dimension_policy(part_class: str, blueprint: dict) -> dict:
    """解释为什么选择该 dimension_policy"""
    detail = blueprint.get("dimension_policy_detail", {})
    policy = blueprint.get("dimension_policy", "outline_only")
    engine = blueprint.get("dimension_engine", {})

    return {
        "policy": policy,
        "required_dims": detail.get("required", []),
        "optional_dims": detail.get("optional", []),
        "note": detail.get("note", ""),
        "strategy_order": engine.get("strategy_order", []),
        "require_display_dim": engine.get("require_display_dim", False),
        "min_display_dim_count": engine.get("min_display_dim_count", 0),
        "allow_note_annotation": engine.get("allow_note_annotation", False),
        "explanation": (
            f"part_class={part_class} 选择 dimension_policy={policy}: {detail.get('note', '')}. "
            f"必须标注 {len(detail.get('required', []))} 类尺寸，"
            f"可选标注 {len(detail.get('optional', []))} 类尺寸，"
            f"最少 DisplayDim 数量={engine.get('min_display_dim_count', 0)}."
        ),
    }


def _explain_vision_policy(part_class: str, blueprint: dict) -> dict:
    """解释为什么选择该 vision_policy"""
    policy = blueprint.get("vision_policy", "basic")

    explanations = {
        "strict": "严格视觉质检：用于 feature_part/long_thin/sheet_metal/weldment 等需要完整尺寸标注的零件",
        "basic": "基础视觉质检：用于 imported_body/sheet_like 等仅需外形尺寸的零件",
        "lenient": "宽松视觉质检：用于 fastener/spring/purchased_part 等采购/标准件，允许 C 级",
    }

    return {
        "policy": policy,
        "explanation": explanations.get(policy, f"vision_policy={policy}"),
    }


def _explain_titlebar_policy(part_class: str, blueprint: dict) -> dict:
    """解释 titlebar_policy"""
    policy = blueprint.get("titlebar_policy", "standard")
    return {
        "policy": policy,
        "explanation": f"标题栏策略={policy}",
    }


def _explain_tolerance_policy(part_class: str, blueprint: dict) -> dict:
    """解释 tolerance_policy"""
    policy = blueprint.get("tolerance_policy", "general")
    explanations = {
        "general": "一般公差（GB/T 1804-m）",
        "detailed": "详细公差标注（每个尺寸单独标注公差）",
        "length_focus": "长度方向公差优先（细长件）",
        "sheet_metal": "钣金公差（GB/T 1804-m + 弯曲公差）",
        "weldment": "焊接件公差（GB/T 19804）",
        "standard": "标准件公差（按标准件规范）",
    }
    return {
        "policy": policy,
        "explanation": explanations.get(policy, f"tolerance_policy={policy}"),
    }


def generate_blueprint_decision(
    run_dir: Path,
    part_class_data: dict = None,
    run_id: str = "",
) -> dict:
    """v2.1 Task 7: 生成 blueprint_decision.json

    Args:
        run_dir: run_dir 根目录
        part_class_data: part_class.json 数据（None 则从 run_dir 加载）
        run_id: run_id

    Returns:
        blueprint_decision dict
    """
    run_dir = Path(run_dir)
    run_id = run_id or run_dir.name

    # 加载 part_class.json
    if part_class_data is None:
        part_class_data = _load_part_class(run_dir)

    part_class = part_class_data.get("part_class", "feature_part") if part_class_data else "feature_part"

    # 加载 blueprints
    blueprints = _load_blueprints()
    blueprint = blueprints.get(part_class, blueprints.get("default", {}))

    # 生成决策解释
    decision = {
        "version": "v2.1",
        "run_id": run_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "part_class": part_class,
        "part_class_explanation": _explain_part_class(part_class_data),
        "part_class_source": part_class_data,
        "dimension_policy": _explain_dimension_policy(part_class, blueprint),
        "vision_policy": _explain_vision_policy(part_class, blueprint),
        "titlebar_policy": _explain_titlebar_policy(part_class, blueprint),
        "tolerance_policy": _explain_tolerance_policy(part_class, blueprint),
        "views": blueprint.get("views", []),
        "notes_policy": blueprint.get("notes_policy", "standard"),
        "blueprint_yaml_path": str(BLUEPRINT_YAML),
        "blueprint_matched": part_class in blueprints,
        "blueprint_fallback_used": part_class not in blueprints,
        "summary": {
            "part_class": part_class,
            "dimension_policy": blueprint.get("dimension_policy", "outline_only"),
            "vision_policy": blueprint.get("vision_policy", "basic"),
            "required_dims_count": len(blueprint.get("dimension_policy_detail", {}).get("required", [])),
            "optional_dims_count": len(blueprint.get("dimension_policy_detail", {}).get("optional", [])),
            "min_display_dim_count": blueprint.get("dimension_engine", {}).get("min_display_dim_count", 0),
            "require_display_dim": blueprint.get("dimension_engine", {}).get("require_display_dim", False),
        },
    }

    # 写入 blueprint_decision.json
    try:
        qc_dir = run_dir / "qc"
        qc_dir.mkdir(parents=True, exist_ok=True)
        out_path = qc_dir / "blueprint_decision.json"
        out_path.write_text(
            json.dumps(decision, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        decision["output_path"] = str(out_path)
    except Exception as e:
        decision["write_error"] = str(e)

    return decision


def load_blueprint_decision(run_dir: Path) -> dict:
    """加载已有的 blueprint_decision.json"""
    try:
        bp_path = Path(run_dir) / "qc" / "blueprint_decision.json"
        if bp_path.exists():
            return json.loads(bp_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def main():
    """CLI: python blueprint_decision_service.py <run_dir> [run_id]"""
    import sys
    if len(sys.argv) < 2:
        print("Usage: python blueprint_decision_service.py <run_dir> [run_id]")
        sys.exit(1)
    run_dir = Path(sys.argv[1])
    run_id = sys.argv[2] if len(sys.argv) > 2 else ""
    decision = generate_blueprint_decision(run_dir, run_id=run_id)
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
