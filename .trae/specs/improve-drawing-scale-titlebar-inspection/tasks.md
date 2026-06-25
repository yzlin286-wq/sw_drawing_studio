# Tasks

- [x] Task 1: 修正比例尺为 GB 标准比例 + 视觉模型辅助判断
  - [x] SubTask 1.1: 修改 `drw_generate_v6.py` 的 `CANDIDATE_SCALES` 为 `[(5,1),(2,1),(1,1),(1,2),(1,5),(1,10),(1,20),(1,50)]`，移除 3:1/1:3/1:4/1:100
  - [x] SubTask 1.2: 新增 `app/services/scale_advisor.py`，提供 `advise_scale(png_path, current_scale, llm)` 函数
  - [x] SubTask 1.3: `advise_scale` 用 LLM 视觉模型看生成图 PNG，返回 `{reasonable, suggestion, score}`
  - [x] SubTask 1.4: 真实用 1 张 PNG 跑通 `advise_scale()`，验证返回 JSON

- [x] Task 2: 扩展标题栏为完整表格 + 模板录入
  - [x] SubTask 2.1: 新增 `config/titlebar_template.yaml`，含公司名/制图人/审核人/交付日期等默认值
  - [x] SubTask 2.2: 修改 `drw_generate_v6.py` 的 `_draw_title_block()` 函数，扩展为 7 行 × 4 列表格
  - [x] SubTask 2.3: 新增字段：技术要求行 / 工艺信息行 / 源文件信息行 / 交付信息行
  - [x] SubTask 2.4: 出图时读取 `titlebar_template.yaml` 填充默认值，SLDPRT 属性覆盖
  - [x] SubTask 2.5: 真实跑 1 件 SLDPRT，验证标题栏 7 行渲染完整

- [x] Task 3: 新增 3D-2D 视觉比对
  - [x] SubTask 3.1: 新增 `app/services/model_compare.py`，提供 `compare_model_2d(part_path, slddrw_png_path, llm)` 函数
  - [x] SubTask 3.2: 用 SolidWorks COM 渲染 3D 模型等轴测视图为 PNG（OpenDoc6 + ViewOrientation + SaveAs PNG）
  - [x] SubTask 3.3: LLM 同时接收 3D PNG + 2D PNG，返回 `{consistency, missing_views, structural_diff}`
  - [x] SubTask 3.4: 真实用 1 件 SLDPRT + 1 张 2D PNG 跑通 `compare_model_2d()`

- [x] Task 4: 增强质检 3 项
  - [x] SubTask 4.1: 在 `drw_quality_check.py` 新增 `scale_gb_standard` 检查（比例是否为 GB/T 14690 标准值）
  - [x] SubTask 4.2: 在 `drw_quality_check.py` 新增 `titlebar_complete` 检查（标题栏 7 行字段完整性）
  - [x] SubTask 4.3: 在 `drw_quality_check.py` 新增 `model_2d_consistency` 检查（调 `compare_model_2d`）
  - [x] SubTask 4.4: 3 项检查结果进入 warnings（不阻断交付），写入 qc.json

- [x] Task 5: 真实验证与归档
  - [x] SubTask 5.1: 用 LB26001-A-04-001.SLDPRT 跑完整闭环（v6 出图 + QC + vision + 3D-2D 比对）
  - [x] SubTask 5.2: 验证比例尺为 GB 标准值、标题栏 7 行完整、3D-2D 比对有结果
  - [x] SubTask 5.3: 归档到 `improve-drawing-scale-titlebar-inspection/validation_log.md`

# Task Dependencies
- Task 2 依赖 Task 1（比例尺修正后再改标题栏，避免冲突）
- Task 3 独立（可与 Task 1/2 并行）
- Task 4 依赖 Task 1 + Task 2 + Task 3（3 项检查需要比例尺/标题栏/3D-2D 比对就绪）
- Task 5 依赖 Task 1 + Task 2 + Task 3 + Task 4
- Task 1 与 Task 3 可并行
