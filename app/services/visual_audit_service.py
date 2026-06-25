"""v2.3 Task 4: 视觉审计服务

对生成的图纸文件执行视觉审计,记录审计结果。
支持按 base_name 审计、重审失败项、生成审计索引。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.services.generated_output_scanner import GeneratedFile, GeneratedOutputScanner


@dataclass
class AuditResult:
    """单个文件的审计结果"""
    file_path: str
    base_name: str
    audit_status: str  # pass / fail / need_review / skipped
    vision_qc_version: str
    issues: list[dict] = field(default_factory=list)
    duration_ms: int = 0
    timestamp: str = ""


class VisualAuditService:
    """视觉审计服务"""

    def __init__(self, scanner: Optional[GeneratedOutputScanner] = None):
        """初始化审计服务

        Args:
            scanner: 生成输出扫描器,默认自动创建
        """
        self.scanner = scanner or GeneratedOutputScanner()

    def run_audit(
        self,
        files: Optional[list[GeneratedFile]] = None,
        only_unaudited: bool = True,
    ) -> list[AuditResult]:
        """运行视觉审计

        Args:
            files: 要审计的文件列表,为 None 时使用 scanner 扫描全部
            only_unaudited: 仅审计尚未有 vision_qc 的文件

        Returns:
            审计结果列表
        """
        if files is None:
            if only_unaudited:
                files = self.scanner.find_missing_vision_qc()
            else:
                files = self.scanner.scan()
        elif only_unaudited:
            files = [f for f in files if not f.has_vision_qc]

        results: list[AuditResult] = []
        for gf in files:
            result = self._audit_single(gf)
            results.append(result)

        return results

    def run_audit_for_base(self, base_name: str) -> AuditResult:
        """对指定 base_name 运行审计

        Args:
            base_name: 零件名称(不含扩展名)

        Returns:
            审计结果
        """
        all_files = self.scanner.scan()
        # 查找 PDF/PNG 文件
        target_files = [
            f for f in all_files
            if f.base_name == base_name and f.file_type in ("pdf", "png")
        ]

        if not target_files:
            return AuditResult(
                file_path="",
                base_name=base_name,
                audit_status="skipped",
                vision_qc_version="",
                issues=[],
                duration_ms=0,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

        # 优先使用 PDF
        gf = next((f for f in target_files if f.file_type == "pdf"), target_files[0])
        return self._audit_single(gf)

    def rerun_failed(self) -> list[AuditResult]:
        """重新审计失败或需要复审的文件

        Returns:
            重审结果列表
        """
        all_files = self.scanner.scan()
        # 查找有 vision_qc 但状态为 fail/need_review 的文件
        # 简化: 对所有文件重新审计
        results: list[AuditResult] = []
        for gf in all_files:
            if gf.file_type in ("pdf", "png"):
                result = self._audit_single(gf)
                if result.audit_status in ("fail", "need_review"):
                    results.append(result)
        return results

    def get_index(self) -> dict:
        """构建 visual_audit_index.json 结构

        Returns:
            审计索引字典
        """
        all_files = self.scanner.scan()
        grouped = self.scanner.group_by_base()

        index = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_files": len(all_files),
            "total_bases": len(grouped),
            "bases": {},
        }

        for base_name, file_list in grouped.items():
            has_qc = any(f.has_vision_qc for f in file_list)
            qc_version = ""
            qc_path = ""
            for f in file_list:
                if f.has_vision_qc:
                    qc_version = f.vision_qc_version
                    qc_path = f.vision_qc_path
                    break

            index["bases"][base_name] = {
                "file_count": len(file_list),
                "file_types": [f.file_type for f in file_list],
                "has_vision_qc": has_qc,
                "vision_qc_version": qc_version,
                "vision_qc_path": qc_path,
                "files": [
                    {
                        "path": f.path,
                        "file_type": f.file_type,
                        "size_bytes": f.size_bytes,
                        "modified_at": f.modified_at,
                    }
                    for f in file_list
                ],
            }

        return index

    def save_index(self, path: Path):
        """写入 visual_audit_index.json

        Args:
            path: 输出路径
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        index = self.get_index()
        path.write_text(
            json.dumps(index, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _audit_single(self, gf: GeneratedFile) -> AuditResult:
        """审计单个文件

        Args:
            gf: 生成文件对象

        Returns:
            审计结果
        """
        start = time.time()
        ts = time.strftime("%Y-%m-%d %H:%M:%S")

        # 仅对 PDF/PNG 执行审计
        if gf.file_type not in ("pdf", "png"):
            return AuditResult(
                file_path=gf.path,
                base_name=gf.base_name,
                audit_status="skipped",
                vision_qc_version="",
                duration_ms=int((time.time() - start) * 1000),
                timestamp=ts,
            )

        pdf_path = Path(gf.path) if gf.file_type == "pdf" else None
        png_path = Path(gf.path) if gf.file_type == "png" else None

        # 如果有 PDF, 优先用 PDF; 同时查找对应的 PNG
        if pdf_path and pdf_path.exists():
            candidate_png = pdf_path.with_suffix(".PNG")
            if not candidate_png.exists():
                candidate_png = pdf_path.with_suffix(".png")
            if candidate_png.exists():
                png_path = candidate_png
        elif png_path and png_path.exists():
            # 从 PNG 找对应 PDF
            candidate_pdf = png_path.with_suffix(".PDF")
            if not candidate_pdf.exists():
                candidate_pdf = png_path.with_suffix(".pdf")
            if candidate_pdf.exists():
                pdf_path = candidate_pdf

        # 运行 vision_qc_v5 (或 v4 fallback)
        try:
            from app.services.vision_qc_v5 import run_vision_qc_v5
            qc_result = run_vision_qc_v5(
                pdf_path=pdf_path,
                png_path=png_path,
                run_dir=Path(gf.run_dir),
            )
            version = "v5"
        except Exception:
            # v5 不可用, 尝试 v4
            try:
                from app.services.vision_qc_v4 import run_vision_qc_v4
                qc_result = run_vision_qc_v4(
                    pdf_path=pdf_path,
                    png_path=png_path,
                    run_dir=Path(gf.run_dir),
                )
                version = "v4"
            except Exception as e:
                return AuditResult(
                    file_path=gf.path,
                    base_name=gf.base_name,
                    audit_status="skipped",
                    vision_qc_version="",
                    issues=[{"key": "audit_error", "severity": "info", "description": str(e)}],
                    duration_ms=int((time.time() - start) * 1000),
                    timestamp=ts,
                )

        # 判断审计状态
        issues = qc_result.get("issues", [])
        critical_count = sum(1 for i in issues if i.get("severity") == "critical")
        major_count = sum(1 for i in issues if i.get("severity") == "major")

        if critical_count > 0:
            audit_status = "fail"
        elif major_count > 0:
            audit_status = "need_review"
        elif len(issues) == 0 or qc_result.get("success", False):
            audit_status = "pass"
        else:
            audit_status = "need_review"

        return AuditResult(
            file_path=gf.path,
            base_name=gf.base_name,
            audit_status=audit_status,
            vision_qc_version=version,
            issues=issues,
            duration_ms=int((time.time() - start) * 1000),
            timestamp=ts,
        )
