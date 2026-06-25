"""v2.3 Task 4: 生成输出扫描器

扫描所有生成的图纸输出文件(PDF/PNG/SLDDRW/DXF),检查是否有对应的 vision_qc JSON。
用于生成输出视觉审计。
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class GeneratedFile:
    """生成的图纸文件"""
    path: str
    file_type: str  # pdf/png/slddrw/dxf/json
    size_bytes: int
    modified_at: str
    base_name: str  # 零件名(不含扩展名)
    run_dir: str  # 父级 run 目录
    has_vision_qc: bool = False
    vision_qc_version: str = ""  # v3/v4/v5
    vision_qc_path: str = ""


class GeneratedOutputScanner:
    """生成输出扫描器"""
    
    def __init__(self, scan_dirs: Optional[list[str]] = None):
        """初始化扫描器
        
        Args:
            scan_dirs: 扫描目录列表,默认为 None 使用默认目录
        """
        if scan_dirs is None:
            # 默认扫描目录
            repo_root = Path(__file__).resolve().parent.parent.parent
            self.scan_dirs = [
                str(repo_root / "drw_output" / "runs"),
                str(repo_root / "drw_output" / "v5"),
                str(repo_root / "drw_output" / "v22_validation"),
                str(repo_root / "drw_output" / "batch_reports"),
            ]
        else:
            self.scan_dirs = scan_dirs
    
    def scan(self) -> list[GeneratedFile]:
        """扫描所有生成文件
        
        Returns:
            按路径排序的生成文件列表
        """
        files: list[GeneratedFile] = []
        
        # 支持的文件类型
        target_extensions = {".pdf", ".png", ".slddrw", ".dxf"}
        
        for scan_dir in self.scan_dirs:
            scan_path = Path(scan_dir)
            if not scan_path.exists():
                continue
            
            # 递归遍历目录
            for root, dirs, filenames in os.walk(scan_path):
                root_path = Path(root)
                for filename in filenames:
                    file_path = root_path / filename
                    ext = file_path.suffix.lower()
                    
                    # 只处理目标文件类型
                    if ext not in target_extensions:
                        continue
                    
                    # 提取基础信息
                    stat = file_path.stat()
                    base_name = file_path.stem
                    file_type = ext[1:]  # 去掉点号
                    
                    # 检查是否有对应的 vision_qc JSON
                    has_vision_qc = False
                    vision_qc_version = ""
                    vision_qc_path = ""
                    
                    # 查找 vision_qc JSON 文件
                    # 可能的命名模式:
                    # 1. {base_name}_vision_qc_v5.json
                    # 2. vision_qc_v5.json (在 qc/ 子目录)
                    # 3. {base_name}_qc.json (旧版本)
                    
                    run_root = _find_run_root(file_path)
                    qc_candidates = [
                        file_path.parent / f"{base_name}_vision_qc_v5.json",
                        file_path.parent / f"{base_name}_vision_qc_v4.json",
                        file_path.parent / f"{base_name}_vision_qc_v3.json",
                        file_path.parent / "qc" / "vision_qc_v5.json",
                        file_path.parent / "qc" / "vision_qc_v4.json",
                        file_path.parent / "qc" / "vision_qc_v3.json",
                    ]
                    if run_root is not None:
                        qc_candidates.extend([
                            run_root / "qc" / "vision_qc_v5.json",
                            run_root / "qc" / "vision_qc_v4.json",
                            run_root / "qc" / "vision_qc_v3.json",
                            run_root / "qc" / f"{base_name}_vision_qc_v5.json",
                            run_root / "qc" / f"{base_name}_vision_qc_v4.json",
                            run_root / "qc" / f"{base_name}_vision_qc_v3.json",
                            run_root / "qc" / f"{base_name}_qc.json",
                        ])
                    
                    for qc_path in qc_candidates:
                        if qc_path.exists():
                            has_vision_qc = True
                            vision_qc_path = str(qc_path)
                            # 从文件名提取版本号
                            if "v5" in qc_path.name:
                                vision_qc_version = "v5"
                            elif "v4" in qc_path.name:
                                vision_qc_version = "v4"
                            elif "v3" in qc_path.name:
                                vision_qc_version = "v3"
                            break
                    
                    # 创建 GeneratedFile 对象
                    gen_file = GeneratedFile(
                        path=str(file_path),
                        file_type=file_type,
                        size_bytes=stat.st_size,
                        modified_at=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
                        base_name=base_name,
                        run_dir=str(root_path),
                        has_vision_qc=has_vision_qc,
                        vision_qc_version=vision_qc_version,
                        vision_qc_path=vision_qc_path,
                    )
                    files.append(gen_file)
        
        # 按路径排序
        files.sort(key=lambda f: f.path)
        return files
    
    def find_missing_vision_qc(self) -> list[GeneratedFile]:
        """查找缺少 vision_qc 的文件
        
        Returns:
            缺少 vision_qc 的文件列表
        """
        all_files = self.scan()
        return [f for f in all_files if not f.has_vision_qc]
    
    def group_by_base(self) -> dict[str, list[GeneratedFile]]:
        """按基础名称分组
        
        Returns:
            {base_name: [GeneratedFile, ...]} 字典
        """
        all_files = self.scan()
        grouped: dict[str, list[GeneratedFile]] = {}
        
        for f in all_files:
            if f.base_name not in grouped:
                grouped[f.base_name] = []
            grouped[f.base_name].append(f)
        
        return grouped
    
    def get_summary(self) -> dict:
        """获取扫描摘要
        
        Returns:
            包含统计信息的字典
        """
        all_files = self.scan()
        
        # 按类型统计
        by_type: dict[str, int] = {}
        for f in all_files:
            by_type[f.file_type] = by_type.get(f.file_type, 0) + 1
        
        # 统计缺少 vision_qc 的数量
        missing_qc_count = sum(1 for f in all_files if not f.has_vision_qc)
        
        return {
            "total_files": len(all_files),
            "by_type": by_type,
            "missing_qc_count": missing_qc_count,
            "scan_dirs": self.scan_dirs,
        }


def _find_run_root(file_path: Path) -> Path | None:
    """Return the nearest run root containing drawing/qc/logs folders."""
    for parent in [file_path.parent, *file_path.parents]:
        if (parent / "qc").is_dir() and ((parent / "drawing").is_dir() or (parent / "manifest.json").exists()):
            return parent
    return None
