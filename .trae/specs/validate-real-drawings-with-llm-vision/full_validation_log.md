# v1.2 全量验证日志

## 1. 验证范围

- 目录: `3D转2D测试图纸/`
- SLDPRT 总数: 129（已排除 `~$` 临时文件）
- 执行时间: 2026-06-18 19:25:33 → 2026-06-18 22:26:12（约 3 小时）
- 策略: `v6_recommended`
- batch_id: `f42afb249fa7`
- SolidWorks 版本: 33.5.0（SolidWorks 2025）
- LLM 模型: `doubao-seed-2.0-pro`（vision）
- 阶段 1: 全量出图 + QC + BOM + 报价（skip_vision=True）
- 阶段 2: 对 success/warning 件跑 `vision_score_with_reference()`
- 阶段 3: 生成 `batch_report.md` + 归档

产物路径:
- `drw_output/batch_validation/f42afb249fa7/batch_summary.json`
- `drw_output/batch_validation/f42afb249fa7/batch_report.md`

## 2. 验证结果汇总

- total: 129
- success: 0
- warning: 1
- failed: 128
- 通过率: 1/129 (0.8%)

| 状态 | 数量 | 占比 |
|------|------|------|
| success | 0 | 0.0% |
| warning | 1 | 0.8% |
| failed | 128 | 99.2% |

## 3. vision_score 统计

阶段 2 仅对 1 个 warning 件（LB26001-A-04-001）跑了 vision。

- 有 vision_score 的件数: 1
- 最高分: 55
- 最低分: 55
- 平均分: 55
- 阈值: 60（pass=False）

### Top 5 vision_score
| 排名 | 零件 | score | status |
|------|------|-------|--------|
| 1 | LB26001-A-04-001 | 55/100 | warning |

### Bottom 5 vision_score
| 排名 | 零件 | score | status |
|------|------|-------|--------|
| 1 | LB26001-A-04-001 | 55/100 | warning |

> 说明：仅 1 件进入 vision 阶段，故 top/bottom 均为该件。

## 4. 对标差异统计

- 有 reference_diff 的件数: 1
- 平均 similarity: 40

### LB26001-A-04-001 对标详情
- similarity: 40/100
- structural_diff: 生成图采用轴测图+双侧视图+俯视图+空白标题栏的分散布局；参考案例仅保留主俯视图与单一侧视图，聚焦孔位标识与附加说明，无轴测图与空白标题栏区块
- missing_elements:
  - 孔位基准标签(A/B/C/D/E/F/G/H)
  - X/Y/0坐标轴定位标注
  - "未标注尺寸按3D加工"提示文本
  - 硬盘槽位更新说明文本
  - "未注尺寸请核对3D图档"提示文本

## 5. 失败清单

共 128 件 failed。失败原因（hard_fail）统计：

| hard_fail 原因 | 数量 | 占失败件占比 |
|----------------|------|--------------|
| png_missing | 128 | 100.0% |
| dim_total_too_low | 116 | 90.6% |
| qc_pass_too_low | 104 | 81.3% |
| view_overlap | 1 | 0.8% |

### qc_pass_count 分布

| qc_pass_count | 数量 |
|---------------|------|
| 7 | 15 |
| 9 | 89 |
| 10 | 22 |
| 11 | 3 |

### 失败模式分类

1. **三重失败**（png_missing + dim_total_too_low + qc_pass_too_low）: 104 件，占 81.3%
   - 这是最典型的失败模式，PNG 导出失败 + 无尺寸 + QC 通过数不足
2. **png_missing + dim_total_too_low**: 12 件（qc_pass_count=10，仅差 1 分达 11 阈值）
3. **仅 png_missing**（无其他 hard_fail）: 3 件
   - LB26001-A-04-008 (qc=11)
   - LB26001-A-04-015 (qc=11)
   - LB26001-A-04-036 (qc=10)
   - 这 3 件 QC 质量已达标，仅因 PNG 导出失败而被判 failed，是最接近通过的件
4. **png_missing + view_overlap**: 1 件（LB26001-A-04-004）

### 全量 warnings 统计（129 件全部命中）

| warning 原因 | 数量 | 说明 |
|--------------|------|------|
| refdoc_correct | 129 | SW2025 SaveAs 后 ReferencedDocument 未持久化（平台限制） |
| has_datum_a | 129 | 未识别基准 A 标识 |
| has_ra_note | 129 | 粗糙度统一标注不符合 GB/T 131-2006 |
| gb_titlebar_complete | 129 | 标题栏缺 6 组核心字段 |
| gb_has_section_view_or_skipped | 129 | 无剖视图 |

> 注：error 字段（pipeline 异常）非空件数 = 0，说明所有失败均由 QC hard_fail 判定，非程序异常。

## 6. 典型成功案例

### 案例 1: LB26001-A-04-001（唯一 warning 件）

- run_id: `8823efa974a9`
- status: warning（无 hard_fail，有 5 个 warnings）
- qc_pass_count: 11/12
- dim_total: 44（全量中唯一有尺寸标注的件）
- drawing_usable.pass: true
- files_exported: true（SLDDRW + PDF + DXF + PNG 齐全）
- vision_score (with_reference): 55/100
- reference_diff.similarity: 40/100
- bom_status: ok
- process_status: ok
- quote_status: ok total=21.15
- fallback_used: false（使用 v6，未回退 v5）

**vision 评分主要扣分项**:
1. 标题栏缺失 6 组核心字段（品名/图号/材质/数量/设计/日期）
2. 未绘制剖视图
3. 未标注基准 A
4. 引用文档名称匹配度为 0（refdoc 平台限制）
5. 技术要求区块未包含关键字
6. 粗糙度统一标注不符合 GB/T 131-2006

**对标差异**: 生成图布局分散（轴测图+双侧视图+俯视图+空白标题栏），案例图聚焦主俯视图+单一侧视图+孔位标识，相似度仅 40。

### 案例 2: LB26001-A-04-008 / 015（接近通过，仅缺 PNG）

- status: failed（hard_fail=[png_missing]）
- qc_pass_count: 11/12
- 这 2 件 QC 质量与 LB26001-A-04-001 相同（qc=11），仅因 PNG 导出失败被判 failed
- 若修复 PNG 导出，预计可升为 warning

## 7. 已知限制

### 7.1 PNG 导出失败（最主要瓶颈）
- 128/129 件 PNG 导出失败（png_missing）
- 根因：v6 pipeline 的 PNG 导出依赖 PDF→PNG 转换（PyMuPDF），但多数件 PDF 未生成或转换失败
- 影响：直接导致 128 件被判 failed；其中 3 件（LB26001-A-04-008/015/036）仅因此项失败
- vision_score_with_reference 也依赖 PNG，故仅 1 件能跑 vision

### 7.2 尺寸标注缺失
- 116/129 件 dim_total=0（无任何尺寸标注）
- 根因：v6 pipeline 调用 `RunCommand(826) InsertModelAnnotations` 在 SW2025 + pywin32 环境下未生效
- 仅 LB26001-A-04-001 成功插入尺寸（dim_total=44），该件原本已有 SLDDRW 工程图

### 7.3 QC 通过率低
- 104/129 件 qc_pass_count < 阈值（11）
- qc_pass_count 分布集中在 9（89 件），距阈值 11 差 2 分
- 主要扣分项：dim_count_sufficient、centermark_count_sufficient、has_tech_note、has_ra_note、has_datum_a、gb_titlebar_complete、gb_has_section_view_or_skipped

### 7.4 GB 合规项普遍不达标（129/129 件命中 5 项 warning）
- **refdoc_correct**: SW2025 + pywin32 平台限制，SaveAs 后 view.ReferencedDocument 未持久化，无法修复（建议作为警告不阻断交付）
- **gb_titlebar_complete**: 标题栏 6 组核心字段全空，CustomProperty 未注入到模板 $PRP 占位符
- **gb_has_section_view_or_skipped**: 无剖视图，auto_section.bas 宏未触发
- **has_datum_a**: 未标注基准 A
- **has_ra_note**: 粗糙度统一标注缺失

### 7.5 vision 对标相似度低
- 仅 1 件有 reference_diff，similarity=40/100
- 生成图与人工案例图布局差异大：生成图含轴测图+空白标题栏，案例图聚焦孔位标识

### 7.6 案例库覆盖有限
- 案例库仅覆盖 40 个有 SLDDRW 的件（主要是 LB26001-A-04-* 系列）
- 129 个 SLDPRT 中多数无对应案例图，vision_score_with_reference 退化为单图评分

## 8. 结论

### 8.1 软件可用性评估

| 能力 | 评估 | 说明 |
|------|------|------|
| SLDDRW 出图 | 基本可用 | 129 件均生成 SLDDRW |
| PDF/DXF 导出 | 大部分可用 | 多数件有 PDF/DXF |
| PNG 导出 | 不可用 | 128/129 件失败（主要瓶颈） |
| 尺寸自动插入 | 不可用 | 116/129 件 dim_total=0 |
| BOM 提取 | 可用 | 129 件均完成 |
| 工艺路线 | 可用 | 129 件均完成 |
| 报价计算 | 可用 | 129 件均完成 |
| QC 评分 | 部分可用 | 评分逻辑可用，但依赖尺寸/PNG |
| LLM vision | 可用 | doubao-seed-2.0-pro 链路正常 |
| 案例对标 | 受限 | 仅 1 件能跑双图对比 |

**整体结论**: v1.2 的批量验证框架（batch_validator + run_manager + vision_qc）链路完整可用，能稳定跑完 129 件不崩溃（耗时 3 小时，0 异常）。但底层出图质量（PNG 导出 + 尺寸插入 + GB 合规）存在系统性缺陷，导致通过率仅 0.8%。LLM vision 链路本身可用，但因 PNG 导出失败而无法大规模验证。

### 8.2 建议改进方向

1. **修复 PNG 导出（最高优先级）**：排查 PDF→PNG 转换失败原因；或改用 SolidWorks COM 直接导出 PNG（`Extension.SaveAs` + `swExportPngData`）；预计可挽救 3 件仅因 png_missing 失败的件，并解锁 vision 大规模验证
2. **修复尺寸插入**：排查 `RunCommand(826) InsertModelAnnotations` 在 SW2025 的调用方式；或改用 `InsertDimension2` 逐个插入；这是提升 dim_total 和 qc_pass_count 的关键
3. **完善标题栏**：确保 13 个 CustomProperty 注入完成且 SLDDRW 链接到模板 `$PRP` 占位符
4. **补充剖视图**：对需要剖视的零件运行 `auto_section.bas` 宏
5. **补充基准 A / 粗糙度标注**：通过 `InsertDatumTag2` 和 NoteBlock 补充
6. **refdoc_correct**：SW2025 平台限制，建议作为警告不阻断交付（v1.1 已采用此策略）
7. **扩展案例库**：对更多件渲染案例 PNG，提升 vision 对标覆盖率

### 8.3 验收状态

- [x] 全量验证（129 个 SLDPRT）执行完成
- [x] `batch_summary.json` + `batch_report.md` 生成
- [x] `full_validation_log.md` 归档
- [x] tasks.md Task 6 全勾选
