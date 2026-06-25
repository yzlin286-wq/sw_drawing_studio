"""验证 v2.3 Task 4 和 Task 5 的新模块"""
import sys
from pathlib import Path

# 确保可以导入 app 模块
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 60)
print("验证 sw_drawing_studio v2.3 Task 4 & Task 5 新模块")
print("=" * 60)

modules_to_test = [
    ("generated_output_scanner", "GeneratedOutputScanner, GeneratedFile"),
    ("visual_audit_service", "VisualAuditService, AuditResult"),
    ("visual_audit_reporter", "VisualAuditReporter"),
    ("vision_qc_v5", "run_vision_qc_v5, VisionIssue"),
    ("vision_evidence_fusion", "EvidenceFusion"),
    ("vision_false_positive_filter", "VisionFalsePositiveFilter, FalsePositiveRule, DEFAULT_RULES"),
    ("vision_issue_tracker", "VisionIssueTracker"),
]

success_count = 0
fail_count = 0

for module_name, exports in modules_to_test:
    try:
        module = __import__(f"app.services.{module_name}", fromlist=exports.split(", "))
        print(f"✓ {module_name:30s} - 导入成功")
        success_count += 1
    except Exception as e:
        print(f"✗ {module_name:30s} - 导入失败: {e}")
        fail_count += 1

print("=" * 60)
print(f"验证结果: 成功 {success_count}, 失败 {fail_count}")
print("=" * 60)

if fail_count == 0:
    print("\n✓ 所有模块导入成功!")
    sys.exit(0)
else:
    print(f"\n✗ {fail_count} 个模块导入失败")
    sys.exit(1)
