"""model_dim_seed_service.py — v1.6 Task 1: 模型副本尺寸源注入服务

对疑难件（InsertModelAnnotations3 失败的件）复制 SLDPRT 到 run_dir，
在副本中创建 AUTO_DIM_GUIDE 3D sketch 和参考尺寸，
让 drw_generate_v6 使用副本出图，使 InsertModelAnnotations3 能从副本的 3D sketch 中导入尺寸。

解决 dim_total=0 问题：导入几何体（无特征尺寸）的件无法通过 InsertModelAnnotations3 导出尺寸，
通过在副本中手动创建 3D 参考尺寸，为出图提供尺寸源。
"""
import os
import json
import shutil
import traceback
from pathlib import Path

from app.services.solidworks_global_lock import require_current_job_lock


def seed_model_dimensions(part_path: str, run_dir: Path) -> dict:
    """主函数：复制 SLDPRT 副本，在副本中创建 AUTO_DIM_GUIDE 3D 参考尺寸。

    Args:
        part_path: 原始 SLDPRT 文件路径
        run_dir: 工作目录（input_work），副本和 seed_dim.json 存放于此

    Returns:
        dict: {
            "work_part_path": str,      # 副本绝对路径
            "seed_dim_count": int,      # 创建的尺寸数量
            "bbox": {xmin,ymin,zmin,xmax,ymax,zmax},
            "overall_length": float,    # xmax - xmin
            "overall_width": float,     # ymax - ymin
            "overall_height": float,    # zmax - zmin
            "success": bool,
            "error": str,               # 失败时的错误信息
        }
    """
    result = {
        "work_part_path": "",
        "seed_dim_count": 0,
        "bbox": {},
        "overall_length": 0.0,
        "overall_width": 0.0,
        "overall_height": 0.0,
        "success": False,
        "error": "",
    }
    guard = require_current_job_lock("model_dim_seed_service.seed_model_dimensions")
    if not guard.get("ok"):
        result.update({
            "status": "blocked_by_solidworks_lock",
            "failure_bucket": "solidworks_lock_conflict",
            "error": "blocked_by_solidworks_lock",
            "reason": guard.get("reason", ""),
            "owner": guard.get("owner", {}),
            "fix_suggestion": guard.get("fix_suggestion", "等待当前 CAD job 完成，或手动确认后释放 stale lock"),
        })
        _write_seed_dim_json(run_dir, result)
        return result

    # 保留原始 run_dir 参数引用，用于最后写 seed_dim.json
    _run_dir_orig = run_dir

    try:
        part_path = str(Path(part_path).resolve())
        run_dir = Path(run_dir).resolve()
        run_dir.mkdir(parents=True, exist_ok=True)

        base = os.path.splitext(os.path.basename(part_path))[0]
        work_part_path = str(run_dir / f"{base}_seed.SLDPRT")

        # 2) 复制 SLDPRT 到副本（不修改原始文件）
        try:
            shutil.copy2(part_path, work_part_path)
        except Exception as exc:
            result["error"] = f"复制文件失败: {exc}"
            _write_seed_dim_json(_run_dir_orig, result)
            return result

        # 3) 用 pywin32 连接 SolidWorks（参考 drw_generate_v6.py L580-597）
        try:
            import pythoncom
            import win32com.client as wc
            from win32com.client import VARIANT
        except ImportError as exc:
            result["error"] = f"pywin32 导入失败: {exc}"
            _write_seed_dim_json(_run_dir_orig, result)
            return result

        sw = None
        try:
            sw = wc.GetActiveObject("SldWorks.Application")
        except Exception:
            try:
                sw = wc.Dispatch("SldWorks.Application")
                sw.Visible = True
                import time
                time.sleep(2)
            except Exception as exc:
                result["error"] = f"连接 SolidWorks 失败: {exc}"
                _write_seed_dim_json(_run_dir_orig, result)
                return result

        if sw is None:
            result["error"] = "SolidWorks 连接返回 None"
            _write_seed_dim_json(_run_dir_orig, result)
            return result

        # 4) OpenDoc6 打开副本（Type=1 swDocPART, Options=1|16|256）
        e = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        w = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        part = None
        try:
            part = sw.OpenDoc6(work_part_path, 1, 1 | 16 | 256, "", e, w)
        except Exception as exc:
            result["error"] = f"OpenDoc6 异常: {exc}"
            _write_seed_dim_json(_run_dir_orig, result)
            return result

        # OpenDoc6 可能因 FileAlreadyOpen(65536) 返回 None，尝试 ActivateDoc3
        if part is None:
            try:
                err_act = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                part = sw.ActivateDoc3(work_part_path, True, 0, err_act)
            except Exception:
                pass
        if part is None:
            # 尝试用文件名（不含路径）激活
            try:
                err_act2 = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                part = sw.ActivateDoc3(os.path.basename(work_part_path), True, 0, err_act2)
            except Exception:
                pass

        if part is None:
            result["error"] = f"OpenDoc6 返回 None, errors={e.value}"
            _write_seed_dim_json(_run_dir_orig, result)
            return result

        # 5) GetPartBox(True) 获取 bbox（返回 flat 6 元素 [xmin,ymin,zmin,xmax,ymax,zmax]）
        bbox = None
        try:
            bbox = part.GetPartBox(True)
        except Exception as exc:
            result["error"] = f"GetPartBox 失败: {exc}"
            try:
                sw.CloseDoc(work_part_path)
            except Exception:
                pass
            _write_seed_dim_json(_run_dir_orig, result)
            return result

        try:
            coords = list(bbox) if bbox is not None else []
        except Exception:
            coords = []

        if len(coords) < 6:
            result["error"] = f"GetPartBox 返回数据不足: {coords}"
            try:
                sw.CloseDoc(work_part_path)
            except Exception:
                pass
            _write_seed_dim_json(_run_dir_orig, result)
            return result

        xmin, ymin, zmin, xmax, ymax, zmax = [float(c) for c in coords[:6]]
        result["bbox"] = {
            "xmin": xmin, "ymin": ymin, "zmin": zmin,
            "xmax": xmax, "ymax": ymax, "zmax": zmax,
        }
        result["overall_length"] = xmax - xmin   # 总长
        result["overall_width"] = ymax - ymin    # 总宽
        result["overall_height"] = zmax - zmin   # 总高

        # 6) 进入 3D 草图
        sm = part.SketchManager
        try:
            sm.Insert3DSketch(True)
        except Exception as exc:
            result["error"] = f"Insert3DSketch 失败: {exc}"
            try:
                sw.CloseDoc(work_part_path)
            except Exception:
                pass
            _write_seed_dim_json(_run_dir_orig, result)
            return result

        # 7) 创建 AUTO_DIM_GUIDE 3D sketch：3 条参考线 + 尺寸
        dim_count = 0
        # 尺寸文本偏移量（取最大外形尺寸的 10%，至少 10mm=0.01m）
        max_dim = max(result["overall_length"], result["overall_width"], result["overall_height"])
        offset = max_dim * 0.1
        if offset < 0.01:
            offset = 0.01

        # 3 条参考线：总长线(X)、总宽线(Y)、总高线(Z)
        # 每条线从 (xmin,ymin,zmin) 出发
        lines_data = [
            # (x1, y1, z1, x2, y2, z2, dim_x, dim_y, dim_z)
            (xmin, ymin, zmin, xmax, ymin, zmin,           # 总长线
             (xmin + xmax) / 2.0, ymin - offset, zmin),
            (xmin, ymin, zmin, xmin, ymax, zmin,           # 总宽线
             xmin - offset, (ymin + ymax) / 2.0, zmin),
            (xmin, ymin, zmin, xmin, ymin, zmax,           # 总高线
             xmin - offset, ymin, (zmin + zmax) / 2.0),
        ]

        for x1, y1, z1, x2, y2, z2, dx, dy, dz in lines_data:
            try:
                # 清除当前选择
                try:
                    part.ClearSelection2(True)
                except Exception:
                    pass

                # 用 SketchManager.CreateLine 创建 3D 参考线
                line = None
                try:
                    line = sm.CreateLine(x1, y1, z1, x2, y2, z2)
                except Exception as exc:
                    print(f"  [seed] CreateLine 异常: {exc}")

                if line is None:
                    print(f"  [seed] CreateLine 返回 None, 跳过")
                    continue

                # 选中线端点（3D 模型中 AddDimension2 需要 SelectByID2 选中线端点）
                selected = False
                # 方式1：通过 SketchPoint.Select4 选中端点
                try:
                    sp = line.GetStartPoint2()
                    ep = line.GetEndPoint2()
                    if sp is not None and ep is not None:
                        try:
                            sp.Select4(False, None)
                        except Exception as exc:
                            print(f"  [seed] sp.Select4 异常: {exc}")
                        try:
                            ep.Select4(True, None)
                        except Exception as exc:
                            print(f"  [seed] ep.Select4 异常: {exc}")
                        selected = True
                except Exception as exc:
                    print(f"  [seed] GetStartPoint2/EndPoint 异常: {exc}")

                # 方式2（回退）：用 Extension.SelectByID2 按坐标选中端点
                if not selected:
                    try:
                        part.Extension.SelectByID2(
                            "", "EXTSKETCHPOINT", x1, y1, z1,
                            False, 1, None, 0)
                        part.Extension.SelectByID2(
                            "", "EXTSKETCHPOINT", x2, y2, z2,
                            True, 1, None, 0)
                        selected = True
                    except Exception as exc:
                        print(f"  [seed] SelectByID2 EXTSKETCHPOINT 异常: {exc}")

                # 方式3：直接选中线（不是端点）
                if not selected:
                    try:
                        line.Select4(False, None)
                        selected = True
                        print(f"  [seed] 用 line.Select4 选中线")
                    except Exception as exc:
                        print(f"  [seed] line.Select4 异常: {exc}")

                # 用 part.AddDimension2(x, y, z) 添加尺寸
                dim = None
                try:
                    dim = part.AddDimension2(dx, dy, dz)
                except Exception as exc:
                    print(f"  [seed] AddDimension2 异常: {exc}")

                if dim is not None:
                    dim_count += 1
                    print(f"  [seed] AddDimension2 成功, dim_count={dim_count}")
                else:
                    print(f"  [seed] AddDimension2 返回 None")
            except Exception as exc:
                print(f"  [seed] 循环异常: {exc}")

        # 8) 退出草图
        try:
            sm.InsertSketch(True)
        except Exception:
            pass  # 即使退出失败也继续尝试保存

        # 强制重建，确保草图尺寸生效
        try:
            part.EditRebuild3()
        except Exception:
            pass

        # 9) 保存副本（参考 drw_generate_v6.py L1668 的 SaveAs）
        saved = False
        try:
            saved = part.SaveAs3(work_part_path, 0, 0)
        except Exception:
            try:
                saved = part.SaveAs3(work_part_path, 0, 0)
            except Exception:
                pass

        if not saved:
            # 回退：使用 Extension.SaveAs
            try:
                err_v = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                warn_v = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                saved = part.Extension.SaveAs(
                    work_part_path, 0, 1, None, err_v, warn_v)
            except Exception:
                pass

        if not saved:
            # 最后回退：Save()
            try:
                part.Save()
                saved = True
            except Exception:
                pass

        # 10) 关闭副本
        try:
            sw.CloseDoc(work_part_path)
        except Exception:
            pass

        result["work_part_path"] = work_part_path
        result["seed_dim_count"] = dim_count
        result["success"] = True

    except Exception as exc:
        result["error"] = f"未预期异常: {exc}\n{traceback.format_exc()}"

    # 12) 写 seed_dim.json 到 run_dir/seed_dim.json
    _write_seed_dim_json(_run_dir_orig, result)

    return result


def _write_seed_dim_json(run_dir, result: dict) -> None:
    """将 seed 结果写入 run_dir/seed_dim.json"""
    try:
        run_dir_path = Path(run_dir).resolve()
        run_dir_path.mkdir(parents=True, exist_ok=True)
        json_path = str(run_dir_path / "seed_dim.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
