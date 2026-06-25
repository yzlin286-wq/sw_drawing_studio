# Tasks

- [x] Task 1: drw_qc_loop_v6 强制绝对路径
  - [x] SubTask 1.1: 入口 `part_path = str(Path(part_path).resolve())`
  - [x] SubTask 1.2: subprocess 命令传给 v6 出图器的 part_path 用绝对路径
  - [x] SubTask 1.3: 加 `[qc_loop_v6] absolute part_path=...` 日志

- [x] Task 2: drw_quality_check refdoc 升级
  - [x] SubTask 2.1: 抽出 `_get_view_ref_model_path(view)` 工具函数（ReferencedDocument 优先 + GetReferencedModelName 兜底）
  - [x] SubTask 2.2: `_check_refdoc_correct` 用文件名 lowercase 匹配 expected_part；新增 `name_match` 字段
  - [x] SubTask 2.3: pass 判定改为 `name_match >= 1` OR `ReferencedDocument 非空 ≥ 1`

- [x] Task 3: v6 SaveAs 前 ReplaceViewModel
  - [x] SubTask 3.1: 在 v6 [9.7/9] rebind 块之后、SaveAs 之前，收集 created_views 名字
  - [x] SubTask 3.2: 调 `drw.ReplaceViewModel(part_abs_path, view_names, instances)`，失败 try/except + log
  - [x] SubTask 3.3: ForceRebuild3 + GraphicsRedraw2 兜底

- [x] Task 4: 真实闭环 + 归档
  - [x] SubTask 4.1: SolidWorks 在线确认（pid 13472；不在则启动 + sleep 60）
  - [x] SubTask 4.2: 跑 `python .trae/specs/build-v6-and-validate-exe-ui/drw_qc_loop_v6.py "3D转2D测试图纸\\LB26001-A-04-001.SLDPRT"`
  - [x] SubTask 4.3: 跑 `_tmp_vision_probe.py` 重读 vision_score
  - [x] SubTask 4.4: 写 `.trae/specs/fix-refdoc-via-qc-and-paths/run_log.md`：含改动行号 / 闭环结果 / 阶段对比

# Task Dependencies
- Task 1 / 2 / 3 可并行（互不冲突）
- Task 4 依赖 Task 1 + 2 + 3
- Task 5 依赖 Task 4

- [x] Task 5: 修复 Task 4 暴露的 ReplaceViewModel 未触发问题（spec mode 第七步）
  - [x] SubTask 5.1: v6 [9.8/9] 改用 `drw.GetFirstView() + GetNextView()` 链表枚举视图名，**复用** [9.7/9] 已收集的 `view_names`（提到外层变量）
  - [x] SubTask 5.2: 视图链表如仍失败，再用 created_views 列表（v6 创建视图时记录的 view 对象）兜底
  - [x] SubTask 5.3: 重跑 v6 闭环 1 轮 + vision_score；据结果勾选 checklist 8/9 两项
