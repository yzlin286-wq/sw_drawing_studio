# 小零件出图质量硬化 v1.5 Spec

## Why
v1.4 验证暴露 3 个系统性限制：(1) `InsertModelAnnotations3` 缺第 7 个参数 `FeatTolType` 导致 COM 异常，且 `InsertDimension2` 兜底未选中几何体，对弹簧/螺丝/AC 系列/002/003/007/009 等 8+ 件 `dim_total=0`；(2) `view_in_frame` 重定位 iso 视图后未重新检测重叠，导致 004 等件生成时无重叠、QC 时判 view_overlap 失败；(3) `sw.GetExportFileData(2)` 在 SW2025 返回 None，PNG 直接导出链路冗余失败（已用 PDF→PyMuPDF 回退规避，但冗余 COM 调用增加耗时）。

## What Changes
- 修复 `drw_generate_v6.py` 的 `InsertModelAnnotations3` 调用：补全第 7 个参数 `FeatTolType=0`（`swFeatureTolType_e.swFeatureTolType_None`），与 `sw_com_api_index.md` L115 的 7 参数签名对齐。
- 增强 `InsertDimension2` 兜底逻辑：在调用前用 `view.GetEdges` / `view.GetVertices` 枚举视图几何体，`SelectByID2` 选中边/顶点后再插入尺寸，确保尺寸附着到实体。
- 新增"轮廓尺寸降级"兜底：当 `InsertModelAnnotations3` + `InsertDimension2` 均未使 `dim_total ≥ 5` 时，用 `part.GetPartBox(True)` 获取包围盒角点，`SelectByID2` 选中后插入总长/总宽/总高 3 个尺寸，确保 `dim_total ≥ 3`（满足 `dim_count_sufficient` 阈值 5 的 60% 兜底）。
- 修复 `view_in_frame` 重定位后未重新检测重叠：在 `ForceRebuild3` 之后重新测量 outline + 重新检测 overlap，若仍有重叠则进入降档循环（复用 L970-993 逻辑）。
- 清理 `drw_generate_v6.py` 的冗余 `sw.GetExportFileData(2)` 调用：直接走 PDF→PyMuPDF 回退路径（run_manager.py 已实现），减少一次失败 COM 调用。
- **BREAKING**：无（所有修改向后兼容，`pick_scale_with_layout` 返回值不变）。

## Impact
- Affected specs: `harden-drawing-pipeline-quality-v1-4`（v1.4 已知限制 1/2/3 的系统性修复）、`improve-drawing-scale-titlebar-inspection`（view_overlap 检测准确性提升）、`build-v6-and-validate-exe-ui`（drw_generate_v6.py 尺寸+重叠+PNG 修复）
- Affected code:
  - `.trae/specs/build-v6-and-validate-exe-ui/drw_generate_v6.py`（InsertModelAnnotations3 参数 + InsertDimension2 选中几何体 + 轮廓尺寸降级 + view_in_frame 重检测 + PNG 冗余清理）
  - `.trae/specs/enforce-drawing-quality/drw_quality_check.py`（dim_count_sufficient 阈值文档化，无代码修改）
  - `.trae/specs/probe-solidworks-com-api/unresolved_apis.md`（补充记录 `GetExportFileData(2)` 不可用）

## ADDED Requirements

### Requirement: InsertDimension2 兜底选中几何体
系统 SHALL 在调用 `InsertDimension2` / `AddHorizontalDimension2` / `AddVerticalDimension2` 前，先用 `view.GetEdges` 或 `view.GetVertices` 枚举视图几何体，并 `SelectByID2` 选中目标边/顶点，确保尺寸附着到实体而非静默失败。

#### Scenario: 选中边后插入水平尺寸
- **WHEN** `InsertModelAnnotations3` 失败且 `dim_total < 5`
- **THEN** 调用 `view.GetEdges` 获取前视图可见边，`SelectByID2` 选中一条水平边后调 `AddHorizontalDimension2(x, y, 0.0)`，尺寸成功附着到该边

#### Scenario: 无可见边时降级
- **WHEN** `view.GetEdges` 返回空或选中失败
- **THEN** 进入"轮廓尺寸降级"逻辑，用 `part.GetPartBox(True)` 包围盒角点插入总长/总宽/总高 3 个尺寸

### Requirement: 轮廓尺寸降级兜底
系统 SHALL 在 `InsertModelAnnotations3` + `InsertDimension2` 均未使 `dim_total ≥ 5` 时，调用 `part.GetPartBox(True)` 获取包围盒，`SelectByID2` 选中包围盒角点后插入总长/总宽/总高 3 个尺寸，确保 `dim_total ≥ 3`。

#### Scenario: 导入几何体零件兜底
- **WHEN** 零件为 STEP/IGES 导入几何体（无特征尺寸），`InsertModelAnnotations3` 和 `InsertDimension2` 均未提取到尺寸
- **THEN** 用 `GetPartBox` 包围盒角点插入 3 个轮廓尺寸，`dim_total ≥ 3`，`dim_count_sufficient` 检查通过（阈值 5，3/5=60% 兜底）

### Requirement: view_in_frame 重定位后重新检测重叠
系统 SHALL 在 `view_in_frame` 重定位视图并 `ForceRebuild3` 之后，重新测量所有视图 outline 并重新检测 overlap；若仍有重叠，则进入降档循环（复用 L970-993 的 scale 降档逻辑）。

#### Scenario: 重定位引入新重叠
- **WHEN** iso 视图因越界被重定位后，与 right 视图产生新重叠
- **THEN** 重新检测发现重叠，进入降档循环（1:5 → 1:10），重新布局后无重叠，QC 的 `view_overlap` 检查通过

#### Scenario: 重定位后无新重叠
- **WHEN** iso 视图重定位后与其他视图无重叠
- **THEN** 保持当前比例和布局，不触发降档

## MODIFIED Requirements

### Requirement: InsertModelAnnotations3 调用签名
v1.4 的 `InsertModelAnnotations3(0, 32, True, True, False, False)` 只传 6 个参数，与 `sw_com_api_index.md` L115 的 7 参数签名不符，导致 COM 异常。v1.5 修改为 `InsertModelAnnotations3(0, 32, True, True, False, False, 0)`，第 7 个参数 `FeatTolType=0`（`swFeatureTolType_e.swFeatureTolType_None`）。

### Requirement: PNG 导出策略
v1.4 的 PNG 导出先尝试 `sw.GetExportFileData(2)`（swExportPngData），失败后回退 PDF→PyMuPDF。v1.5 移除 `GetExportFileData(2)` 调用，直接走 PDF→PyMuPDF 路径（run_manager.py L222-254 已实现并验证），减少一次失败 COM 调用。

### Requirement: view_in_frame 重定位后处理
v1.4 的 `view_in_frame` 重定位后直接 `ForceRebuild3` 并继续，未重新检测重叠。v1.5 修改为重定位 + `ForceRebuild3` 之后，重新测量 outline + 重新检测 overlap，必要时降档。

## REMOVED Requirements
（无）
