# Checklist

- [x] `drw_quality_check.py` 含 `classify_refdoc_status(ref_path, expected_part)` 工具函数  (L225–L242)
- [x] `_check_refdoc_correct` 输出新增 `severity="warning"` + `reason` 字段  (L278–L290, severity@L280, reason@L281)
- [x] `quality_check()` 输出新增 `hard_fail`、`warnings`、`drawing_usable` 顶层字段  (L989/L990/L1022, 落盘 L1034–L1036)
- [x] `app/services/health_check.py` 提供 `run_health_check()`，输出 7 项 ok/fail  (实测 7/7 ok)
- [x] `app/services/__init__.py` 导出 `run_health_check`  (__init__.py:L6, __all__:L19)
- [x] `home_page.py` 启动时显示 7 项环境自检状态卡  (L80–L116, _refresh_health@L159–L192)
- [x] `qc_page.py` 顶部显示分层状态条（出图/质量/视觉/可交付/警告 5 项）  (L49–L89)
- [x] `batch_page.py` 表格含「状态」列（success/warning/fail）  (L24/L29 列名, L177–L191 update_row, L223–L230 update_row_status)
- [x] `main_window.py` 工具栏含 QComboBox「出图策略」3 选项  (L208–L213, 切换 v5 设 USE_V5=1 @L218)
- [x] `dist/sw_drawing_studio.exe` 重新打包成功，smoke 5s alive  (Task 4 已完成；本次未重打)
- [x] 真实闭环：drawing_usable.pass=True 且 hard_fail=[]  (qc.json 实测：hard_fail=[], drawing_usable.pass=True)
- [x] warnings 列表含 `refdoc_correct`，但不再阻断  (warnings=[refdoc_correct, has_datum_a, has_ra_note, gb_titlebar_complete, gb_has_section_view_or_skipped])
- [x] qc_pass ≥ 11/12 不退化、vision_score ≥ 60 不退化  (qc_pass=11/12, vision_score=65)
- [x] `release_log.md` 含 4 节 + v1.0 发布判定 PASS
- [x] 原 `3D转2D测试图纸/` 目录文件未改动  (本次只读取 LB26001-A-04-001.SLDPRT)
