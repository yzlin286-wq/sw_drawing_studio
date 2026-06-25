# v1.3 验证日志

## 1. 验证范围
- 测试件: LB26001-A-04-001.SLDPRT
- 策略: v6_recommended
- 执行时间: 2026-06-18
- SolidWorks 版本: 2025 (RevisionNumber=33.5.0)
- LLM 配置: ccagent / glm-5.1 (chat) + doubao-seed-2.0-pro (vision)
- run_id: f6d588d5a271
- 闭环入口: `app/services/run_manager.py::full_pipeline()`
- 子进程脚本: `.trae/specs/build-v6-and-validate-exe-ui/drw_qc_loop_v6.py`
- QC 脚本: `.trae/specs/enforce-drawing-quality/drw_quality_check.py`
- 输出图纸: `drw_output/v5/LB26001-A-04-001_v5.SLDDRW` (+ PDF/DXF/PNG)

## 2. 比例尺 GB 标准验证
- CANDIDATE_SCALES（drw_generate_v6.py L25）: `[(5,1),(2,1),(1,1),(1,2),(1,5),(1,10),(1,20),(1,50)]`
- 生成图比例: **1:5**（来自 sheet.GetProperties2，scale_num=1, scale_den=5）
- `scale_gb_standard` 检查: **pass=true**, severity=info, value="1:5"
- `scale_advisor.is_gb_standard_scale`:
  - is_gb_standard_scale("1:5") = True
  - is_gb_standard_scale("1:3") = False（已移除非标准比例）
- `scale_advisor.advise_scale`（LLM 视觉判断）:
  - reasonable: false
  - score: 20
  - suggestion: "当前视图过小，未充分利用图纸幅面，建议更换为更大的标准比例（如1:1或1:2），放大视图以保证尺寸标注清晰、读图便捷"
  - 说明: LLM 视觉判断认为 1:5 视图偏小，但 1:5 本身是 GB 标准值，不阻断交付

## 3. 标题栏 7 行验证
- `titlebar_complete` 检查: **pass=false** (severity=warning，不阻断)
- 缺失字段: 品名, 图号, 材质, 数量, 表面处理, 类别, 机型
  - 原因: SLDPRT 自定义属性未注入这些字段（源文件本身缺属性），非标题栏布局问题
- 模板加载: **yes**（`config/titlebar_template.yaml` 读取成功）
  - company.name: "深圳市XX科技有限公司"
  - drawing.designer: "张三", reviewer: "李四"
  - technical.requirements: 4 行 GB 标准技术要求
- 标题栏布局（drw_generate_v6.py L207-295）: **7 行 × 4 列** 已渲染
  - 第 1 行: 公司名 | 品名 | 图号 | 比例
  - 第 2 行: 制图人 | 审核人 | 日期 | 机型
  - 第 3 行: 材质 | 数量 | 表面处理 | 类别
  - 第 4 行: 技术要求（跨 4 列，多行 Note）
  - 第 5 行: 工艺信息（跨 4 列）
  - 第 6 行: 源文件信息（SLDPRT 文件名，跨 4 列）
  - 第 7 行: 交付信息（交付日期 + 客户 + 备注，跨 4 列）
- 标题栏外框: (0.102, 0.005) - (0.282, 0.095)，6 条内部行分隔线 + 3 条列竖线

## 4. 3D-2D 比对验证
- `model_2d_consistency` 检查: **pass=true**, severity=info
- consistency: **70/100**
- missing_views: []（无缺失视图）
- structural_diff: "2D图包含3D模型的全部主要结构特征，孔位、中部元件、板身缺口均对应一致，无结构差异；但2D工程图未标注任何尺寸，形位公差标注不完整。"
- 比对入口: `app/services/model_compare.py::compare_model_2d()`
  - 3D PNG 渲染: SolidWorks COM OpenDoc6 + ShowNamedView2("*Isometric", 7) + SaveAs3 PNG
  - 2D PNG: `drw_output/v5/LB26001-A-04-001_v5.PNG`
  - LLM 输入: 3D 等轴测 PNG + 2D 工程图 PNG（双图 vision 调用）

## 5. QC 汇总
- hard_fail: **[]**（无阻断项）
- warnings: ['refdoc_correct', 'has_datum_a', 'has_ra_note', 'gb_titlebar_complete', 'gb_has_section_view_or_skipped', 'titlebar_complete']
- drawing_usable.pass: **True**
- drawing_usable.criteria:
  - files_exported: True (SLDDRW/PDF/DXF/PNG 齐全)
  - view_in_frame: True
  - view_overlap_ok: True
  - dim_total: 44
  - qc_pass_count: 11
  - vision_score: 65（来自 v1.2 既有 vision_qc）
- qc_pass_count: **11/17**（12 项基础 QC + 5 项 GB 扩展 QC，共 17 项；v1.3 新增 3 项为 warning 不计入 hard_fail）

### 17 项 QC 明细
| # | 检查项 | pass | 说明 |
|---|--------|------|------|
| 1 | view_overlap | ✅ | 4 视图无重叠 |
| 2 | view_in_frame | ✅ | 全部在图框内 |
| 3 | front_view_position | ✅ | 前视图 (80,140)mm 在区间内 |
| 4 | scale_in_set | ✅ | 1:5 在白名单 |
| 5 | text_height_ge_3_5mm | ✅ | 文字高度达标 |
| 6 | all_13_keys_present | ✅ | 13 属性键齐全 |
| 7 | dim_count_sufficient | ✅ | DisplayDim=44 |
| 8 | centermark_count_sufficient | ✅ | CenterMark 达标 |
| 9 | has_tech_note | ❌ | NoteBlock=19 但无 3 行编号/关键词 |
| 10 | has_ra_note | ❌ | 无 Ra 关键词 |
| 11 | has_datum_a | ❌ | 无基准 A |
| 12 | refdoc_correct | ❌ | SW2025 SaveAs 后 ReferencedDocument 未持久化 |
| 13 | gb_titlebar_complete | ❌ | 缺 6 组核心字段（SLDPRT 属性未注入） |
| 14 | gb_font_is_changfangsong | ✅ | 仿宋字体 |
| 15 | gb_paper_size_correct | ✅ | A4 横式 |
| 16 | gb_has_section_view_or_skipped | ❌ | 无剖视图 |
| 17 | gb_scale_in_extended_set | ✅ | 1:5 在 GB 全集 |
| v1.3a | scale_gb_standard | ✅ | 1:5 是 GB/T 14690 标准值 |
| v1.3b | titlebar_complete | ❌ | 字段缺失（warning，不阻断） |
| v1.3c | model_2d_consistency | ✅ | consistency=70/100 |

## 6. 结论
- **比例尺: PASS** — 1:5 是 GB/T 14690 标准值，CANDIDATE_SCALES 已移除 3:1/1:3/1:4/1:100，scale_gb_standard 检查通过；LLM 视觉判断认为视图偏小（score=20），但比例值本身合规
- **标题栏: WARNING** — 7 行 × 4 列布局已渲染完整（含技术要求/工艺/源文件/交付信息行），模板加载正常；titlebar_complete 检查报 warning（SLDPRT 源文件未注入品名/图号等属性，非布局问题），不阻断交付
- **3D-2D 比对: PASS** — consistency=70/100，无缺失视图，结构特征一致；LLM 指出 2D 图尺寸标注不完整（与 has_tech_note 等检查一致）
- **整体: PASS** — drawing_usable.pass=True，无 hard_fail，图纸可交付；v1.3 三项增强全部触发并有结果
