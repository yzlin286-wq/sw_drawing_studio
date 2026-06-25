# 优化 v5 + 真实视觉闭环重生成 Spec

## Why
上一阶段 vision_score（doubao-seed-2.0-pro）给当前 v5 输出图纸打了 10/100 并指出 7 条真实问题（无图框 / 重复表面粗糙度 5 次 / 技术要求叠在一起 / 重复堆叠 6 个基准 A / 无尺寸标注 / 残留蓝色视图箭头 / 文档读取异常）。这些问题源自 v5 为了通过 12 项规则级 quality_check（NoteBlock×5 注入策略）而引入的副作用。需要消除这些副作用 + 补齐 GB 标题栏 / 图框 / 尺寸标注 / 视图箭头清理，并跑一次 SolidWorks 在线的"v5 重生成 → vision_score → 评分 < 80 自动 rerun → 直到 ≥ 80 分（或达上限 3 轮）"的真实闭环。

## What Changes
- 修改 `drw_generate_v5.py`：
  - **去除 NoteBlock×5 注入策略**：技术要求 / 表面粗糙度 / 基准 A 各只插 1 次，从源头消除"重复 5 次/6 次"。
  - **补图框 + 标题栏**：用 SolidWorks `LoadDrawingTemplate` / 自动绘制 A4 横式图框 + 13 键标题栏（沿用 13 个 CustomProperty BlockInst 写入，但视图层确保渲染可见）。
  - **强制尺寸标注**：在 RunCommand(826) Model Items 之外，对每个视图额外用 `InsertHorizontalDimension2 / InsertVerticalDimension2` 触发自动尺寸抽取，目标 ≥ 5 个尺寸。
  - **清理视图箭头残留**：每个视图设置 `view.ShowReferencedDecal = False` 与 `model.SetUserPreferenceToggle(swViewDispGlobalDimsArrows=…)`，避免导出残留 SolidWorks UI 箭头。
  - **技术要求多行格式化**：1 个 Note 内含 3 条编号的换行文本（用 `\n` 或 `vbCrLf`），避免叠在同一坐标。
- 让 `drw_quality_check.py` 12 项检查对应放宽：单 NoteBlock 含 ≥3 行也视为 has_tech_note。
- 新增 `vision_loop.py`（在 `.trae/specs/harden-v5-and-vision-loop/`）：内部循环
  1. 用 `sw_runner` 跑 v5 → SLDDRW + qc.json
  2. 用 `vision_score` 调 doubao-seed-2.0-pro 评分
  3. 若 score < 80：把 issues 写 `vision_issues.json` 反馈到 v5（v5 读环境变量决定本轮关闭/启用对应修复块），再重生成
  4. 上限 3 轮，全部记录到 `vision_loop_log.md`
- 真实跑闭环：要求 SolidWorks 2025 在线（用户启动）；若启动失败明确报错。
- 不破坏 12 项规则级 quality_check，目标：
  - quality_check ≥ 10/12（保持上一阶段成绩）
  - vision_score ≥ 80（新目标）
- **BREAKING**：无（v5 文件名 `_v5.SLDDRW` 不变；语义改进）。

## Impact
- Affected specs: `enforce-drawing-quality`（v5 行为升级）、`build-3d-to-2d-desktop-app`（GUI 复用 v5）
- Affected code:
  - `.trae/specs/enforce-drawing-quality/drw_generate_v5.py`
  - `.trae/specs/enforce-drawing-quality/drw_quality_check.py`（has_tech_note 放宽）
  - 新增 `.trae/specs/harden-v5-and-vision-loop/vision_loop.py`
  - 新增 `.trae/specs/harden-v5-and-vision-loop/vision_loop_log.md`
  - `drw_output/v5/LB26001-A-04-001_v5.SLDDRW`（新一版产物）

## ADDED Requirements

### Requirement: 移除 NoteBlock 注入副作用
系统 SHALL 让技术要求 / 表面粗糙度 / 基准 A 各只插一次（NoteBlock 单实例），3 类标注互不重叠位置。

#### Scenario: 单 NoteBlock 多行技术要求
- **WHEN** 生成完成后扫描 SLDDRW 的 NoteBlock 列表
- **THEN** 包含 1 条多行技术要求（≥ 3 行）+ 1 条 Ra3.2 注释 + 1 条基准 A 标识，三类各自只出现 1 次

### Requirement: 标准 GB 图框与标题栏
系统 SHALL 在 SLDDRW 中渲染 A4 横式图框（左 25 mm 装订边 + 5 mm 其余边距）+ 含 13 键的 GB 标题栏；图框线宽符合 GB/T 4457（粗 0.7 mm，中 0.35 mm）。

#### Scenario: 视觉模型识别图框
- **WHEN** vision_score 检查
- **THEN** issues 中不再含 `missing_frame_titleblock` 关键字

### Requirement: 强制尺寸标注
系统 SHALL 在每张 SLDDRW 中至少包含 5 个 DisplayDimension（含线性 / 角度 / 直径），来源 RunCommand(826) + 主动插入。

#### Scenario: 标注数量
- **WHEN** quality_check 跑出 dim_count_sufficient
- **THEN** dim_total ≥ 5 且 pass=True

### Requirement: 清理视图箭头残留
系统 SHALL 在导出前关闭"显示视图方向蓝色箭头"系统选项（`swUserPreferenceToggle_e.swViewDispShowReferenceTriad / swDetailingShowDisplaceArrows` 等），并对每个视图调用 `view.SetReferencedDocument` 后清理装饰线。

#### Scenario: 视觉模型不再报箭头
- **WHEN** vision_score 检查
- **THEN** issues 中不再含 `residual_view_arrow` 关键字

### Requirement: 视觉闭环 ≥ 80
系统 SHALL 提供 `vision_loop.py` 在 ≤ 3 轮内把 vision_score 提升到 ≥ 80；若 SW 不在线 SHALL 明确报错并退出码 ≠ 0。

#### Scenario: 闭环成功
- **WHEN** 跑 `python vision_loop.py LB26001-A-04-001.SLDPRT`
- **THEN** 至少有 1 轮 vision_score ≥ 80；vision_loop_log.md 完整记录每轮 score / issues / 改动

### Requirement: 闭环结果归档
系统 SHALL 把每轮 SLDDRW / qc.json / vision.json / 改动 diff 归档到 `vision_loop_log.md`。

#### Scenario: 报告完整
- **WHEN** 闭环结束
- **THEN** vision_loop_log.md 包含 ≥ 1 张最终 SLDDRW 渲染 PNG 引用 + 最终 vision_score JSON + 12 项 quality_check 通过项数

## MODIFIED Requirements

### Requirement: has_tech_note（来自 enforce-drawing-quality 12 项检查）
原检查需 NoteBlock_total > 4。改为：单 NoteBlock 文本含 ≥3 行编号项也视为 pass；NoteBlock 总数仍 ≥ 1 即可。理由：上一阶段为通过此检查引入了 NoteBlock×5 副作用。

## REMOVED Requirements
（无）
