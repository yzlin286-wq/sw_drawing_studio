# Tasks

- [x] Task 1: 提前编译 VBA .swp
  - [x] SubTask 1.1: 写 `templates/macros/precompile_swp.py`，尝试 `sw.RunMacro2(.bas, "auto_section", "main", 1, 0)` 触发 SW 内部转译并复制结果文件
  - [x] SubTask 1.2: 真实跑 precompile，记录是否生成 .swp；若失败给出 ui_acceptance.md 中的"用户手动一次性编译"指引

- [x] Task 2: 写 v6 出图器
  - [x] SubTask 2.1: 把 v5 复制到 `.trae/specs/build-v6-and-validate-exe-ui/drw_generate_v6.py`
  - [x] SubTask 2.2: 改"视图布局"块：4 视图按 T 字布局 + 自动 outline + 重叠降比例至 1:50
  - [x] SubTask 2.3: 加"二次 RunCommand(826)" + sleep + ForceRebuild3
  - [x] SubTask 2.4: 在 part 打开后立即 `_cached_cfg_name = part.GetActiveConfiguration().Name`，所有 SetReferencedConfiguration 用缓存值
  - [x] SubTask 2.5: VBA .swp 缺失时回退 .bas（已有 v5 兜底逻辑保留）

- [x] Task 3: 写 v6 闭环器
  - [x] SubTask 3.1: 把 `drw_qc_loop.py` 复制为 `drw_qc_loop_v6.py`，子进程入口改为调 v6 出图器
  - [x] SubTask 3.2: 输出文件名仍用 `<base>_v5.SLDDRW`（保持向后兼容；不破坏 quality_check 路径推断）

- [x] Task 4: sw_runner 切换到 v6
  - [x] SubTask 4.1: 修改 `app/services/sw_runner.py`：优先 `drw_qc_loop_v6.py`，缺失或 env `USE_V5=1` 回退 v5
  - [x] SubTask 4.2: 加 `[runner] using v6` / `[runner] using v5 fallback` 日志

- [x] Task 5: 重新打包 EXE
  - [x] SubTask 5.1: 检查 build_exe.spec 是否包含新增 `app/ui/bom_pricing_page.py`、`libs/`（若需要）
  - [x] SubTask 5.2: 跑 `pyinstaller --noconfirm build_exe.spec`
  - [x] SubTask 5.3: 验证产物大小、smoke 启动 5 秒不崩

- [x] Task 6: EXE UI 全面验收
  - [x] SubTask 6.1: 启动 EXE，依次切换 6 项导航并截图
  - [x] SubTask 6.2: 在 BOM 页点 4 按钮（打开 / AI 工艺建议 / 生成报价 / 导出），逐项截图与日志
  - [x] SubTask 6.3: 在质检页点 3 按钮（选择 SLDDRW / AI 视觉质检 / AI 生成技术要求），逐项截图
  - [x] SubTask 6.4: 打开设置对话框 3 Tab（模型 / 路径 / 并发），点击「测试连接」按钮，截图
  - [x] SubTask 6.5: 清单整理到 `ui_acceptance.md`：按钮 → 期望行为 → 实测结果 → 截图引用 → 通过/失败
  - [x] SubTask 6.6: 任何失败项立即修复（不要拖到下个 spec），修后再回归

- [x] Task 7: v6 真实闭环
  - [x] SubTask 7.1: SolidWorks 在线确认（已知 pid 13472）
  - [x] SubTask 7.2: 跑 `python .trae/specs/harden-v5-and-vision-loop/vision_loop.py LB26001-A-04-001.SLDPRT --max-rounds 2 --threshold 60`（阈值降到 60）
  - [x] SubTask 7.3: 记录 v6 退出码 / score / qc_pass / refdoc 视图非空数 / dim 数
  - [x] SubTask 7.4: 写 `run_log_v6.md` 含 4 节（v6 改动 / 闭环 / UI 验收摘要 / 阶段对比）

# Task Dependencies
- Task 2 与 Task 1 并行
- Task 3 依赖 Task 2
- Task 4 依赖 Task 3
- Task 5 依赖 Task 4
- Task 6 依赖 Task 5
- Task 7 依赖 Task 4
- Task 8 依赖 Task 7

- [x] Task 8: 修复 Task 7 暴露的 1 项 checklist 失败（spec mode 第七步）
  - [x] SubTask 8.1: 修 v6 的 `_cached_cfg_name`：当 `part.GetActiveConfiguration().Name` 为空字符串时，回退到 `"默认"` / `"Default"` 并尝试 `part.ConfigurationManager.ActiveConfiguration.Name`、再退到 `Path(sldprt).stem`
  - [x] SubTask 8.2: 跑 `_tmp_vision_probe.py` 重新读 `_v5_vision.json` 看 refdoc_correct 是否改善
  - [x] SubTask 8.3: 在 run_log_v6.md 末尾追加"## 节 E 二次验证"，据结果勾选 checklist 第 5 项
