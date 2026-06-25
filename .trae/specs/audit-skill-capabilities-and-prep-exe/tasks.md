# Tasks

- [x] Task 1: 能力盘点 — 输出 `capability_matrix.md`
  - [x] SubTask 1.1: 阅读 `capabilities.md`、`app/services/`、`app/ui/`、`.trae/specs/enforce-drawing-quality/` 全部 .py，提取真实能力清单
  - [x] SubTask 1.2: 对每条能力填写 (分类 / 入口 / UI 是否暴露 / 备注) 表格
  - [x] SubTask 1.3: 标记"已接 UI"、"仅 CLI"、"仅 MCP" 三类
  - [x] SubTask 1.4: 写到 `.trae/specs/audit-skill-capabilities-and-prep-exe/capability_matrix.md`

- [x] Task 2: 冒烟测试 — 输出 `smoke_test_report.md`
  - [x] SubTask 2.1: 选定 5 个零件 + 1 个装配 + 1 个 SLDDRW 作为测试样本（来自 `3D转2D测试图纸/`）
  - [x] SubTask 2.2: 跑 `drw_qc_loop.py` 单文件链路（生成→QC→修复闭环），记录耗时与产物
  - [x] SubTask 2.3: 跑 `vision_qc.py` 视觉评分链路（如果 LLM 配置可用，否则记 SKIP 并说明）
  - [x] SubTask 2.4: 跑 `app/services/sw_runner.py` 桌面服务调用，验证 UI 信号 log_line/progress/finished
  - [x] SubTask 2.5: 跑 `app/ui/main_window.py` 启动并截图首页/批量/QC 三页，验证基本可用
  - [x] SubTask 2.6: 汇总 pass/warn/fail，写到 `smoke_test_report.md`

- [x] Task 3: UX 评审 — 输出 `ux_review.md` 与小修补
  - [x] SubTask 3.1: 按 8 项 UX 维度（状态可见性 / 用户控制 / 错误处理 / 一致性 / 防错 / 空态 / 键盘 / 帮助）评审 `app/ui/`
  - [x] SubTask 3.2: 列出 P0 / P1 / P2 问题清单
  - [x] SubTask 3.3: 仅修补 P0（不可用、阻断流程、显眼缺陷）：例如停止按钮、空状态文案、错误徽章、键盘 Esc 取消
  - [x] SubTask 3.4: 验证修补后 UI 仍能启动且不引入回归（`python -m app.main` 启动验证）

- [x] Task 4: GB 制图规范比对 — 输出 `gb_compliance_matrix.md` 与生成器/QC 补丁
  - [x] SubTask 4.1: 列出 10 条核心 GB 条款，逐条对照 `drw_generate_v5.py` 与现有 SLDDRW 输出现状
  - [x] SubTask 4.2: 对 ❌ 项给出最小补丁（标题栏字段映射、字体强制、剖视检查、粗糙度等）
  - [x] SubTask 4.3: 把新增 5 项 QC 规则加入 `drw_quality_check.py`（带开关，默认开启）
  - [x] SubTask 4.4: 在 `LB26001-A-04-001` 上回归 QC，确认 status ∈ {pass, warn}

- [x] Task 5: 打包前检查清单 — 输出 `pre_exe_checklist.md`
  - [x] SubTask 5.1: 列出依赖（`requirements_app.txt` / pywin32 / comtypes / PySide6 / httpx）
  - [x] SubTask 5.2: 列出运行时资源（config 模板、模板路径、QC 脚本绝对路径解决方案）
  - [x] SubTask 5.3: 列出错误兜底（无 SolidWorks、无 LLM Key、无网络、模板缺失）
  - [x] SubTask 5.4: 给出 YES/NO 结论与阻塞项清单（不真的执行 PyInstaller）

- [x] Task 6: 验证 & 收尾
  - [x] SubTask 6.1: 按 `checklist.md` 逐项打钩
  - [x] SubTask 6.2: 失败项回填 tasks.md 修复（无失败，未触发）

# Task Dependencies
- Task 2 依赖 Task 1（先盘点再测）
- Task 3 与 Task 4 可并行（UI 与生成器互不冲突）
- Task 5 依赖 Task 1/2/3/4（汇总结论）
- Task 6 依赖 Task 1~5
