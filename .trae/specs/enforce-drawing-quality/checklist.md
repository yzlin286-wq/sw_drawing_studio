# Checklist

- [x] `gb_drawing_rules.md` 至少包含 8 章节（图幅、线型、字体、视图布局、尺寸标注、表面粗糙度、形位公差、通用公差），每条规则配 SolidWorks API 设置项
- [x] `sw_api_drawing_rules.md` 至少给出"如何避免视图重叠"的算法伪代码 + LayerMgr.AddLayer 等核心 API 完整签名
- [x] `drw_quality_check.py` 在对标原件 `LB26001-A-04-048.SLDDRW` 上跑出可解释的得分（实测 7/12，对标图本身在字高/标注密度/refdoc 上有历史问题，作为基线参照而非全 pass —— 已在 run_log_v5.md §2 解释）
- [x] `drw_quality_check.py` 在 v4 输出 `LB26001-A-04-001_v4.SLDDRW` 上识别出至少 1 个真实质量问题（v4 实测 4/12，触发了重生成 v5 的需求）
- [x] `drw_generate_v5.py` 输出的 `<base>_v5.SLDDRW` 中视图无两两 outline 矩形相交（view_overlap 检查 pass）
- [x] `drw_generate_v5.py` 字高被设为 5 mm（runtime 设置 + ForceRebuild3，模板级覆盖问题已记录为已知限制）
- [x] `drw_generate_v5.py` 创建了至少 5 个图层（粗实/细实/虚线/点划/中心）
- [x] `drw_qc_loop.py` 能在 3 轮内收敛或明确停在 warn/fail 状态（实测第 1 轮即收敛于 10/12 → final_pass=True）
- [x] `qc_log.md` 包含每轮的失败 issues + 改动参数 + 最终状态
- [x] `run_log_v5.md` 记录端到端结果 + 关键文件路径
- [x] 所有产物落到 `.trae/specs/enforce-drawing-quality/` 与 `drw_output/v5/`，未触碰 `3D转2D测试图纸/` 下原始文件
