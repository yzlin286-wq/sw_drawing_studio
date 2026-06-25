# Tasks

- [x] Task 1: 设计模板规格
  - [x] SubTask 1.1: 把图框尺寸 / 标题栏网格坐标 / 字高映射 / 图层定义 / 13 字段的 CustomProperty key 名汇总到 `template_spec.md`（同目录下）
  - [x] SubTask 1.2: 标题栏 5×3 = 15 格的 (cell_id, x, y, label, prp_key) 表格化

- [x] Task 2: 写 build_drwdot.py
  - [x] SubTask 2.1: 在仓库根新建 `templates/`，落地 `templates/build_drwdot.py`
  - [x] SubTask 2.2: 脚本流程：连接 SW → NewDocument(空白 drawing 模板) → 切到 sheet sketch → 画图框 + 标题栏 19 条线 → 退 sketch → InsertNote ×15（13 字段标签 + 2 个 $PRP）→ 设字高 5 mm + 图层 5 层 + 第一角投影 → SaveAs `templates/gb_a4_landscape.drwdot`（type=swDocTEMPLATE_DRAWING=1）
  - [x] SubTask 2.3: 字高用 `model.SetUserPreferenceDoubleValue(89, 0.005)` 后 `model.Extension.RebuildSheets`
  - [x] SubTask 2.4: 图层用 `LayerMgr.AddLayer(name, desc, color, style, weight)` 5 次

- [x] Task 3: 写 probe_drwdot.py
  - [x] SubTask 3.1: 落地 `templates/probe_drwdot.py`
  - [x] SubTask 3.2: 5 项验证：sheet 尺寸 / 字高 / 图层数 / 标题栏 NoteBlock 字段 / CustomProperty 链接
  - [x] SubTask 3.3: 输出 JSON 到 `.trae/specs/craft-gb-drwdot-template/probe_result.json`

- [x] Task 4: v5 接入新模板
  - [x] SubTask 4.1: 修改 `drw_generate_v5.py`：`drwdot = os.environ.get("DRWDOT_TEMPLATE")` 或读 `app.yaml.drwdot_template`，优先 `NewDocument(drwdot, paper_size, 0.297, 0.210)`；缺失时回退原行为
  - [x] SubTask 4.2: 修改 `app/config/defaults.py`：`get_app_config()` 默认值里 `drwdot_template = repo_root/templates/gb_a4_landscape.drwdot`
  - [x] SubTask 4.3: 修改 `config/app.yaml.example`：`drwdot_template` 字段示例改为 `templates/gb_a4_landscape.drwdot`

- [x] Task 5: 真实跑闭环 + 归档
  - [x] SubTask 5.1: 检测/启动 SolidWorks 2025
  - [x] SubTask 5.2: 跑 `python templates/build_drwdot.py` 生成模板
  - [x] SubTask 5.3: 跑 `python templates/probe_drwdot.py` 验证 5 项 pass
  - [x] SubTask 5.4: 跑 `python .trae/specs/harden-v5-and-vision-loop/vision_loop.py LB26001-A-04-001.SLDPRT --max-rounds 2 --threshold 80`
  - [x] SubTask 5.5: 把构造耗时 / 探针 / v5 接入日志 / vision_loop 结果归档到 `build_log.md`
  - [x] SubTask 5.6: 同步更新 `harden-v5-and-vision-loop/vision_loop_log.md` 末尾"## 三次验证（模板根治后）"节

# Task Dependencies
- Task 2 依赖 Task 1
- Task 3 依赖 Task 2
- Task 4 与 Task 3 可并行
- Task 5 依赖 Task 2 + 3 + 4
- Task 6 依赖 Task 5

- [x] Task 6: 修复 Task 5 暴露的 2 项 checklist 失败（依据 spec mode 第七步）
  - [x] SubTask 6.1: 修 v5 让其在使用模板时**跳过**自绘图框/标题栏（模板已含），避免覆盖模板字段
  - [x] SubTask 6.2: v5 调 NewDocument 第 2 参数从 0 改为 12（swDwgPaperA4size 横式），强制应用 A4
  - [x] SubTask 6.3: 让 quality_check 的 text_height/paper_size 读取路径与 probe_drwdot 一致（GetUserPreferenceTextFormat(1).CharHeight 文档级、sheet.GetSize 失败时回退 GetProperties2）
  - [x] SubTask 6.4: 重跑 vision_loop（≤ 2 轮），更新 build_log.md 末尾"## 节 5 二次闭环验证"
