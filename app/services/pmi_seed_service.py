"""v2.1 Task 3: PMI Seed Service

调用 Add-in 的 SeedPMI 方法:
  1. 复制原始 part 到 run_dir/input_work
  2. 在副本中创建 overall_length / width / height 的 PMI 或 annotation
  3. 保存副本（不修改原文件）
  4. 返回副本路径 + 尺寸信息

原则: 不修改原始 SLDPRT，只允许修改 run_dir/input_work 副本
"""
from __future__ import annotations
import json
import time
from pathlib import Path


def seed_pmi(
    part_path: str,
    run_dir: Path = None,
    run_id: str = "",
) -> dict:
    """v2.1 Task 3: PMI Seed

    Args:
        part_path: 原始 SLDPRT 绝对路径
        run_dir: run_dir 根目录
        run_id: run_id

    Returns:
        {
            "success": bool,
            "method": str,
            "seed_part_path": str,
            "seed_dim_count": int,
            "overall_length": float,
            "overall_width": float,
            "overall_height": float,
            "reason": str,
        }
    """
    part_path = str(Path(part_path).resolve())
    run_dir_str = str(run_dir) if run_dir else ""

    try:
        from app.services.sw_addin_client import _get_sw_app, _find_addin
        sw = _get_sw_app()
    except Exception as e:
        return {
            "success": False,
            "method": "none",
            "reason": f"SolidWorks 未运行: {e}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    result = {
        "success": False,
        "method": "addin",
        "reason": "",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "engine_version": "v3.0",
    }

    try:
        addin, method = _find_addin(sw)
        if addin is None:
            result["reason"] = "Add-in 未加载"
            result["method"] = "none"
            return result
        result["method"] = method

        ret = addin.SeedPMI(part_path, run_id, run_dir_str)
        if isinstance(ret, str):
            try:
                parsed = json.loads(ret)
                result.update(parsed)
            except Exception:
                result["reason"] = f"Add-in 返回非 JSON: {ret[:200]}"
        else:
            result["reason"] = f"Add-in 返回类型异常: {type(ret)}"
    except Exception as e:
        result["reason"] = f"SeedPMI 异常: {e}"
        result["method"] = "exception"

    # 写入 pmi_seed.json
    if run_dir is not None:
        try:
            qc_dir = Path(run_dir) / "qc"
            qc_dir.mkdir(parents=True, exist_ok=True)
            out_path = qc_dir / "pmi_seed.json"
            out_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            result["output_path"] = str(out_path)
        except Exception as e:
            result["write_error"] = str(e)

    return result


def main():
    """CLI: python pmi_seed_service.py <part_path> [run_dir] [run_id]"""
    import sys
    if len(sys.argv) < 2:
        print("Usage: python pmi_seed_service.py <part_path> [run_dir] [run_id]")
        sys.exit(1)

    part_path = sys.argv[1]
    run_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    run_id = sys.argv[3] if len(sys.argv) > 3 else ""

    result = seed_pmi(part_path, run_dir, run_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
