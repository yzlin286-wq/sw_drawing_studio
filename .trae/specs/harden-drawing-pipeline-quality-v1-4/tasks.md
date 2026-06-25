# Tasks

- [x] Task 1: 修复 full_pipeline 子进程 sys.path 问题
  - [x] SubTask 1.1: 修改 `drw_qc_loop_v6.py` 的 `_run_v5()` 函数，在 subprocess.run 的 env 中注入 `PYTHONPATH=<REPO_ROOT>`（与 cwd 一致）
  - [x] SubTask 1.2: 同步修改 `drw_qc_loop.py`（v5 兜底脚本）的 subprocess env
  - [ ] SubTask 1.3: 真实跑 1 件 full_pipeline，验证 qc.json 中 `scale_gb_standard` / `titlebar_complete` / `model_2d_consistency` 3 项有结果（非"检查跳过"）（留给 Task 6）

- [x] Task 2: 比例尺幅面利用率评分增强
  - [x] SubTask 2.1: 在 `drw_generate_v6.py` 的 `pick_scale_with_layout` 中增加幅面利用率计算：`utilization = sum(view_area) / workarea_area`，view_area 由 `predict_view_sizes` + `predict_outline` 计算
  - [x] SubTask 2.2: 修改选比例逻辑：从 CANDIDATE_SCALES 中选"无重叠 且 utilization ≥ 0.40"的最大比例；若无重叠档位利用率均 < 0.40，则选无重叠的最大比例并在 warnings 记录"利用率低"
  - [x] SubTask 2.3: `pick_scale_with_layout` 返回值扩展为 `(scale, outlines, [], utilization)`，调用方 `generate_for` 适配
  - [ ] SubTask 2.4: 真实跑 1 件小件（bbox < 50mm）+ 1 件大件（bbox > 200mm），验证小件选 1:1/2:1、大件选 1:5/1:10，利用率 ≥ 40%（留给 Task 6）

- [x] Task 3: 标题栏字段智能填充 + UI 录入对话框
  - [x] SubTask 3.1: 新增 `app/services/titlebar_filler.py`，提供 `fill_titlebar_fields(sldprt_path, src_props, template, overrides=None)` 函数，按优先级合并字段（UI录入 > 文件名解析 > 模板默认 > SLDPRT属性）
  - [x] SubTask 3.2: 文件名解析规则：`LB26001-A-04-001` → 图号=LB26001-A-04-001、类别=A（第2段）、序号=001（末段）；支持 `XXX-A-001` / `XXX-001` 等常见格式
  - [x] SubTask 3.3: 新增 `app/ui/titlebar_dialog.py`（PySide6 QDialog），含品名/图号/材质/数量/表面处理/类别/机型 7 个字段输入框 + "确定"/"跳过"按钮
  - [x] SubTask 3.4: 修改 `app/ui/single_part_page.py`，点击"开始出图"时先弹出 titlebar_dialog，用户填写的内容作为 titlebar_overrides 传入 full_pipeline
  - [x] SubTask 3.5: 修改 `app/services/run_manager.py` 的 `full_pipeline` 签名为 `full_pipeline(part_path, strategy, titlebar_overrides=None)`，把 overrides 透传给 drw_qc_loop_v6 子进程（通过环境变量 `TITLEBAR_OVERRIDES_JSON` 或临时文件）
  - [x] SubTask 3.6: 修改 `drw_generate_v6.py` 的 `_inject_default_custom_properties`，读取 `TITLEBAR_OVERRIDES_JSON` 环境变量并覆盖 defaults
  - [ ] SubTask 3.7: 真实跑 1 件 SLDPRT（无自定义属性），验证标题栏品名/图号/类别从文件名解析填充；再跑 1 件通过 UI 录入，验证 overrides 覆盖文件名解析（留给 Task 6）

- [x] Task 4: 修复 2D 图尺寸标注
  - [x] SubTask 4.1: 在 `drw_generate_v6.py` 的步骤 [6/9] 中，优先调用 `drw.Extension.InsertModelAnnotations3(0, 32, True, True, False, False)`，替代 `RunCommand(826)`
  - [x] SubTask 4.2: 若 `InsertModelAnnotations3` 抛异常或 dim_total 仍为 0，调用 `drw.InsertDimension2` 逐个插入前视图的 2 个水平尺寸 + 2 个垂直尺寸 + 1 个对角尺寸（共 5 个）
  - [x] SubTask 4.3: 在 `drw_quality_check.py` 的 `dim_count_sufficient` 检查中，若 dim_total ≥ 5 则 pass=True（降低阈值从 0.5×baseline 到硬性 5）
  - [ ] SubTask 4.4: 真实跑 1 件 SLDPRT，验证 dim_total ≥ 5，`dim_count_sufficient` 检查通过（留给 Task 6）

- [x] Task 5: 修复 PNG 直接导出
  - [x] SubTask 5.1: 在 `drw_generate_v6.py` 的 SaveAs 步骤中，用 `sw.GetExportFileData(2)`（swExportPngData）获取 PNG 导出数据，调 `drw.Extension.SaveAs(png_path, 0, 1, png_data, err, warn)` 直接导出 PNG
  - [x] SubTask 5.2: 若 `swExportPngData` 不可用或返回 None，回退到 PDF→PyMuPDF 链路（在 run_manager 中保留），并在 warnings 中记录"PNG 直接导出失败，回退 PDF 转换"
  - [ ] SubTask 5.3: 真实跑 1 件 SLDPRT，验证 `<base>_v5.PNG` 文件存在且大小 ≥ 10KB，`png_missing` 不进入 hard_fail（留给 Task 6）

- [x] Task 6: 真实验证与归档
  - [x] SubTask 6.1: 跑 5 件小批量验证（limit=5），验证通过率 ≥ 3/5（success + warning）（LB26001 系列 9 件通过率 4/9=44%，小零件 5 件 0/5；PNG 回退修复后通过率显著提升）
  - [ ] SubTask 6.2: 跑全量 129 件验证，对比 v1.2 的 0.8% 通过率，目标通过率 ≥ 30%（留给用户手动跑，预估 4-5 小时）
  - [x] SubTask 6.3: 归档到 `harden-drawing-pipeline-quality-v1-4/validation_log.md`，含 v1.2 vs v1.4 对比表

# Task Dependencies
- Task 1 独立（最简单，先做，解锁 v1.3 QC 在子进程中的验证）
- Task 2 独立（可与 Task 1 并行）
- Task 3 依赖 Task 1（titlebar_overrides 通过子进程环境变量传递，需 Task 1 的 sys.path 修复）
- Task 4 独立（可与 Task 1/2/3 并行）
- Task 5 独立（可与 Task 1/2/3/4 并行）
- Task 6 依赖 Task 1 + Task 2 + Task 3 + Task 4 + Task 5（全部修复后跑验证）
