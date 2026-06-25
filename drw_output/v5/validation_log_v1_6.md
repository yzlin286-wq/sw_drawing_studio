# v1.6 验证日志 (validation_log_v1_6.md)

**生成时间**: 2026-06-19
**SW Revision**: 33.5.0 (SolidWorks 2025)
**pywin32**: rev 33.5.0
**策略**: v6_recommended

---

## 1. 概述

v1.6 针对 v1.5 暴露的 3 个核心问题实施修复：
1. `InsertModelAnnotations3` 在 SW2025 + pywin32 下抛 `<unknown>.InsertModelAnnotations3`，导致 dim_total=0
2. `view_in_frame` 内存重定位后，保存/重载的 outline 仍可能变化，导致 view_out_of_frame
3. `AddHorizontalDimension2` 等需要选中真实几何体，但 `GetEdges`/`SelectByID2("POINT")` 不可靠

v1.6 实施 6 个 Task：
- Task 1: 新增模型副本尺寸源注入 (model_dim_seed_service.py)
- Task 2: 新增 VBA sidecar (annotate_sidecar_service.py + auto_annotate.bas)
- Task 3: 新增 persisted_layout_solver (SaveAs→Close→Reopen→GetOutline)
- Task 4: 保持 PNG 回退 (PDF→PyMuPDF)
- Task 5: QC 结构升级 (dimension_coverage 字段)
- Task 6: 真实验证 (6 项)

---

## 2. Task 实施结果

### Task 1: 模型副本尺寸源注入
**状态**: 已实施，但不可靠（降级）

- 新增 `app/services/model_dim_seed_service.py` (310 行)
- 复制 SLDPRT 到 run_dir/input_work/，不修改原始文件
- 使用 GetPartBox(True) 获取 bbox ✓
- 创建 AUTO_DIM_GUIDE 3D sketch ✓
- **问题**: AddDimension2 在 pywin32 下不可靠：
  - `line.GetStartPoint2()` 抛 `找不到成员` (-2147352573)
  - `SelectByID2("EXTSKETCHPOINT")` 抛 `类型不匹配` (-2147352571)
  - `line.Select4` 抛 `类型不匹配` (-2147352571)
- **降级**: seed_dim_count=0，seed service 返回 success=True 但无尺寸
- 与用户预期一致："AddHorizontalDimension2 需要选中真实几何体；当前 GetEdges / SelectByID2("POINT") 不可靠"

### Task 2: VBA sidecar
**状态**: 已实施，但不可靠（降级）

- 新增 `app/services/annotate_sidecar_service.py` (240 行)
- 新增 `templates/macros/auto_annotate.bas` (72 行)
- **问题 1**: `active.GetType()` 抛 `'int' object is not callable` → 修复为属性/方法兼容
- **问题 2**: `RunMacro2` 第 5 参数需 VARIANT byref int → 修复
- **问题 3**: `RunMacro2` 对 .bas 文件返回 False（.bas 不能直接运行，需先编译为 .swp）
- **问题 4**: result json 路径错误（run_dir 拼接错误）→ 修复为 out_dir
- **降级**: sidecar 不可用，dim_total 仍按 QC 判断，不假装成功
- 与用户要求一致："若 sidecar 不可用，必须降级并记录，不得假装成功"

### Task 3: persisted_layout_solver
**状态**: ✓ 已实施并验证通过

- 新增 `app/services/persisted_layout_solver.py`
- 生成 drawing 后 SaveAs → Close → Reopen → GetOutline
- 同时检测 overlap 和 out_of_frame
- 若任一失败，降比例并重新保存/重开测量
- **关键修复**:
  - SaveAs 第 4 参数需 `VARIANT(VT_DISPATCH, None)` 而非 `None`（否则抛"类型不匹配"）
  - 移除无效的位置调整（save/reopen 后位置不持久化）
  - 添加 `_vt_dispatch_none()` 辅助函数
  - 多策略视图遍历（GetFirstView/GetNextView + GetViews property + GetSheetNames）
  - `_call_or_get` 兼容 COM property/method 双态访问
  - 0 个视图视为失败（不误判为成功）
- **验证**: LB26001-A-04-004 迭代 6 scale=1:10 成功，无 overlap/out_of_frame

### Task 4: PNG 回退
**状态**: ✓ 已实施并验证通过

- 保留 run_manager PDF→PyMuPDF 回退
- 不再调用 `sw.GetExportFileData(2)`
- PNG 失败才进入 hard_fail
- PDF 存在且 PyMuPDF 渲染成功时，从 hard_fail 移除 png_missing
- **验证**: 小零件 5 件 png_missing=0/5 ✓

### Task 5: QC 结构升级
**状态**: ✓ 已实施

- 新增 `dimension_coverage` 字段：
  - `dim_total`: DisplayDim 总数
  - `source`: model_items / model_seed / drawing_sketch_fallback / none
  - `overall_length/width/height`: 从 bbox_m 或 seed_dim.json 读取
  - `hole_diameter/location`: None（未实现）
  - `associativity`: model / model_seed / non_model / none / unknown
- `dim_total_zero` 为 hard_fail
- `dim_total_below_threshold` (<5 但 >0) 为 warning
- `non_model_associative_dimension` 作为 warning
- `refdoc_correct` 继续 warning，不阻断交付 ✓

### Task 6: 真实验证
见下文第 3 节

---

## 3. Task 6 真实验证结果

### Task 6.1: LB26001-A-04-001 不退化
**状态**: ✓ PASS
- hard_fail=[]
- dim_total=44
- qc_pass=11/12
- drawing_usable=True

### Task 6.2: LB26001-A-04-002 dim_total>=5
**状态**: ✗ FAIL（降级记录）
- dim_total=0（目标 >=5）
- hard_fail=['dim_total_zero', 'qc_pass_too_low']
- **原因**: InsertModelAnnotations3 抛 `<unknown>.InsertModelAnnotations3`；sidecar RunMacro2 对 .bas 返回 False；seed service AddDimension2 不可靠
- **降级**: 如实记录 dim_total=0，不假装成功

### Task 6.3: LB26001-A-04-004 无 view_overlap/out_of_frame
**状态**: ✓ PASS
- hard_fail=[]
- dim_total=64
- qc_pass=11/12
- drawing_usable=True
- persisted_layout: 迭代 6 scale=1:10 成功
- **关键修复**: SaveAs 用 `_vt_dispatch_none()` 替代 None

### Task 6.4: -M3x8十字螺丝 dim_total>=3
**状态**: ✗ FAIL（降级记录）
- dim_total=0（目标 >=3）
- hard_fail=['dim_total_zero', 'qc_pass_too_low']
- **原因**: 同 Task 6.2

### Task 6.5: LB26001-A-04-001~009 PASS/WARNING>=6/9
**状态**: ✗ 未达标（5/9，目标 6/9）

| 件号 | status | hard_fail | qc_pass | dim_total | usable |
|------|--------|-----------|---------|-----------|--------|
| 001 | warning | [] | 11 | 44 | True |
| 002 | failed | dim_total_zero, qc_pass_too_low | 9 | 0 | False |
| 003 | failed | dim_total_too_low, qc_pass_too_low | 9 | 0 | False |
| 004 | warning | [] | 11 | 64 | True |
| 005 | warning | [] | 10 | 8 | True |
| 006 | warning | [] | 10 | 8 | True |
| 007 | failed | dim_total_too_low, qc_pass_too_low | 9 | 0 | False |
| 008 | warning | [] | 11 | 32 | True |
| 009 | failed | dim_total_too_low, qc_pass_too_low | 9 | 0 | False |

- success=0, warning=5, failed=4
- pass_rate=55.6%（目标 66.7%）
- 失败件均为 dim_total 问题（002/003/007/009）

### Task 6.6: 小零件 5 件 png_missing=0, dim_total_zero<=1/5
**状态**: 部分达标

| 件号 | status | png_missing | dim_total_zero | dim_total |
|------|--------|-------------|----------------|-----------|
| -AK-15-AC-25 | failed | False | False | 0 |
| -AK-15-AC-26 | failed | False | False | 0 |
| -AK-15-AC-27 | failed | False | True | 0 |
| -M3x8十字螺丝 | failed | False | True | 0 |
| -弹簧压棒弹簧 | failed | False | True | 0 |

- png_missing=0/5 ✓（目标 0，达标）
- dim_total_zero=3/5 ✗（目标 <=1，未达标）
- 注：AC-25/26 的 hard_fail 是 `dim_total_too_low`（非 `dim_total_zero`），但 dim_total 实际仍为 0

---

## 4. 关键修复总结

### 4.1 SaveAs 类型不匹配修复
**问题**: `drw.Extension.SaveAs(path, 0, 1, None, err, warn)` 抛 `(-2147352571, '类型不匹配。', None, 4)`
**原因**: SaveAs 第 4 参数需 VARIANT(VT_DISPATCH, None)，不能直接传 None
**修复**: 新增 `_vt_dispatch_none()` 辅助函数，返回 `VARIANT(pythoncom.VT_DISPATCH, None)`
**影响**: persisted_layout_solver 的 SaveAs 现在能成功保存 ScaleRatio 修改

### 4.2 persisted_layout_solver 视图遍历
**问题**: `GetFirstView()` 抛 `DISP_E_MEMBERNOTFOUND`，`GetSheetNames`/`GetViews` 是 tuple 不是 callable
**修复**: 
- 多策略遍历（A: GetFirstView/GetNextView 链，B: GetViews property，C: GetSheetNames 遍历）
- `_call_or_get` 兼容 COM property/method 双态访问
- 3 次重试 + ForceRebuild3

### 4.3 sidecar GetType 修复
**问题**: `active.GetType()` 抛 `'int' object is not callable`
**原因**: pywin32 中 GetType 可能是属性不是方法
**修复**: 兼容处理 `if callable(gt): doc_type = gt() else: doc_type = gt`

### 4.4 sidecar RunMacro2 参数修复
**问题**: `RunMacro2(path, mod, proc, 1, 0)` 抛 `类型不匹配`
**原因**: 第 5 参数需 VARIANT byref int
**修复**: `VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)`

### 4.5 sidecar 触发条件扩展
**问题**: sidecar 只在 `not imported` 时触发，但 RunCommand(826) 不抛异常就把 imported=True
**修复**: 触发条件扩展为 `(not imported) OR (dim_total < 5)`

---

## 5. 已知限制

1. **InsertModelAnnotations3 在 SW2025 + pywin32 下不可靠**
   - 抛 `<unknown>.InsertModelAnnotations3`
   - 影响: 002/003/007/009/小零件 dim_total=0

2. **VBA sidecar 对 .bas 文件不可靠**
   - RunMacro2 返回 False
   - 需要手动预编译为 .swp 文件
   - 影响: sidecar 降级，dim_total 仍为 0

3. **seed service AddDimension2 不可靠**
   - GetStartPoint2/EndPoint 找不到成员
   - SelectByID2("EXTSKETCHPOINT") 类型不匹配
   - line.Select4 类型不匹配
   - 影响: seed_dim_count=0

4. **位置调整在 save/reopen 后不持久化**
   - Position 设置后 save/reopen outline 不变
   - 影响: 移除位置调整，直接降比例

5. **refdoc_correct 仍为 warning**
   - SW2025 + pywin32 持久化限制
   - 不阻断交付 ✓

---

## 6. 达标情况汇总

| Task | 目标 | 实际 | 达标 |
|------|------|------|------|
| 6.1 | 001 hard_fail=[] | hard_fail=[] | ✓ |
| 6.2 | 002 dim_total>=5 | dim_total=0 | ✗ |
| 6.3 | 004 无 overlap/out_of_frame | 无 overlap/out_of_frame | ✓ |
| 6.4 | 螺丝 dim_total>=3 | dim_total=0 | ✗ |
| 6.5 | 001~009 PASS/WARNING>=6/9 | 5/9 | ✗ |
| 6.6 | 小零件 png_missing=0 | 0/5 | ✓ |
| 6.6 | 小零件 dim_total_zero<=1/5 | 3/5 | ✗ |

**整体**: 7 项目标中 3 项达标，4 项未达标
**核心成果**: 
- view_out_of_frame 问题已解决（Task 3 persisted_layout_solver）
- PNG 回退完全生效（Task 4）
- QC 结构升级完成（Task 5 dimension_coverage）
**未解决**: 
- dim_total=0 问题（sidecar/seed 在 SW2025 + pywin32 下不可靠，已降级记录）

---

## 7. 输出文件清单

- `validation_log_v1_6.md` (本文件)
- `seed_dim.json`: 各 run 的 input_work/seed_dim.json（seed service 降级，seed_dim_count=0）
- `annotate_result.json`: 各 run 的 qc/annotate_result.json（sidecar 降级，未生成）
- `persisted_layout.json`: 各 run 的 drawing/persisted_layout.json
- `qc.json`: 各 run 的 qc/<part>_v5_qc.json
- `full_pipeline manifest`: 各 run 的 manifest.json
- `task6_5_results.json`: drw_output/v5/task6_5_results.json
- `task6_6_results.json`: drw_output/v5/task6_6_results.json

---

## 8. 后续建议

1. **手动预编译 auto_annotate.swp**: 在 SolidWorks VBA IDE 中打开 auto_annotate.bas，另存为 .swp，使 sidecar 能通过 RunMacro2 执行
2. **C# sidecar**: 用 C# 早期绑定 SolidWorks API 调用 InsertModelAnnotations3，编译为 SwAnnotate.exe，避免 pywin32 COM 方法分发问题
3. **工程图直接标注**: 在工程图中用 SelectByID2 选中视图轮廓边（不是 3D 模型边），再用 InsertDimension2 标注
4. **降低 dim_total 阈值**: 若业务允许，可将 dim_total>=5 降为 dim_total>=3，但用户明确要求"不是只降低 QC 阈值"
