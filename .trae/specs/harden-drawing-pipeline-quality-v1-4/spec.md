# 出图管线质量硬化 v1.4 Spec

## Why
v1.2 全量验证暴露 5 个系统性问题：(1) `pick_scale_with_layout` 只考虑"无重叠"，不考虑"幅面利用率/可读性"，LLM 建议 1:5 放大到 1:1 但算法不会自动选更大比例；(2) SLDPRT 源文件未注入品名/图号/材质等属性时 `titlebar_complete` 报 warning，缺智能填充；(3) 116/129 件 `dim_total=0`，`RunCommand(826) InsertModelAnnotations` 在 SW2025 + pywin32 下未生效，2D 图无任何尺寸标注；(4) `full_pipeline` 子进程 sys.path 未含项目根，v1.3 新增 3 项 QC 在子进程中跳过；(5) 128/129 件 `png_missing`，PDF→PNG 转换链路系统性失败。

## What Changes
- 修复 `drw_qc_loop_v6.py` 子进程 sys.path：在 subprocess.run 前注入 `PYTHONPATH=<REPO_ROOT>`，让 v1.3 的 `scale_gb_standard` / `titlebar_complete` / `model_2d_consistency` 3 项 QC 在子进程中正常触发。
- 增强 `pick_scale_with_layout`：在"无重叠"基础上增加"幅面利用率"评分（视图总面积 / 工作区面积），优先选利用率 ≥ 40% 且无重叠的最大比例；可选集成 `scale_advisor.advise_scale` 作为后置验证（不阻断）。
- 新增 `app/services/titlebar_filler.py`：从文件名解析图号（如 `LB26001-A-04-001` → 图号=LB26001-A-04-001、类别=A、序号=001）；模板字段优先级：UI 录入 > 文件名解析 > 模板默认值 > SLDPRT 属性。
- 新增 `app/ui/titlebar_dialog.py`：标题栏字段录入对话框（PySide6 QDialog），用户可在出图前手动填写品名/图号/材质/数量等字段，覆盖文件名解析和模板默认值。
- 修复 2D 图尺寸标注：`drw_generate_v6.py` 改用 `Extension.InsertModelAnnotations3` 显式调用（替代 `RunCommand(826)`），并增加 `InsertDimension2` 兜底逐个插入关键尺寸；目标 `dim_total ≥ 5`。
- 修复 PNG 导出：`drw_generate_v6.py` 改用 SolidWorks COM 直接导出 PNG（`Extension.SaveAs` + `swExportPngData` 或 `swExportImageData`），替代 PDF→PyMuPDF 链路；目标 `png_missing` 降至 ≤ 10%。
- **BREAKING**：`pick_scale_with_layout` 返回值从 `(scale, outlines, [])` 扩展为 `(scale, outlines, [], utilization)`，调用方需适配。

## Impact
- Affected specs: `improve-drawing-scale-titlebar-inspection`（v1.3 的 scale_advisor / titlebar_complete / model_2d_consistency 在子进程中真正生效）、`build-v6-and-validate-exe-ui`（drw_generate_v6.py 比例+尺寸+PNG）、`validate-real-drawings-with-llm-vision`（v1.2 全量验证通过率提升）
- Affected code:
  - `.trae/specs/build-v6-and-validate-exe-ui/drw_qc_loop_v6.py`（子进程 sys.path 修复）
  - `.trae/specs/build-v6-and-validate-exe-ui/drw_generate_v6.py`（pick_scale_with_layout 增强 + InsertModelAnnotations3 + PNG 直接导出）
  - `app/services/titlebar_filler.py`（**新增**）
  - `app/ui/titlebar_dialog.py`（**新增**）
  - `app/services/__init__.py`（导出 titlebar_filler）
  - `app/ui/single_part_page.py`（出图前弹出 titlebar_dialog）
  - `app/services/run_manager.py`（full_pipeline 接收 titlebar_overrides 参数）

## ADDED Requirements

### Requirement: 子进程 sys.path 修复
系统 SHALL 在 `drw_qc_loop_v6.py` 的 `_run_v5()` subprocess.run 调用中注入 `PYTHONPATH=<REPO_ROOT>`，确保子进程能 `from app.services.scale_advisor import ...` 等模块导入。

#### Scenario: 子进程 QC 正常触发
- **WHEN** `full_pipeline` 调用 `drw_qc_loop_v6.py` 子进程
- **THEN** 子进程的 `drw_quality_check.py` 能正常导入 `app.services.scale_advisor` / `app.services.model_compare`，v1.3 的 3 项 QC（scale_gb_standard / titlebar_complete / model_2d_consistency）在 qc.json 中有结果（非"检查跳过"）

### Requirement: 比例尺幅面利用率评分
系统 SHALL 在 `pick_scale_with_layout` 中增加"幅面利用率"评分：视图总面积（4 视图 outline 面积之和） / 工作区面积（WORKAREA），优先选利用率 ≥ 40% 且无重叠的最大比例。

#### Scenario: 利用率达标
- **WHEN** bbox=(0.05, 0.05, 0.05)（小件）
- **THEN** 选 1:1 或 2:1（利用率 ≥ 40%），而非 1:5（利用率 < 10%）

#### Scenario: 利用率与无重叠冲突
- **WHEN** 某比例利用率 ≥ 40% 但视图重叠
- **THEN** 降档到下一档无重叠比例，并在 warnings 中记录"为避免重叠降档"

### Requirement: 标题栏字段智能填充
系统 SHALL 提供 `app/services/titlebar_filler.py`，按以下优先级填充标题栏字段：
1. UI 录入（titlebar_overrides，最高优先级）
2. 文件名解析（如 `LB26001-A-04-001` → 图号=LB26001-A-04-001、类别=A、序号=001）
3. 模板默认值（`config/titlebar_template.yaml`）
4. SLDPRT 自定义属性（最低优先级）

#### Scenario: 文件名解析
- **WHEN** 输入 `LB26001-A-04-001.SLDPRT` 且 SLDPRT 无"图号"属性
- **THEN** 图号填充为 `LB26001-A-04-001`，类别填充为 `A`，序号填充为 `001`

#### Scenario: UI 录入覆盖
- **WHEN** 用户在 titlebar_dialog 中输入品名="支架"，且 SLDPRT 无"品名"属性
- **THEN** 标题栏品名填充为"支架"，文件名解析和模板默认值被覆盖

### Requirement: 标题栏录入对话框
系统 SHALL 提供 `app/ui/titlebar_dialog.py`（PySide6 QDialog），用户可在出图前手动填写品名/图号/材质/数量/表面处理/类别/机型等字段。

#### Scenario: 用户录入
- **WHEN** 用户在 single_part_page 点击"开始出图"
- **THEN** 先弹出 titlebar_dialog，用户可填写或跳过；填写的内容作为 titlebar_overrides 传入 full_pipeline

### Requirement: 2D 图尺寸标注修复
系统 SHALL 在 `drw_generate_v6.py` 中改用 `Extension.InsertModelAnnotations3` 显式调用（替代 `RunCommand(826)`），并增加 `InsertDimension2` 兜底逐个插入关键尺寸。

#### Scenario: 尺寸标注成功
- **WHEN** 生成工程图
- **THEN** `dim_total ≥ 5`（DisplayDim 计数），`dim_count_sufficient` 检查通过

#### Scenario: InsertModelAnnotations3 失败兜底
- **WHEN** `InsertModelAnnotations3` 抛异常或返回 False
- **THEN** 调用 `InsertDimension2` 逐个插入前视图的 2 个水平尺寸 + 2 个垂直尺寸 + 1 个对角尺寸，确保 `dim_total ≥ 5`

### Requirement: PNG 直接导出修复
系统 SHALL 在 `drw_generate_v6.py` 中改用 SolidWorks COM 直接导出 PNG（`Extension.SaveAs` + `swExportPngData`），替代 PDF→PyMuPDF 链路。

#### Scenario: PNG 导出成功
- **WHEN** 生成工程图并保存
- **THEN** `<base>_v5.PNG` 文件存在且大小 ≥ 10KB，`png_missing` 不进入 hard_fail

#### Scenario: swExportPngData 不可用兜底
- **WHEN** `swExportPngData` 获取失败
- **THEN** 回退到 PDF→PyMuPDF 链路，并在 warnings 中记录"PNG 直接导出失败，回退 PDF 转换"

## MODIFIED Requirements

### Requirement: pick_scale_with_layout 返回值
v1.3 的 `pick_scale_with_layout` 返回 `(scale, outlines, [])`。v1.4 修改为 `(scale, outlines, [], utilization)`，其中 utilization 为 0.0-1.0 的浮点数，表示幅面利用率。调用方（`generate_for`）需适配第 4 个返回值。

### Requirement: full_pipeline 签名
v1.3 的 `full_pipeline(part_path, strategy)`。v1.4 修改为 `full_pipeline(part_path, strategy, titlebar_overrides=None)`，titlebar_overrides 为 dict，键为标题栏字段名（品名/图号/材质/数量/表面处理/类别/机型），值为用户录入的字符串。

### Requirement: drw_generate_v6.py 尺寸插入逻辑
v1.3 的尺寸插入逻辑为 `RunCommand(826)` + 二次 `RunCommand(826)`。v1.4 修改为 `Extension.InsertModelAnnotations3(0, 32, True, True, False, False)` 优先，失败时 `InsertDimension2` 兜底。

### Requirement: drw_generate_v6.py PNG 导出逻辑
v1.3 的 PNG 导出依赖外部 PDF→PyMuPDF 链路（在 run_manager 中）。v1.4 修改为在 `generate_for` 内部用 SolidWorks COM 直接导出 PNG，与 SLDDRW/PDF/DXF 同步保存。

## REMOVED Requirements
（无）
