# 制作 GB A4 .drwdot 模板根治模板级硬限制 Spec

## Why
harden-v5-and-vision-loop 已把 vision_score 从 15 提升到 35、quality_check 从 0/12 提升到 9/12，残余 3 项失败被识别为 SolidWorks 2025 模板级硬限制：(1) 默认字高 0.00025 m 在 SaveAs 后覆盖 runtime 设置；(2) `sheet.GetSize()` 返回 (None, None)；(3) 标题栏字段未绑定到 CustomProperty。这 3 项均无法通过运行时 API 解决，必须制作一份固化好图框 / 标题栏 / 字高 / 图层 / 第一角投影 / 13 个 CustomProperty 链接的 `gb_a4_landscape.drwdot` 模板，并让 v5 在 NewDocument 时使用它。

## What Changes
- 新增 `templates/gb_a4_landscape.drwdot`（仓库根新增 `templates/` 目录），通过 SolidWorks COM API 一次性脚本生成：
  - A4 横式 297×210 mm，启用第一角投影
  - 默认字高 5 mm（标题栏小字 3.5 mm）+ 字体「宋体 / Arial」
  - 5 图层（粗实 0.7、细实 0.35、虚线 0.35、点划 0.35、中心 0.25）
  - GB 图框（左 25 mm 装订 + 右 / 上 / 下 5 mm）
  - GB 标题栏 180×40 mm，5×3 网格，13 个字段全部用 `$PRP:"<key>"` 链接到 CustomProperty
  - sheet 尺寸预设 A4 (paper_size_code=6) 让 `sheet.GetSize()` 可读
- 新增脚本 `templates/build_drwdot.py`：用 SW COM API 自动从空白 SLDDRW 构造模板并 `SaveAs` 为 `.drwdot`
- 修改 `drw_generate_v5.py`：`NewDocument()` 优先使用 `templates/gb_a4_landscape.drwdot`，回退原 SW 内置模板
- 修改 `app/config/app.yaml.example` 与 `%APPDATA%/sw_drawing_studio/app.yaml`：`drwdot_template` 指向新模板
- 真实跑闭环：用新模板重跑 vision_loop，目标 `vision_score ≥ 80` 且 `quality_check ≥ 11/12`
- **BREAKING**：无（v5 在模板缺失时仍可回退）

## Impact
- Affected specs: `enforce-drawing-quality`、`harden-v5-and-vision-loop`、`build-3d-to-2d-desktop-app`
- Affected code:
  - 新增 `templates/gb_a4_landscape.drwdot`
  - 新增 `templates/build_drwdot.py`
  - 新增 `templates/probe_drwdot.py`（验证模板内容的探针脚本）
  - 修改 `.trae/specs/enforce-drawing-quality/drw_generate_v5.py`（NewDocument 用模板路径）
  - 修改 `app/config/defaults.py` 与 `config/app.yaml.example`（暴露 drwdot_template 字段）
  - 新增 `.trae/specs/craft-gb-drwdot-template/build_log.md` / `verify_log.md`

## ADDED Requirements

### Requirement: 模板构造脚本
系统 SHALL 提供 `templates/build_drwdot.py`，调用 SolidWorks COM API 一次性生成 `gb_a4_landscape.drwdot`，包含 A4 横式 / 5 mm 默认字高 / 5 图层 / GB 图框 / 13 字段标题栏。

#### Scenario: 自动构造
- **WHEN** 用户运行 `python templates/build_drwdot.py`
- **THEN** 在 `templates/` 下落地 `gb_a4_landscape.drwdot`，文件大小 > 50 KB

### Requirement: 模板探针验证
系统 SHALL 提供 `templates/probe_drwdot.py`，打开新模板并用 SolidWorks COM 验证：sheet 尺寸 A4、`GetUserPreferenceDoubleValue(89) ≥ 0.0035`、图层 ≥ 5、CustomProperty 链接 ≥ 13。

#### Scenario: 探针通过
- **WHEN** 运行 `python templates/probe_drwdot.py`
- **THEN** 输出 5 项验证结果，每项 `pass=True`

### Requirement: v5 使用新模板
系统 SHALL 在 `drw_generate_v5.NewDocument()` 中优先用 `templates/gb_a4_landscape.drwdot`，缺失时回退到默认行为，并在日志中注明用了哪个模板。

#### Scenario: 模板生效
- **WHEN** v5 运行结束
- **THEN** SLDDRW 中 `model.GetUserPreferenceDoubleValue(89)` 读到 ≥ 0.0035、`sheet.GetSize()` 返回非 None、标题栏 13 字段可见

### Requirement: 真实闭环达到 80 分
系统 SHALL 用新模板重跑 vision_loop，让 `vision_score ≥ 80` 且 `quality_check pass_count ≥ 11/12`。

#### Scenario: 真实通过
- **WHEN** 跑 `python .trae/specs/harden-v5-and-vision-loop/vision_loop.py LB26001-A-04-001.SLDPRT`
- **THEN** 退出码 0；`vision_loop_log.md` 末尾出现「PASS（template + harden-v5）」

### Requirement: 模板版本可追溯
系统 SHALL 在 `.trae/specs/craft-gb-drwdot-template/build_log.md` 记录模板构造耗时 / 文件大小 / 探针 5 项原文 / 闭环结果。

#### Scenario: 报告完整
- **WHEN** 全部任务结束
- **THEN** `build_log.md` 含 4 节（构造 / 探针 / v5 接入 / 闭环），有完整 vision_score JSON

## MODIFIED Requirements

### Requirement: drwdot_template 配置项（来自 build-3d-to-2d-desktop-app）
原默认空字符串。改为：默认指向仓库根 `templates/gb_a4_landscape.drwdot`（绝对路径）；GUI 设置对话框「路径」Tab 显示该字段。

## REMOVED Requirements
（无）
