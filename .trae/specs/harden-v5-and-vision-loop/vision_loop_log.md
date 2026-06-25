# Vision Loop Log

- 零件: `LB26001-A-04-001.SLDPRT`
- 开始: 2026-06-18 12:29:10.859042
- 阈值: 80


## 第 1 轮

- SLDDRW: `c:\Users\Vision\Desktop\SW 相关\drw_output\v5\LB26001-A-04-001_v5.SLDDRW`
- qc.json: `c:\Users\Vision\Desktop\SW 相关\drw_output\v5\LB26001-A-04-001_v5_qc.json`
- quality_check: 11/12
- vision_score: **35/100**
- issues:
  - `gb_titlebar_complete`: 标题栏缺失品名/机型、图号、材质、数量、设计、日期共6项GB要求的核心字段，未规范放置在图纸右下角，也未标注第一角投影符号
  - `gb_has_section_view_or_skipped`: 未绘制剖视图，无法清晰表达零件内部结构，不符合GB视图表达要求
  - `refdoc_correct`: 共4个视图缺失对应的三维模型引用，视图合法性不足
  - `has_datum_a`: 仅存在基准A的标识符号，无对应基准定义框，也未关联对应的形位公差标注
  - `has_ra_note`: 粗糙度其余标注不符合GB/T 131-2006规范格式要求
  - `has_tech_note`: 技术要求板块不符合规范，必填关键字缺失
- summary: 本图11项基础检查合规，6项核心检查不通过，存在标题栏核心字段缺失、无剖视图、视图缺失模型引用、基准/粗糙度/技术要求不规范等问题，不符合GB机械制图规范，不通过，需全面整改。

---

## 最终结果

- best_score: **35/100**
- best_slddrw: `c:\Users\Vision\Desktop\SW 相关\drw_output\v5\LB26001-A-04-001_v5.SLDDRW`
- best_vision_json: `c:\Users\Vision\Desktop\SW 相关\drw_output\v5\LB26001-A-04-001_v5_vision.json`
- quality_check 通过项数: 11/12
- 状态: **FAIL（已达上限）**
- 结束时间: 2026-06-18 12:30:10.599478
