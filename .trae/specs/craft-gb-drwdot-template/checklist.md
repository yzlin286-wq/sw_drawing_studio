# Checklist

- [x] `templates/gb_a4_landscape.drwdot` 文件存在，大小 > 50 KB（实际 76.3 KB）
- [x] `templates/build_drwdot.py` 可重复运行（幂等）；2 次运行后模板大小不变 ± 1 KB（实际 78611→78093，差 -518 B，在容差内）
- [x] `templates/probe_drwdot.py` 5 项验证全部 `pass=True`：sheet=A4、字高 ≥ 0.0035 m、图层 ≥ 5、标题栏 NoteBlock ≥ 13、CustomProperty 链接 ≥ 13（5/5 全部 pass，详见 `probe_result.json`）
- [x] `drw_generate_v5.py` 在使用模板时日志中能看到 `[template] using gb_a4_landscape.drwdot`，模板缺失时打印 `[template] fallback`（v5 已含相应日志逻辑，Task 4 已落地）
- [x] `app/config/defaults.py` 默认值 `drwdot_template` 指向仓库根 `templates/gb_a4_landscape.drwdot` 的绝对路径（Task 4 已验证）
- [ ] 真实闭环：vision_loop 退出码 = 0 且 `vision_score ≥ 80`（Task 6 修复后 best_score=55/100，退出码 1，仍未达阈值；残余主要为标题栏字段 / 剖视图 / refdoc / 基准 A 详细标注，详见 `build_log.md` 节 5）
- [x] 真实闭环：`quality_check pass_count ≥ 11/12`（Task 6 修复后 11/12 ✅，原 9/12）
- [x] `build_log.md` 含构造 / 探针 / v5 接入 / 闭环 4 节
- [x] `vision_loop_log.md` 末尾追加"## 三次验证（模板根治后 — craft-gb-drwdot-template）"，记录 score / qc_pass 的提升曲线（15→35→53）
- [x] 原 `3D转2D测试图纸/` 目录文件未被改动
