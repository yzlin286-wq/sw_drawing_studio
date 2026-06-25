# Tasks

- [x] Task 1: QC 双轨字段
  - [x] SubTask 1.1: 在 `drw_quality_check.py` 新增 `classify_refdoc_status(ref_path, expected_part)`
  - [x] SubTask 1.2: `_check_refdoc_correct` 输出新增 `severity: "warning"` + `reason` 字段
  - [x] SubTask 1.3: `quality_check()` 输出新增 3 顶层字段：`hard_fail`、`warnings`、`drawing_usable`
  - [x] SubTask 1.4: AST parse ok

- [x] Task 2: 环境自检
  - [x] SubTask 2.1: 新增 `app/services/health_check.py`，函数 `run_health_check() -> dict`
  - [x] SubTask 2.2: 实现 7 项检查（SW / 模板 / 宏 / 输出目录 / LLM / DB / 出图脚本）
  - [x] SubTask 2.3: 在 `app/services/__init__.py` 导出 `run_health_check`
  - [x] SubTask 2.4: import 测试 + 真实跑出 7 项结果

- [x] Task 3: UI 分层状态
  - [x] SubTask 3.1: `home_page.py` 增加"环境自检"状态卡，启动时调 `run_health_check()`
  - [x] SubTask 3.2: `qc_page.py` 顶部增加分层状态条
  - [x] SubTask 3.3: `batch_page.py` 表格新列「状态」+ warning 列
  - [x] SubTask 3.4: `main_window.py` 工具栏增加 QComboBox 出图策略；切换 v5 时设 `USE_V5=1`

- [x] Task 4: 重打 v1.0 EXE
  - [x] SubTask 4.1: 重新跑 `pyinstaller --noconfirm build_exe.spec`
  - [x] SubTask 4.2: smoke 启动 5 秒 alive
  - [x] SubTask 4.3: 截图覆盖新「环境自检」与「出图策略」UI 元素

- [x] Task 5: 真实闭环 v1.0 + 发布判定
  - [x] SubTask 5.1: SW 在线确认
  - [x] SubTask 5.2: 跑 v6 闭环 1 轮
  - [x] SubTask 5.3: 读 qc.json 验证 `hard_fail=[]`、`warnings ⊃ ["refdoc_correct"]`、`drawing_usable.pass=True`
  - [x] SubTask 5.4: 写 `release_log.md` 含 4 节 + v1.0 发布判定

# Task Dependencies
- Task 2 与 Task 1 可并行
- Task 3 依赖 Task 2
- Task 4 依赖 Task 1 + 2 + 3
- Task 5 依赖 Task 4
