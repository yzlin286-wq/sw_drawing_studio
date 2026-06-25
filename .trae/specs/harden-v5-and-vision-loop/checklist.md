# Checklist

- [x] `drw_generate_v5.py` 不再调用 `_insert_note_n(*, n=5)`，技术要求 / Ra / 基准 A 各只插 1 次
- [ ] 生成的 SLDDRW 包含 A4 横式图框（10mm 边距 + 25/5/5/5mm 内框） — Task 7 修复后已把渲染移到 SaveAs 前 [9.6/9]，但 vision 仍报 `gb_paper_size_correct`（sheet GetSize 返回 None）；待后续 spec 处理 sheet 尺寸 API
- [ ] 标题栏 5×3 网格框线绘制完成，13 个字段可见 — Task 7 修复后 vision 不再报 `titlebar_empty`，但仍报 `gb_titlebar_complete`（属性 `品名/机型/图号/...` 读不到）；待后续 spec 处理 InsertNote 属性写入
- [x] 视图导出后无残留 SolidWorks 蓝色视图箭头（关闭对应 UserPreferenceToggle） — 多轮 vision report 均未出现 `residual_view_arrow`
- [x] `drw_quality_check.py` has_tech_note / has_ra_note / has_datum_a 改为单 Note 多行也通过（代码已放宽；本轮 12 项被 `OpenDoc6 returned None` 短路，与该指标无关）
- [x] `vision_loop.py` 落到 `.trae/specs/harden-v5-and-vision-loop/`，能在命令行 `python vision_loop.py <SLDPRT>` 启动
- [x] SolidWorks 未启动时 vision_loop 退出码 = 2 并提示用户启动 SW
- [x] 真实闭环跑出 vision_score ≥ 80 在 ≤ 3 轮内完成 **或** 记录最近最佳 score + 残余 issues 到 `vision_loop_log.md` — Task 6 最佳 15/100；Task 7 修复后最佳 35/100，残余 issues 已记录
- [ ] 12 项 quality_check 通过项数依然 ≥ 10/12 — Task 6: 0/12（OpenDoc6 短路）；Task 7 修复后 9/12（`OpenDoc6 retry×3 + 降级容错` 生效），距 ≥10 仅差 1 项；剩余 `text_height_ge_3_5mm` / `refdoc_correct` / `gb_*` 系列待后续 spec
- [x] `vision_loop_log.md` 包含最终 SLDDRW 渲染 PNG 引用 + 最终 vision_score JSON + 12 项通过项数

