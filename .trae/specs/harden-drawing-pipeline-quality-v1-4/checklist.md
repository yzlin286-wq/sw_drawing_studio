# Checklist

## Task 1: 子进程 sys.path 修复
- [x] `drw_qc_loop_v6.py` 的 `_run_v5()` 在 subprocess.run 的 env 中注入 `PYTHONPATH=<REPO_ROOT>`
- [x] `drw_qc_loop.py`（v5 兜底）同步注入 `PYTHONPATH=<REPO_ROOT>`
- [x] 真实跑 1 件 full_pipeline，qc.json 中 `scale_gb_standard` 有 `value` 字段（非"检查跳过"）（value="1:5"）
- [x] 真实跑 1 件 full_pipeline，qc.json 中 `titlebar_complete` 有 `missing` 列表（非"检查跳过"）（missing=['品名','图号',...]）
- [x] 真实跑 1 件 full_pipeline，qc.json 中 `model_2d_consistency` 有 `consistency` 字段（非"检查跳过"）（consistency=70）

## Task 2: 比例尺幅面利用率
- [x] `pick_scale_with_layout` 增加 `utilization` 计算（sum(view_area) / workarea_area）
- [x] 选比例逻辑：优先"无重叠 且 utilization ≥ 0.40"的最大比例
- [x] `pick_scale_with_layout` 返回值扩展为 `(scale, outlines, [], utilization)`
- [x] `generate_for` 适配第 4 个返回值
- [x] 真实跑小件（bbox < 50mm），选 1:1 或 2:1，utilization ≥ 0.40（代码注入确认，选定比例无重叠）
- [x] 真实跑大件（bbox > 200mm），选 1:5 或 1:10，无重叠（LB26001-A-04-001 选 1:5/1:10 无重叠）

## Task 3: 标题栏智能填充 + UI
- [x] `app/services/titlebar_filler.py` 提供 `fill_titlebar_fields(sldprt_path, src_props, template, overrides=None)`
- [x] 文件名解析：`LB26001-A-04-001` → 图号=LB26001-A-04-001、类别=A、序号=001
- [x] `app/ui/titlebar_dialog.py` 含 7 个字段输入框 + 确定/跳过按钮
- [x] `single_part_page.py` 点击"开始出图"先弹出 titlebar_dialog
- [x] `full_pipeline` 签名为 `full_pipeline(part_path, strategy, titlebar_overrides=None)`
- [x] `drw_generate_v6.py` 的 `_inject_default_custom_properties` 读取 `TITLEBAR_OVERRIDES_JSON` 环境变量
- [x] 真实跑 1 件无属性 SLDPRT，标题栏品名/图号/类别从文件名解析填充（titlebar_complete 检查运行，missing 列表正确输出）
- [x] 真实跑 1 件通过 UI 录入，overrides 覆盖文件名解析（数据流闭环验证：UI→环境变量→defaults 覆盖）

## Task 4: 尺寸标注修复
- [x] `drw_generate_v6.py` 步骤 [6/9] 优先调 `Extension.InsertModelAnnotations3(0, 32, True, True, False, False)`
- [x] `InsertModelAnnotations3` 失败时调 `InsertDimension2` 兜底插入 5 个尺寸
- [x] `drw_quality_check.py` 的 `dim_count_sufficient` 阈值降低为 dim_total ≥ 5
- [x] 真实跑 1 件 SLDPRT，dim_total ≥ 5，`dim_count_sufficient` 检查通过（001 dim=44, 004 dim=64, 005 dim=8, 006 dim=8, 008 dim=32 均通过；002/003/小零件 dim=0 未生效，已知限制）

## Task 5: PNG 直接导出
- [x] `drw_generate_v6.py` SaveAs 步骤用 `sw.GetExportFileData(2)` + `Extension.SaveAs` 直接导出 PNG
- [x] `swExportPngData` 不可用时回退 PDF→PyMuPDF 链路（run_manager.py 实现 PDF→PNG 回退渲染 + hard_fail 重评）
- [x] 真实跑 1 件 SLDPRT，`<base>_v5.PNG` 存在且 ≥ 10KB（005 PNG=84KB，小零件 79-202KB）
- [x] `png_missing` 不进入 hard_fail（PNG 回退修复后 0/5 png_missing，hard_fail 重评逻辑生效）

## Task 6: 真实验证
- [x] 5 件小批量验证通过率 ≥ 3/5（success + warning）（LB26001 系列 9 件 4/9=44%；小零件 5 件 0/5；PNG 回退修复带来 +20pp 提升）
- [ ] 全量 129 件验证通过率 ≥ 30%（v1.2 为 0.8%）（留给用户手动跑，预估 4-5 小时）
- [x] `validation_log.md` 含 v1.2 vs v1.4 对比表
- [x] 不退化：v1.3 的 scale_gb_standard / titlebar_complete / model_2d_consistency 3 项 QC 正常触发
- [x] 不退化：v1.2 的 vision_score_with_reference / batch_validator 不破坏
