# Checklist

- [x] `templates/macros/precompile_swp.py` 存在且能跑出 `auto_section.swp` 或给出明确手动指引
- [x] `.trae/specs/build-v6-and-validate-exe-ui/drw_generate_v6.py` 存在，AST parse ok
- [x] v6 视图布局：quality_check 的 view_overlap 与 view_in_frame 都 pass
- [x] v6 二次 RunCommand(826)：dim_total ≥ 5（实测 dim_total=44）
- [ ] v6 cfg_name 缓存：refdoc_correct 检查中至少 1 个视图 ReferencedConfiguration 非空（v6 已用 4 级回退缓存非空 cfg_name=`默认`，SetReferencedConfiguration 4/4 set_ok=True，但 SW SaveAs 后视图缓存路径仍清空，属 SW2025 持久化层硬限制；详见 run_log_v6.md 节 E）
- [x] `drw_qc_loop_v6.py` 存在，能被 sw_runner 子进程拉起
- [x] `app/services/sw_runner.py` 在 v6 存在时输出 `[runner] using v6`，否则 fallback 日志
- [x] `dist/sw_drawing_studio.exe` 重新打包成功，体积 ≤ 200 MB（131.7 MB），5 秒 smoke 启动不崩
- [x] EXE 6 项导航 ≥ 6 张截图，每项页面正常显示，无文字乱码 / 错位
- [x] BOM 与核价页 4 按钮（打开 / AI 工艺建议 / 生成报价 / 导出）全部可点、回调正常或弹出友好提示
- [x] 设置对话框 3 Tab 全部可切换；「测试连接」按钮真实调 LLM 返回 ok=True/False（实测 ok=True, latency=6832ms）
- [x] `ui_acceptance.md` 列出每按钮的期望/实测/截图引用
- [x] v6 真实闭环：vision_score ≥ 60 或 ≥ 55 但 refdoc 缓存生效（实测 65 ≥ 60 ✅）
- [x] `run_log_v6.md` 含阶段对比（extend Task 11 → v6 Task 7）
- [x] 原 `3D转2D测试图纸/` 目录文件未改动
