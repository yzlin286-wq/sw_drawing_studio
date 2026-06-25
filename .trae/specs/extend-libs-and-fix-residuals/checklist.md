# Checklist

- [x] `libs/research_notes.md` 含 Toolbox / BOM / 工艺 / 核价 4 节，每节 ≥ 3 来源链接
- [x] `libs/standard_parts/parts.yaml` ≥ 8 类、≥ 50 条；`standard_parts.db` 可被 `lookup()` 查询（Task 10.2 实跑：65 parts / 8 categories；lookup("GB/T 70.1","M5x16") 命中）
- [x] `libs/bom/extract_bom.py` 对 `LB26001-A-04-001.SLDPRT` 输出 `<base>_bom.csv` + `<base>_bom.xlsx`（Task 10.3 实跑 rows=1）
- [x] `libs/process/process.db` 含 ≥ 12 道工序记录；`suggest_route()` 返回钣金件路线（Task 10.2 实跑：12 processes inserted）
- [x] `libs/pricing/quote.py` 真实跑出 `<base>_quote.json` + `<base>_quote.md`，total_cny > 0（Task 10.4 实跑：total_cny=21.15）
- [x] GUI 多一项"BOM 与核价"导航；切换无崩溃（`app/ui/main_window.py` NAV_ITEMS L32 含 "BOM 与核价"）
- [x] v5 输出的 SLDDRW 标题栏 13 字段全部非空（即使源 SLDPRT 字段为空）（Task 10.5 实跑 QC `all_13_keys_present` pass=True 13/13）
- [x] `templates/macros/auto_section.bas` 文件存在；v5 在原生 section API 失败时尝试调用宏（drw_generate_v5.py L1024-L1044）
- [ ] v5 视图 `ReferencedConfiguration` 在 SaveAs 后非空（quality_check 的 refdoc_correct 部分项目通过）— Task 11 二次验证后仍未通过：v5 [9.7/9] 已在 SaveAs 之前调用 SetReferencedDocument + SetReferencedConfiguration（rebound 4 views），但 QC 仍报 4 视图 ref_doc 为空（残余原因：SW SaveAs 后 drawing 视图模型路径未持久化，需后续调整 part/drawing 关闭顺序与 SaveAs 时序）
- [x] v5 在基准 A 处插入了 GTol（quality_check 中 NoteBlock 数据含 GTol 标记或视图 annotation type=4）— Task 11 二次验证已通过：原生 `drw.InsertGtol()` 仍返回 None，已成功通过 InsertNote("⏥ 0.05 A") fallback 插入（drw_generate_v5.py [9/9] L1124-L1158；stdout 实测 `[gtol] fallback note '⏥ 0.05 A' inserted`）
- [x] `run_log.md` 含 4 节（标准件 / BOM / 核价 / v5 残余修复闭环结果）（`.trae/specs/extend-libs-and-fix-residuals/run_log.md`）
- [x] 原 `3D转2D测试图纸/` 目录文件未被改动（Task 10 全程仅作只读输入，所有输出均落到 `drw_output/`）
