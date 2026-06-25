# v1.1 功能完整性增强 + 真实交付闭环 Spec

## Why
v1.0 已通过 hard_fail=[] / drawing_usable=True / qc_pass=11/12 / vision_score=65 的发布判定，但产物分散在多目录、缺乏 run_id 可追溯、健康自检只有 7 项、UI 七页未补全、诊断包未实现、refdoc 强修接口未预留。用户视角的"完整可交付"还差最后一公里：把所有 run 产物归集到 `drw_output/runs/<run_id>/`，扩 12 项健康自检，补全 UI 七页 smoke + 截图，落 diagnostics zip 与 refdoc_relink_service 接口，重新打包并真实闭环。

## What Changes

### 1. 统一运行会话 run_id（Task 1）
- 新增 `app/services/run_manager.py`：`new_run() -> RunContext`，含 run_id（uuid4 短码）/ started_at / app_version / sw_revision / strategy / 子目录工厂
- 产物目录结构：`drw_output/runs/<run_id>/{input,drawing,qc,bom,quote,logs}` + `manifest.json`
- 支持 `RunContext.write_manifest()`、`RunContext.add_output_file(category, path)`

### 2. 健康自检 12 项（Task 2）
- `app/services/health_check.py` 扩展为 12 项；返回 `{all_ok, pass, warning, fail, items: [...]}`
- 每 item 含 `key, status (pass/warning/fail), msg, fix`
- 新增 5 项：sw_revision_supported / template_size_ok / chinese_path_support / v5_fallback_present / db_readable

### 3. SolidWorks 制图链路（Task 3）
- 复用 v6 + v5 fallback；强化 sw_runner 路径绝对化；写 `<run_id>/logs/sw.log`
- v6 失败时 fallback_used=true 写入 manifest

### 4. QC + diagnostics（Task 4）
- `drw_quality_check.py` 输出新增 `diagnostics: {sw_revision, refdoc_strategy, replace_view_model_result, cfg_name}`
- hard_fail 与 warnings 列表与 spec 文中规定 11 项 / 8 项严格对齐
- refdoc_correct 强制 severity=warning 不进 hard_fail

### 5. vision_score + fix_suggestion（Task 5）
- `app/services/vision_qc.py` 输出 `vision.json`：含 score / pass / threshold / issues[].fix_suggestion / image_path / model
- 4 类典型 warning 给出明确 fix_suggestion 文本

### 6. BOM / 工艺 / 报价交付（Task 6）
- 单件出图后自动调 `extract_bom + suggest_route + calculate_quote`
- 6 个产物（bom.json/.xlsx + process_route.json/.xlsx + quote.json/.xlsx）写入 `<run_id>/bom/` 和 `<run_id>/quote/`

### 7. UI 七页（Task 7）
- 首页 12 项卡 + 最近 5 次 run + 打开输出目录
- 单件页（新增）+ 批量页（增强）+ 质检页 + BOM 页 + 设置页 + 日志页
- 每页 EXE 中 smoke 截图 ≥ 30KB

### 8. 诊断包 zip（Task 8）
- `app/services/diagnostics.py`：`build_diagnostics_zip(run_id) -> Path`
- 含 manifest / qc / vision / logs / health / screenshots / version.txt

### 9. refdoc_relink_service 接口（Task 9）
- `app/services/refdoc_relink_service.py`：`relink_refdoc(drawing_path, part_path, view_names, strategy="auto") -> dict`
- 5 策略 stub（pywin32_late 实现，其他 3 个返回 not_implemented），结果进 diagnostics
- 默认关闭，不阻断交付

### 10. 重打 EXE + release_log_v1_1.md（Task 10）
- build_exe.spec 加 health_check / refdoc_relink_service / diagnostics / run_manager
- pyinstaller 重打；smoke alive ≥ 6s；首页截图覆盖 12 项卡
- 真实闭环 + release_log_v1_1.md（14 节 + 发布判定）

### BREAKING
- 无（产物从 `drw_output/v5/` 迁到 `drw_output/runs/<run_id>/` 但原路径仍兼容；旧 manifest/qc/vision 字段保留）

## Impact
- Affected specs: 全部前序 spec（保持向后兼容）
- Affected code: 8 个 app/services 文件 + 7 个 app/ui 文件 + build_exe.spec + drw_quality_check + drw_qc_loop_v6 + drw_generate_v6
- 新增产物: `.trae/specs/enhance-v1-1-complete-deliverable/release_log_v1_1.md`、`drw_output/runs/<run_id>/`、`diagnostics_<run_id>.zip`

## ADDED Requirements

### Requirement: run_id 统一会话
系统 SHALL 在每次单件/批量出图开始时生成 run_id，并把所有产物归集到 `drw_output/runs/<run_id>/{input,drawing,qc,bom,quote,logs}` 子目录，写 manifest.json。

#### Scenario: 单件 run
- **WHEN** 调用 `run_manager.new_run()` + 完整闭环
- **THEN** `drw_output/runs/<run_id>/manifest.json` 存在，含 run_id / started_at / sw_revision / output_files / hard_fail / drawing_usable

### Requirement: 健康自检 12 项
系统 SHALL 在 health_check 返回 12 项，每项含 key / status / msg / fix。

#### Scenario: 启动调用
- **WHEN** UI 启动 → run_health_check()
- **THEN** 返回 `{all_ok, pass, warning, fail, items: [{key, status, msg, fix}, x12]}`

### Requirement: QC diagnostics
系统 SHALL 在 qc.json 增加 `diagnostics` 字段含 4 子项；hard_fail 仅含 12 项白名单；refdoc_correct 不进 hard_fail。

#### Scenario: 真实闭环
- **WHEN** v6 跑完
- **THEN** qc.json 同时含 hard_fail / warnings / drawing_usable / diagnostics

### Requirement: vision.json fix_suggestion
系统 SHALL 在 vision.json issues 内每项含 fix_suggestion 文本。

#### Scenario: 标题栏不全
- **WHEN** issues 含 gb_titlebar_complete=false
- **THEN** fix_suggestion 含具体缺失字段名提示

### Requirement: BOM / 报价完整交付
系统 SHALL 单件 run 完成后自动生成 6 个产物（json + xlsx 各 3）。

#### Scenario: 缺失数据
- **WHEN** 部分字段缺失
- **THEN** quote.json 包含 assumptions 列表，warnings 中加 `bom_partial` 等，但不阻断 drawing_usable

### Requirement: UI 七页 smoke
系统 SHALL EXE 启动后能切换 7 页（首页/单件/批量/质检/BOM/设置/日志），每页截图 ≥ 30KB。

#### Scenario: 截图齐全
- **WHEN** 验收完成
- **THEN** screenshots/ 目录含 7 张 PNG，全部 ≥ 30KB

### Requirement: 诊断包 zip
系统 SHALL 提供 `build_diagnostics_zip(run_id)`，输出 `diagnostics_<run_id>.zip` 含 9 项。

#### Scenario: 用户报错
- **WHEN** 调 diagnostics
- **THEN** zip 含 manifest / qc / vision / run.log / sw.log / exceptions.log / health_check.json / screenshots / version.txt

### Requirement: refdoc_relink_service 接口
系统 SHALL 提供 5 策略接口；默认 strategy=auto；失败不阻断交付；结果进 diagnostics。

#### Scenario: 实验性调用
- **WHEN** 设置中开启实验性 + 调 relink_refdoc(...)
- **THEN** 返回 `{ok, strategy_used, attempts, name_match_count, ref_present_count, bad_ref_count, severity}`

### Requirement: v1.1 真实闭环 + 发布判定
系统 SHALL 跑完整闭环，写 `release_log_v1_1.md`，末尾给出发布判定。

#### Scenario: PASS
- **WHEN** hard_fail=[] + drawing_usable.pass=True + 7 页截图 ≥ 30KB + EXE alive
- **THEN** 末尾 `v1.1 发布判定: PASS`

## MODIFIED Requirements

### Requirement: 产物路径（来自 v1.0）
原 `drw_output/v5/<base>_v5.*`。改为：v1.1 默认 `drw_output/runs/<run_id>/drawing/<base>_v5.*`，但 v6/v5 出图器仍可向旧路径输出（向后兼容），run_manager 在闭环结束时复制/移动到 run 目录。

## REMOVED Requirements
（无）
