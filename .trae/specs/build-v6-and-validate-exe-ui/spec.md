# 构建 v6 出图器 + EXE UI 全面验收 Spec

## Why
extend-libs-and-fix-residuals 把 vision_score 锁在 55、qc_pass 锁在 11/12，残余主要是 v5 视图布局与拉模型项的能力局限（前视图被压扁、二次模型项未触发、refdoc 解除）。同时距离首次打包 EXE 已经过去多次后端代码 / GUI 改动（增加了 BOM 与核价页、bom_pricing_page、模板路径变更），需要重新打包并人工模拟点击每一项 UI 按钮，确认文字、布局、按钮回调、错误提示均无回归。

## What Changes
### 1. 出图器 v6（在 v5 基础上新增）
- 新增 `.trae/specs/build-v6-and-validate-exe-ui/drw_generate_v6.py`，复制 v5 主流程，做 3 处升级：
  - **重写视图布局**：4 视图按 GB 第一角投影 T 字布局（前 / 俯 / 左 / 等轴测），主视图固定 (0.080, 0.140) m，自动计算 outline 后 padding 5mm 间距，遇重叠则降比例直至 ≤ 1:50；视图标签禁用
  - **二次拉模型项**：第一次 `RunCommand(826)` 后 sleep 1.0s + `ForceRebuild3` + 再次 `RunCommand(826)`，让 Auto-Insert Dimensions 从模型尺寸增量拉出更多 DisplayDim
  - **缓存 cfg_name**：在 `_inject_default_custom_properties` 之后立即缓存 `_cached_cfg_name = part.GetActiveConfiguration().Name`，所有视图 `SetReferencedConfiguration` 用这个缓存值，避免 part 关闭后取空
- 新增 `.trae/specs/build-v6-and-validate-exe-ui/drw_qc_loop_v6.py`：调用 v6 替代 v5（保持 QC 闭环原状）
- 新增 `templates/macros/auto_section.swp`（用 SW VBA IDE 编译；附 `precompile_swp.py` 自动化）：v6 优先用 .swp，缺失则回退到 v5 的 .bas 路径

### 2. UI 全面验收 + 重新打包
- 重新跑 `pyinstaller --noconfirm build_exe.spec`，把最新 GUI（含 BOM 与核价页、6 项导航）打包为 `dist/sw_drawing_studio.exe`
- 启动 EXE，**逐项点击 6 项导航 + 工具栏 + 设置对话框 + BOM 页所有按钮 + 质检页所有按钮**，每项截图 + 检查：
  - 显示文字是否正确（无错别字、无 placeholder 残留）
  - 按钮回调是否触发（无 `_on_xxx not implemented` 报错）
  - 表格 / Splitter / Dock 布局是否正常
  - 错误对话框是否在异常输入下出现（不静默崩溃）
- 将所有截图与回归发现整理到 `ui_acceptance.md`

### 3. 真实闭环 v6
- 用 v6 重跑 vision_loop（≤ 2 轮），目标：vision_score ≥ 60、qc_pass = 11/12 不退化、refdoc_correct ≥ 1 视图非空（cfg_name 缓存生效）

### BREAKING
- 无（v5 保留；v6 是平行新增器）

## Impact
- Affected specs: `enforce-drawing-quality`、`harden-v5-and-vision-loop`、`craft-gb-drwdot-template`、`extend-libs-and-fix-residuals`、`build-3d-to-2d-desktop-app`
- Affected code:
  - 新增 `.trae/specs/build-v6-and-validate-exe-ui/drw_generate_v6.py`、`drw_qc_loop_v6.py`、`run_log_v6.md`、`ui_acceptance.md`
  - 新增 `templates/macros/precompile_swp.py`、`templates/macros/auto_section.swp`（产物）
  - 修改 `app/services/sw_runner.py`：`run_single` 改为优先调 v6 的 qc_loop，缺失时回退 v5
  - 重新打包 `dist/sw_drawing_studio.exe`
  - 新增 `.trae/specs/build-v6-and-validate-exe-ui/screenshots/` 6+ 张图

## ADDED Requirements

### Requirement: v6 视图布局
系统 SHALL 在 v6 中按 GB T 字第一角投影布局 4 视图，主视图固定 (0.080, 0.140) m，俯视图正下方、左视图正右、等轴测右上；任意 outline 矩形不重叠。

#### Scenario: 4 视图无重叠
- **WHEN** v6 跑完 quality_check
- **THEN** view_overlap pass=True、view_in_frame pass=True

### Requirement: 二次拉模型项
系统 SHALL 在 v6 中调 `RunCommand(826)` 两次（中间 ForceRebuild3 + sleep 1s），目标 DisplayDim ≥ 5。

#### Scenario: 标注数量
- **WHEN** quality_check 跑出 dim_count_sufficient
- **THEN** dim_total ≥ 5 且 pass=True

### Requirement: cfg_name 缓存
系统 SHALL 在 v6 中 part 打开后立即缓存 `_cached_cfg_name`，所有 `SetReferencedConfiguration` 调用使用缓存值。

#### Scenario: refdoc 部分非空
- **WHEN** v6 SaveAs 后 quality_check 跑 refdoc_correct
- **THEN** ≥ 1 个视图的 ReferencedConfiguration 非空（即 bad_ref 数量 < 4）

### Requirement: VBA .swp 提前编译
系统 SHALL 提供 `templates/macros/precompile_swp.py`，自动用 RunMacro2 把 .bas 编译成 .swp，落地 `templates/macros/auto_section.swp`；若 SW 自动编译失败，给出手动指引并跳过（不阻塞主流程）。

#### Scenario: .swp 就绪
- **WHEN** 跑 `python templates/macros/precompile_swp.py`
- **THEN** `templates/macros/auto_section.swp` 存在或脚本退出码 1 + 明确提示

### Requirement: EXE UI 全面验收
系统 SHALL 重新打包 EXE 后启动，逐项验证 6 项导航（首页 / 批量出图 / AI 质检 / BOM 与核价 / 设置 / 日志）+ 工具栏按钮 + BOM 页 4 按钮 + 质检页 3 按钮 + 设置对话框 3 Tab，所有按钮可点、无报错、无文字错位。

#### Scenario: 截图归档
- **WHEN** 验收结束
- **THEN** `screenshots/` 至少 6 张 + `ui_acceptance.md` 列出每项「点击 / 期望 / 实测 / 截图引用」

### Requirement: v6 真实闭环
系统 SHALL 用 v6 跑 vision_loop ≤ 2 轮，达到 vision_score ≥ 60 且 qc_pass ≥ 11/12 不退化，最佳产物记录到 `run_log_v6.md`。

#### Scenario: v6 闭环达标
- **WHEN** 闭环结束
- **THEN** `run_log_v6.md` 末尾给出"PASS（vision_score ≥ 60）" 或 "已知限制 + 残余 issues"

## MODIFIED Requirements

### Requirement: sw_runner.run_single（来自 build-3d-to-2d-desktop-app）
原默认调 `drw_qc_loop.py`（v5）。改为：优先调 `drw_qc_loop_v6.py`，缺失时回退 v5；环境变量 `USE_V5=1` 强制走 v5。

## REMOVED Requirements
（无）
