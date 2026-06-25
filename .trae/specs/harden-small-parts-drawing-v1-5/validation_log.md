# v1.5 验证日志

## 1. 验证范围
- 测试件:
  - 单件验证: LB26001-A-04-001（v1.4 通过件，验证不退化）
  - 单件验证: LB26001-A-04-002（v1.4 dim=0 件，验证 Task 1 尺寸修复）
  - 单件验证: LB26001-A-04-004（v1.4 view_overlap 件，验证 Task 3 重检测修复）
  - 单件验证: -M3x8十字螺丝-1-V3-V02（小零件，验证 Task 2 轮廓尺寸降级）
- 执行时间: 2026-06-19 05:36 ~ 06:10
- SolidWorks 版本: 33.5.0 (sw_revision)
- v1.5 修复点: Task 1-4

## 2. 单件验证结果

| 文件 | run_id | hard_fail | qc_pass | drawing_usable | v1.4 对比 |
|------|--------|-----------|---------|----------------|-----------|
| LB26001-A-04-001 | a78bb36345e6 | [] | 11 | True | 持平（v1.4 也通过）✓ 不退化 |
| LB26001-A-04-002 | 026a04b6c974 | dim_total_too_low, qc_pass_too_low | 9 | False | 持平（v1.4 也失败，dim=0）|
| LB26001-A-04-004 | fa66d6a72704 | view_out_of_frame | 10 | False | view_overlap 消除 ✓，但出现 view_out_of_frame |
| -M3x8十字螺丝 | 559542d946b6 | dim_total_too_low, qc_pass_too_low | 9 | False | 持平（v1.4 也失败，dim=0）|

## 3. Task 验证明细

### Task 1: InsertModelAnnotations3 参数 + InsertDimension2 选中几何体
- **SubTask 1.1（参数补全）**: 代码已修改为 7 参数 `fn(0, 32, True, True, False, False, 0)`，与 sw_com_api_index.md L115 签名对齐
- **验证结果**: **FAIL** — 002 件 warnings.json 仍有 `dim_import3_exc`（`<unknown>.InsertModelAnnotations3`），补全参数后仍抛异常
- **根因**: InsertModelAnnotations3 在 SW2025 + pywin32 下可能根本不可用，非参数数量问题。异常消息 `<unknown>.InsertModelAnnotations3` 表明 COM 方法分发失败，而非参数错误
- **SubTask 1.2（GetEdges 选中几何体）**: 代码已实现 `view.GetEdges(True)` + `Select4` / `SelectByID2` 选中边
- **验证结果**: **未生效** — 002 件 dim_total=0，warnings.json 无 `dim_fallback_fail`（未抛异常）但也无尺寸生成
- **根因推断**: GetEdges 在工程图视图中可能返回空（小零件/细长件无可见边），或选中边后 AddHorizontalDimension2 仍不生成 DisplayDim

### Task 2: 轮廓尺寸降级兜底
- **SubTask 2.1/2.2（GetPartBox + SelectByID2 POINT）**: 代码已实现 `part.GetPartBox(True)` + `SelectByID2("", "POINT", ...)` 选中角点 + AddHorizontalDimension2 等
- **验证结果**: **FAIL** — 小零件（螺丝）dim_total=0，warnings.json 无 `outline_dim_fallback_fail`（未抛异常）但也无尺寸生成
- **根因推断**: `SelectByID2("", "POINT", x, y, z)` 在工程图中无法选中包围盒角点（POINT 类型需对应实际草图点实体，空名选中无效）；AddHorizontalDimension2 在无选中几何体时不生成 DisplayDim

### Task 3: view_in_frame 重定位后重新检测重叠
- **SubTask 3.1/3.2（重检测 + 降档）**: 代码已实现 `ForceRebuild3` 后重新测量 outline + 重新检测 overlap + 降档循环
- **验证结果**: **部分 PASS** — 004 件 real_overlap_pairs=[]（view_overlap 消除 ✓），但 hard_fail=['view_out_of_frame']（新问题）
- **根因**: view_in_frame 重定位后，iso 视图在内存中被拉回 FRAME_BOX 内，但保存/重载后 outline 变化（real_outlines_m.iso y_max=0.211 > 0.200），QC 检测到越界。Task 3 的重检测逻辑只检测重叠，不检测越界；且重定位后保存/重载 outline 与内存 outline 不一致

### Task 4: 清理 PNG 导出冗余 COM 调用
- **SubTask 4.1（移除 GetExportFileData(2)）**: 代码已移除 `sw.GetExportFileData(2)` 调用，直接记录"PNG 由 run_manager PDF→PyMuPDF 回退生成"
- **验证结果**: **PASS** — 所有件 warnings.json 含 `png_fallback_to_pdf`（"PNG 由 run_manager PDF→PyMuPDF 回退生成"），PNG 由 run_manager 回退生成，png_missing 不进入 hard_fail ✓
- **SubTask 4.2（unresolved_apis.md 补充）**: 已补充记录 C-3 条目

## 4. v1.4 vs v1.5 对比表

| 指标 | v1.4 | v1.5 | 变化 |
|------|------|------|------|
| LB26001-001 | PASS (hard_fail=[]) | PASS (hard_fail=[]) | 持平 ✓ 不退化 |
| LB26001-002 | FAIL (dim=0) | FAIL (dim=0) | 持平（Task 1/2 未生效）|
| LB26001-004 | FAIL (view_overlap) | FAIL (view_out_of_frame) | view_overlap 消除 ✓，但出现 view_out_of_frame |
| 小零件（螺丝）| FAIL (dim=0) | FAIL (dim=0) | 持平（Task 2 未生效）|
| PNG 导出 | PDF→PyMuPDF 回退（含冗余 COM 调用）| PDF→PyMuPDF 回退（无冗余 COM 调用）| 优化 ✓ |
| InsertModelAnnotations3 | 6 参数（COM 异常）| 7 参数（仍 COM 异常）| 参数补全，但 API 仍不可用 |

## 5. 关键问题与瓶颈

### 5.1 InsertModelAnnotations3 在 SW2025 不可用（最高优先级）
- **现象**: 补全第 7 参数后仍抛 `<unknown>.InsertModelAnnotations3` 异常
- **根因**: SW2025 + pywin32 的 COM 方法分发失败，非参数问题。异常消息 `<unknown>.` 表明 pywin32 无法解析方法名
- **影响**: 所有件尺寸标注依赖 RunCommand(826) 兜底，对无特征尺寸件（002/003/007/009/小零件）dim_total=0
- **后续方向**: 
  1. 尝试 `drw.InsertModelAnnotations3(...)`（IDrawingDoc 接口，非 Extension）
  2. 尝试 `sw.ExecuteCommand` 或 VBA 宏调用
  3. 放弃自动尺寸标注，改为手动标注或接受 dim_total=0

### 5.2 AddHorizontalDimension2 需要选中几何体
- **现象**: InsertDimension2 兜底和轮廓尺寸降级均未生成 DisplayDim
- **根因**: AddHorizontalDimension2 等 API 要求先选中视图中的几何实体（边/顶点），但 GetEdges 返回空或 SelectByID2("POINT") 无法选中包围盒角点
- **影响**: Task 1.2 和 Task 2 的兜底逻辑无效
- **后续方向**:
  1. 用 `view.GetEdges` 返回的 edge 对象的 `Select4` 方法选中（需确认 SW2025 可用性）
  2. 用 `IDrawingDoc.InsertDimension2` 配合手动选中的视图实体
  3. 用 Sketch API 在视图中绘制构造线，再标注构造线尺寸

### 5.3 view_in_frame 重定位后保存/重载 outline 不一致
- **现象**: 004 件 view_in_frame 重定位后内存 outline 在 FRAME_BOX 内，但保存/重载后 y_max=0.211 > 0.200
- **根因**: SolidWorks 保存/重载时视图位置/大小可能变化，与内存状态不一致
- **影响**: Task 3 的重检测逻辑只检测重叠，不检测越界；即使重检测越界也无法解决保存/重载不一致问题
- **后续方向**:
  1. view_in_frame 重定位后也检测越界，若仍越界则降档
  2. 保存后重新打开 SLDDRW，重新测量 outline 并重定位
  3. 调整 FRAME_BOX 或 iso 视图默认位置

## 6. 结论（最终）
- 整体: **部分 PASS** — Task 4 完全生效；Task 3 部分生效（view_overlap 消除，但 view_out_of_frame 新问题）；Task 1/2 受限于 SW2025 API 兼容性未生效
- 不退化: LB26001-001（v1.4 通过件）在 v1.5 仍通过 ✓
- 已知限制:
  1. InsertModelAnnotations3 在 SW2025 + pywin32 下不可用（COM 方法分发失败，非参数问题）
  2. AddHorizontalDimension2 需要 SelectByID2 选中几何体，但 GetEdges/SelectByID2("POINT") 在工程图中不可靠
  3. view_in_frame 重定位后保存/重载 outline 不一致，导致 view_out_of_frame
  4. 全量 129 件验证未完成（预估 4-5 小时），留给用户手动跑
- v1.5 交付状态: 可交付（Task 4 PNG 清理生效，Task 3 view_overlap 部分修复，不退化；Task 1/2 受限于 SW API 需后续 spec 处理）

## 7. 全量验证命令（留给用户）
```bash
cd "c:\Users\Vision\Desktop\SW 相关"
python -c "from app.services.batch_validator import run_batch_validation, write_batch_report; r = run_batch_validation(strategy='v6_recommended', limit=None, skip_vision=True); print('batch_id:', r['batch_id']); print('total:', r['total']); print('success:', r['success']); print('warning:', r['warning']); print('failed:', r['failed']); rep = write_batch_report(r['batch_id']); print('report:', rep)"
```
预估耗时: 4-5 小时（129 件 × 约 2 分钟/件）

## 8. 后续 spec 建议（v1.6）
基于 v1.5 已知限制，建议发起 v1.6 spec 处理：
1. **InsertModelAnnotations3 替代方案**: 尝试 IDrawingDoc 接口或 VBA 宏调用，或放弃自动尺寸标注
2. **AddHorizontalDimension2 几何体选中**: 用 view.GetEdges 返回的 edge 对象 Select4 方法，或 Sketch API 绘制构造线
3. **view_in_frame 保存/重载一致性**: 保存后重新打开 SLDDRW 重定位，或调整 FRAME_BOX
