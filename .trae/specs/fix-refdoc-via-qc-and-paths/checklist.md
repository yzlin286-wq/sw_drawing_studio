# Checklist

- [x] `drw_qc_loop_v6.py` 入口绝对路径转换；日志含 `[qc_loop_v6] absolute part_path=...`
- [x] `drw_qc_loop_v6.py` 子进程命令传给 v6 的 part_path 是绝对路径
- [x] `drw_quality_check.py` 含 `_get_view_ref_model_path(view)` 工具函数
- [x] `_check_refdoc_correct` 输出含 `name_match` 字段；pass 用名称匹配判定
- [x] `drw_generate_v6.py` SaveAs 之前调 `drw.ReplaceViewModel(...)`，失败不阻塞
- [x] AST 三脚本 parse ok
- [x] 真实闭环 v6 退出码 = 0
- [ ] `name_match ≥ 1/4` 或 `bad_ref ≤ 3/4` ❌ Task 5 二次验证 name_match=0/4, bad_ref=4/4：[9.7/9] 已成功收集 4 个视图名（`['工程图视图1'..'4']`），ReplaceViewModel 进入并以 4 个 view 调用，但 SW 返回 **False**，磁盘 SLDDRW 中 ref 仍为空。下一步建议走 spec 方向 C（VBA 宏 ReplaceViewModel）或 D（pywin32 EnsureDispatch 早期绑定），详见 run_log.md 节 E
- [x] vision_score ≥ 60 不退化（Task 4=55 → Task 5=65，回升 10 分，达到阈值）
- [x] qc_pass ≥ 11/12 不退化（实测 11/12）
- [x] `run_log.md` 含改动行号 + 闭环结果 + 阶段对比表
- [x] 原 `3D转2D测试图纸/` 目录文件未改动
