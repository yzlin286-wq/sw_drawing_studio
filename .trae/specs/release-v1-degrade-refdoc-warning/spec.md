# 发布 v1.0 + refdoc 降级为 warning Spec

## Why
v6 出图、QC（11/12）、vision_score（65/100）、EXE、UI、BOM、LLM 链路均已达可交付状态，唯一未闭环的 `refdoc_correct` 是 SolidWorks 2025 + pywin32 持久化层硬限制，已经把 4 级 cfg 缓存、SetReferencedConfiguration、ReplaceViewModel 都验证过，不再属于业务代码可解决范围。继续把它当成上线阻断项会让产品永远无法发布。本 spec 落地"生产可用 v1.0"：把 refdoc_correct 降级为 warning，明确 9 项 hard_fail + 5 项 warning 的分层验收标准，新增 `drawing_usable` 顶层字段；UI 增加环境自检 + 分层状态展示；重新打包并真实闭环验证 v1.0 可发布。

## What Changes
### 1. QC 双轨制（核心）
- `drw_quality_check.py` 输出新增顶层字段：
  - `hard_fail`（list[str]）：列出命中的 9 项硬阻断条件（SW 不连接 / OpenDoc6 失败 / 文件未生成 / view_overlap=false / view_in_frame=false / dim_total<5 / qc_pass<10/12 / vision_score<60，以及 SLDDRW/PDF/DXF 任一缺失）
  - `warnings`（list[str]）：列出命中的 5 项警告（refdoc_correct=false / has_datum_a=false / has_ra_note=false / gb_titlebar_complete=false / section_view skipped）
  - `drawing_usable`（dict）：`{"pass": bool, "criteria": {...}}` 顶层交付门槛字段，与 `hard_fail` 对应
- `refdoc_correct` 内部新增 `severity: "warning"` + `reason: "SW2025 SaveAs 后 ReferencedDocument 未持久化"`
- 抽 `classify_refdoc_status(ref_path, expected_part)` 工具函数（spec 文档已写出）

### 2. 环境自检模块
- 新增 `app/services/health_check.py`：函数 `run_health_check() -> dict`，检查 7 项：
  1. SW 进程 / RevisionNumber
  2. 模板 `templates/gb_a4_landscape.DRWDOT` 存在
  3. 宏 `auto_section.bas` / `.swp` 存在
  4. 输出目录可写
  5. LLM 配置可解析 + 可联通（`test_connection()`）
  6. 标准件 / 工艺 / 报价数据库存在
  7. v6 / v5 出图脚本路径可用

### 3. UI 分层状态
- `app/ui/home_page.py` 增加"环境自检"状态卡，启动时自动跑 `run_health_check()` 显示 7 项绿/红
- `app/ui/batch_page.py` 表格新列「状态」展示 `success / warning / fail`，warning 时悬浮提示 warnings 列表
- `app/ui/qc_page.py` 顶部状态条改为分层（出图: ✓ / 质量: ✓ 11/12 / 视觉: ✓ 65 / 可交付: ✓ / 警告: 1）

### 4. 出图模式标签化
- 主窗口工具栏增加下拉框「出图策略」：默认 = v6 推荐；可选 v5 兼容、v6 调试（输出完整日志）
- 选 v5 兼容时设置 `os.environ["USE_V5"] = "1"`，由 sw_runner 已有逻辑路由

### 5. 重新打包 v1.0
- `pyinstaller --noconfirm build_exe.spec` 重打 dist/sw_drawing_studio.exe
- smoke 启动 + 截图覆盖新加的环境自检卡

### 6. 真实闭环 v1.0 验证
- 跑 v6 闭环 1 轮，验证 drawing_usable=True 时 hard_fail=[]，warnings 含 refdoc_correct
- 写 `release_log.md` 含 4 节（QC 双轨 / 环境自检 / UI 分层 / 阶段对比 + v1.0 发布判定）

### BREAKING
- 无（所有改动均纯增量 + 兼容字段；旧调用者读 `score_pass_count` / `pass` 仍然可用）

## Impact
- Affected specs: `enforce-drawing-quality`、`build-v6-and-validate-exe-ui`、`fix-refdoc-via-qc-and-paths`、`build-3d-to-2d-desktop-app`、`extend-libs-and-fix-residuals`
- Affected code:
  - 修改 `.trae/specs/enforce-drawing-quality/drw_quality_check.py`（QC 双轨字段 + classify_refdoc_status）
  - 新增 `app/services/health_check.py`
  - 修改 `app/services/__init__.py` 导出 `run_health_check`
  - 修改 `app/ui/home_page.py`（环境自检状态卡）
  - 修改 `app/ui/batch_page.py`（状态列）
  - 修改 `app/ui/qc_page.py`（顶部分层状态条）
  - 修改 `app/ui/main_window.py`（出图策略下拉框）
  - 重打 `dist/sw_drawing_studio.exe`
  - 新增 `.trae/specs/release-v1-degrade-refdoc-warning/release_log.md`

## ADDED Requirements

### Requirement: QC 双轨字段
系统 SHALL 在 `quality_check()` 输出中新增 `hard_fail`、`warnings`、`drawing_usable` 三项顶层字段，分别对应 9 项硬阻断、5 项警告、顶层交付门槛。

#### Scenario: refdoc 失败但 drawing 可交付
- **WHEN** v6 跑出 SLDDRW + PDF + DXF + view_overlap=true + view_in_frame=true + dim_total=44 + qc_pass=11/12 + vision_score=65 + bad_ref=4/4
- **THEN** `hard_fail = []`、`warnings ⊃ ["refdoc_correct"]`、`drawing_usable.pass = True`

### Requirement: classify_refdoc_status
系统 SHALL 提供 `classify_refdoc_status(ref_path, expected_part) -> {pass, severity, message}`，按 spec 中给出的 3 分支逻辑分类。

#### Scenario: 路径匹配
- **WHEN** ref_path 与 expected_part 同名（lowercase）
- **THEN** 返回 `{pass: True, severity: "ok", message: "视图引用模型路径匹配"}`

#### Scenario: 路径为空
- **WHEN** ref_path 为空字符串
- **THEN** 返回 `{pass: False, severity: "warning", message: "SolidWorks API 未返回视图引用文档；不阻断图纸导出"}`

### Requirement: 环境自检
系统 SHALL 提供 `app/services/health_check.run_health_check() -> dict`，输出 7 项 ok/fail 状态。

#### Scenario: 启动时自检
- **WHEN** GUI 启动加载首页
- **THEN** 调 `run_health_check()` 返回 `{"sw": {ok, msg}, "template": {...}, "macro": {...}, "output_dir": {...}, "llm": {...}, "db": {...}, "generator": {...}}`，UI 渲染 7 张子卡

### Requirement: UI 分层状态展示
系统 SHALL 在主窗口质检页顶部展示分层状态条："出图: ✓ / 质量: 11/12 / 视觉: 65 / 可交付: ✓ / 警告: N"，warning 个数 > 0 时显示橙色徽章。

#### Scenario: 警告显示
- **WHEN** drawing_usable=True 且 warnings=["refdoc_correct"]
- **THEN** 状态条最右侧显示「警告: 1」，鼠标悬浮显示 warning 详情

### Requirement: 出图策略下拉框
系统 SHALL 在主窗口工具栏增加 QComboBox「出图策略」，提供 3 选项：v6 推荐 / v5 兼容 / v6 调试；切换 v5 时设置 `USE_V5=1` 环境变量。

#### Scenario: 切换兼容模式
- **WHEN** 用户选「v5 兼容」并触发出图
- **THEN** sw_runner 日志输出 `[runner] using v5 fallback`

### Requirement: v1.0 真实闭环
系统 SHALL 跑一次 v6 真实闭环，确认 drawing_usable=True 且 hard_fail=[]；记录到 `release_log.md`。

#### Scenario: 发布判定
- **WHEN** 闭环结束
- **THEN** `release_log.md` 末尾给出"v1.0 发布判定: PASS（drawing_usable=True, hard_fail=[]）"

## MODIFIED Requirements

### Requirement: refdoc_correct 严重等级（来自 fix-refdoc-via-qc-and-paths）
原作为 12 项 QC 之一，pass=false 时拉低 `score_pass_count`。改为：保留 `pass` 字段以保持向后兼容，但同时新增 `severity` 字段（默认 "warning"）；`hard_fail` 不再包含此项；UI 与发布判定均参考 `severity`。

## REMOVED Requirements
（无）
