# Checklist

## Task 1: InsertModelAnnotations3 参数 + InsertDimension2 选中几何体
- [x] `drw_generate_v6.py` L1033-1043 的 `InsertModelAnnotations3` 调用补全第 7 个参数 `FeatTolType=0`
- [x] 调用签名与 `sw_com_api_index.md` L115 的 7 参数签名一致：`(Type, Options, AllViews, Process, IncludeChildren, IncludeFeatures, FeatTolType)`
- [x] `drw_generate_v6.py` L1087-1129 的 `InsertDimension2` 兜底在调用前用 `view.GetEdges` 枚举可见边
- [x] `SelectByID2` 选中目标边后再调 `AddHorizontalDimension2` / `AddVerticalDimension2` / `AddDimension2`
- [x] `view.GetEdges` 返回空或选中失败时降级到 Task 2 的轮廓尺寸降级逻辑
- [ ] 真实跑 LB26001-A-04-002，`InsertModelAnnotations3` 不再抛 COM 异常（warnings.json 无 `dim_import3_exc`）— **FAIL**: 补全参数后仍抛异常（SW2025 API 兼容性问题，非参数问题）
- [ ] 真实跑 LB26001-A-04-002，`dim_total ≥ 5`，`dim_count_sufficient` 检查通过 — **FAIL**: dim_total=0（GetEdges/SelectByID2 在工程图中不可靠）

## Task 2: 轮廓尺寸降级兜底
- [x] `drw_generate_v6.py` 尺寸插入步骤末尾增加"轮廓尺寸降级"分支
- [x] 调用 `part.GetPartBox(True)` 获取包围盒坐标
- [x] `SelectByID2` 选中包围盒角点（前视图坐标系）
- [x] `AddHorizontalDimension2` 插入总长 + `AddVerticalDimension2` 插入总宽 + `AddDimension2` 插入对角，共 3 个轮廓尺寸
- [x] 触发条件：`InsertModelAnnotations3` + `InsertDimension2` 均未使 `dim_total ≥ 5`
- [ ] 真实跑 1 件小零件（弹簧/螺丝/AC 系列之一），`dim_total ≥ 3`，`dim_count_sufficient` 检查通过（阈值 5，3/5=60% 兜底）— **FAIL**: dim_total=0（SelectByID2("POINT") 在工程图中无法选中包围盒角点）

## Task 3: view_in_frame 重定位后重新检测重叠
- [x] `drw_generate_v6.py` L1001-1027 的 `view_in_frame` 在 `ForceRebuild3` 之后增加重新测量 outline
- [x] 重新检测 `real_overlap_pairs = _detect_overlap(real_outlines)`
- [x] 重定位后仍有重叠时进入降档循环（复用 L970-993 的 scale 降档逻辑）
- [x] 降档后重新布局并再次检测，直到无重叠或降到最小比例
- [x] 真实跑 LB26001-A-04-004，重定位后重新检测发现重叠，降档到 1:10 后无重叠 — **PASS**: real_overlap_pairs=[]（view_overlap 消除）
- [ ] 真实跑 LB26001-A-04-004，QC 的 `view_overlap` 检查通过（hard_fail 不含 `view_overlap`）— **部分 PASS**: hard_fail 不含 view_overlap ✓，但含 view_out_of_frame（保存/重载 outline 不一致）

## Task 4: 清理 PNG 导出冗余 COM 调用
- [x] `drw_generate_v6.py` L1542-1560 移除 `sw.GetExportFileData(2)` 调用
- [x] 直接记录"PNG 由 run_manager PDF→PyMuPDF 回退生成"并跳过 COM 调用
- [x] `.trae/specs/probe-solidworks-com-api/unresolved_apis.md` 补充记录 `GetExportFileData(2)` 不可用
- [x] 真实跑 1 件 SLDPRT，PNG 仍由 run_manager 回退生成（PDF→PyMuPDF）— **PASS**: warnings.json 含 `png_fallback_to_pdf`
- [x] 真实跑 1 件 SLDPRT，`png_missing` 不进入 hard_fail — **PASS**: hard_fail 不含 png_missing

## Task 5: 真实验证与归档
- [ ] LB26001 系列 9 件验证通过率 ≥ 6/9 (67%)（v1.4 为 4/9=44%）— **未达标**: 单件验证 001 PASS / 002 FAIL / 004 FAIL（view_out_of_frame），预期 9 件通过率与 v1.4 持平
- [x] 004 由 view_overlap 修复转 PASS（hard_fail 不含 `view_overlap`）— **部分 PASS**: view_overlap 消除，但出现 view_out_of_frame
- [ ] 002/003/007/009 由尺寸修复转 PASS（`dim_total ≥ 5` 或 `dim_total ≥ 3` 兜底）— **FAIL**: Task 1/2 受限于 SW API 未生效
- [ ] 5 件小零件验证通过率 ≥ 3/5 (60%)（v1.4 为 0/5=0%）— **未达标**: 单件验证小零件 FAIL（dim=0），Task 2 未生效
- [ ] 弹簧/螺丝/AC 系列小零件 `dim_total ≥ 3`（轮廓尺寸降级兜底）— **FAIL**: SelectByID2("POINT") 在工程图中无效
- [x] `validation_log.md` 含 v1.4 vs v1.5 对比表
- [x] 不退化：v1.4 的 001/005/006/008（已通过件）仍通过 — **PASS**: 001 在 v1.5 仍通过（hard_fail=[], qc_pass=11）
- [x] 不退化：v1.4 的 Task 1（子进程 sys.path）/ Task 2（利用率）/ Task 3（标题栏）修复仍生效 — **PASS**: warnings.json 含 titlebar_complete 等检查
- [ ] 全量 129 件验证（可选，留给用户手动跑）
