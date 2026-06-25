# 图纸比例尺、信息栏与质检增强 Spec

## Why
v1.2 全量验证暴露 4 个系统性问题：(1) 比例尺不合理——CANDIDATE_SCALES 含非标准比例（3:1/1:3/1:4 违反 GB/T 14690），且只考虑"无重叠"不考虑"可读性"；(2) 信息栏不完整——仅 5×3 网格 13 个 Note，缺技术要求/工艺/公司/制图人/时间/源文件/交付信息，无模板录入；(3) 缺少 3D-2D 视觉比对——v1.2 的 vision_score_with_reference 只对比"生成图 vs 案例图"，未对比"源 3D 模型 vs 生成 2D 图"；(4) 质检不完善——12 项 QC 无比例尺合理性检查、无信息栏完整性检查、无 3D-2D 一致性检查。

## What Changes
- 修正 `drw_generate_v6.py` 的 CANDIDATE_SCALES 为 GB/T 14690 标准比例（5:1/2:1/1:1/1:2/1:5/1:10/1:20/1:50），移除 3:1/1:3/1:4。
- 新增 `app/services/scale_advisor.py`：用 LLM 视觉模型辅助判断比例是否合适（看生成图 PNG 后给出"比例是否合理 + 建议"）。
- 扩展 `drw_generate_v6.py` 的标题栏为完整表格（7 行 × 4 列），新增字段：技术要求/工艺信息/公司信息/制图人/审核/日期/源文件/交付信息。
- 新增 `config/titlebar_template.yaml`：用户可配置公司名/制图人/审核人等模板字段。
- 新增 `app/services/model_compare.py`：渲染 3D 模型等轴测视图 PNG，与 2D 工程图 PNG 一起送 LLM 比对，输出 `model_2d_diff`。
- 增强 `drw_quality_check.py`：新增 3 项 QC 检查（scale_gb_standard / titlebar_complete / model_2d_consistency）。
- **BREAKING**：CANDIDATE_SCALES 移除非标准比例，可能导致之前用 3:1 的件改用 2:1 或 1:1。

## Impact
- Affected specs: `build-v6-and-validate-exe-ui`（drw_generate_v6.py 比例+标题栏）、`enforce-drawing-quality`（drw_quality_check.py 新增 3 项）、`validate-real-drawings-with-llm-vision`（vision 对比扩展）
- Affected code:
  - `.trae/specs/build-v6-and-validate-exe-ui/drw_generate_v6.py`（CANDIDATE_SCALES + 标题栏扩展）
  - `.trae/specs/enforce-drawing-quality/drw_quality_check.py`（新增 3 项 QC）
  - `app/services/scale_advisor.py`（**新增**）
  - `app/services/model_compare.py`（**新增**）
  - `config/titlebar_template.yaml`（**新增**）
  - `app/services/__init__.py`（导出新模块）

## ADDED Requirements

### Requirement: GB 标准比例尺选择
系统 SHALL 只使用 GB/T 14690 标准比例（5:1 / 2:1 / 1:1 / 1:2 / 1:5 / 1:10 / 1:20 / 1:50），移除非标准比例（3:1 / 1:3 / 1:4）。

#### Scenario: 比例选择
- **WHEN** `pick_scale_with_layout(bbox_m)` 被调用
- **THEN** 只从 `[(5,1),(2,1),(1,1),(1,2),(1,5),(1,10),(1,20),(1,50)]` 中选取，不返回 3:1/1:3/1:4

### Requirement: 视觉模型辅助比例判断
系统 SHALL 提供 `advise_scale(png_path, current_scale, llm)` 函数，用 LLM 视觉模型看生成图 PNG 后判断比例是否合理。

#### Scenario: 比例合理
- **WHEN** 输入生成图 PNG + 当前比例 1:2
- **THEN** LLM 返回 `{reasonable: true, suggestion: "", score: 80-100}`

#### Scenario: 比例不合理
- **WHEN** 输入生成图 PNG + 当前比例 1:50（视图太小）
- **THEN** LLM 返回 `{reasonable: false, suggestion: "建议放大到 1:10 或 1:5", score: 30-60}`

### Requirement: 完整标题栏表格
系统 SHALL 把标题栏扩展为 7 行 × 4 列表格，含以下字段：
- 第 1 行：公司名 / 品名 / 图号 / 比例
- 第 2 行：制图人 / 审核人 / 日期 / 机型
- 第 3 行：材质 / 数量 / 表面处理 / 类别
- 第 4 行：技术要求（跨 4 列，多行）
- 第 5 行：工艺信息（跨 4 列）
- 第 6 行：源文件信息（SLDPRT 路径 + 版本）
- 第 7 行：交付信息（交付日期 + 客户 + 备注）

#### Scenario: 标题栏渲染
- **WHEN** 生成工程图
- **THEN** 标题栏含 7 行 × 4 列表格线，所有字段有对应 Note 或 $PRP 链接

### Requirement: 标题栏模板录入
系统 SHALL 提供 `config/titlebar_template.yaml`，用户可配置公司名/制图人/审核人等默认值。

#### Scenario: 模板加载
- **WHEN** 出图时读取 `titlebar_template.yaml`
- **THEN** 公司名/制图人/审核人等字段从模板填充，SLDPRT 属性覆盖模板默认值

### Requirement: 3D-2D 视觉比对
系统 SHALL 提供 `compare_model_2d(part_path, slddrw_png_path, llm)` 函数，渲染 3D 模型等轴测视图 PNG，与 2D 工程图 PNG 一起送 LLM 比对。

#### Scenario: 3D-2D 比对
- **WHEN** 输入 SLDPRT 路径 + 2D 工程图 PNG
- **THEN** 渲染 3D 等轴测 PNG，LLM 同时接收 2 张图，返回 `{consistency: 0-100, missing_views: list, structural_diff: str}`

### Requirement: 质检增强 3 项
系统 SHALL 在 `drw_quality_check.py` 新增 3 项 QC 检查：
1. `scale_gb_standard`：比例是否为 GB/T 14690 标准值
2. `titlebar_complete`：标题栏 7 行字段是否完整
3. `model_2d_consistency`：3D-2D 视觉一致性（调 `compare_model_2d`）

#### Scenario: 比例非标准
- **WHEN** 生成图比例为 1:3
- **THEN** `scale_gb_standard` 检查返回 `pass=false, severity=warning, reason="1:3 非GB/T 14690标准比例"`

#### Scenario: 标题栏字段缺失
- **WHEN** 标题栏"公司名"字段为空
- **THEN** `titlebar_complete` 检查返回 `pass=false, severity=warning, reason="字段[公司名]为空"`

## MODIFIED Requirements

### Requirement: CANDIDATE_SCALES
v1.1 的 `CANDIDATE_SCALES = [(5,1),(3,1),(2,1),(1,1),(1,2),(1,3),(1,4),(1,5),(1,10),(1,20),(1,50),(1,100)]`。v1.3 修改为 `[(5,1),(2,1),(1,1),(1,2),(1,5),(1,10),(1,20),(1,50)]`，移除 3:1/1:3/1:4/1:100。

### Requirement: 标题栏布局
v1.1 的标题栏为 5 列 × 3 行（13 个 Note）。v1.3 扩展为 7 行 × 4 列（含技术要求/工艺/源文件/交付信息行）。

## REMOVED Requirements
（无）
