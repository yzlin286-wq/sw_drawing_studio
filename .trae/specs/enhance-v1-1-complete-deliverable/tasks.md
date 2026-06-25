# Tasks

- [x] Task 1: run_id + manifest 统一产物目录
  - [x] SubTask 1.1: 新增 `app/services/run_manager.py`：RunContext 类 + new_run() / write_manifest()
  - [x] SubTask 1.2: 子目录工厂：input/drawing/qc/bom/quote/logs 自动 mkdir
  - [x] SubTask 1.3: services/__init__.py 导出 RunContext, new_run

- [x] Task 2: health_check 扩展到 12 项
  - [x] SubTask 2.1: 12 项检查实现（含 sw_revision_supported / template_size_ok / chinese_path_support / v5_fallback / db_readable）
  - [x] SubTask 2.2: 返回结构改为 {all_ok, pass, warning, fail, items}
  - [x] SubTask 2.3: 真实跑出 12 项 + EXE hiddenimport 适配

- [x] Task 3: SolidWorks 制图链路确认
  - [x] SubTask 3.1: sw_runner 绝对路径 + fallback 日志写 sw.log
  - [x] SubTask 3.2: 闭环结束扫描 SLDDRW/PDF/DXF/PNG 落盘并写 manifest.output_files
  - [x] SubTask 3.3: fallback_used 字段记录到 manifest

- [x] Task 4: QC diagnostics + hard_fail 白名单
  - [x] SubTask 4.1: drw_quality_check.py 新增 diagnostics 4 子项
  - [x] SubTask 4.2: hard_fail 严格按 12 项白名单
  - [x] SubTask 4.3: refdoc_correct 强制 severity=warning，不进 hard_fail

- [x] Task 5: vision_score + fix_suggestion
  - [x] SubTask 5.1: vision_qc.py 输出新增 threshold + image_path + model 字段
  - [x] SubTask 5.2: 4 类典型 warning（gb_titlebar / has_datum_a / has_ra_note / section_view）补 fix_suggestion 文本

- [x] Task 6: BOM / 工艺 / 报价完整交付
  - [x] SubTask 6.1: run_manager.full_pipeline(part_path) 串联 BOM+工艺+报价
  - [x] SubTask 6.2: 6 产物（json+xlsx）写入 run_id 子目录
  - [x] SubTask 6.3: assumptions / warnings 缺失字段处理

- [x] Task 7: UI 七页 + smoke 截图
  - [x] SubTask 7.1: 首页 12 项卡 + 最近 5 次 run + 打开输出目录按钮
  - [x] SubTask 7.2: 新增「单件制图」页 single_part_page.py
  - [x] SubTask 7.3: 批量页增强单行重跑、导出 CSV
  - [x] SubTask 7.4: 质检页 / BOM 页 / 设置页 / 日志页 增强
  - [x] SubTask 7.5: 主窗口导航更新（新增单件页）
  - [x] SubTask 7.6: EXE 中 7 页 smoke 截图 ≥ 30KB

- [x] Task 8: 诊断包 zip
  - [x] SubTask 8.1: 新增 `app/services/diagnostics.py`：build_diagnostics_zip(run_id)
  - [x] SubTask 8.2: zip 内 9 文件（manifest/qc/vision/3 logs/health/2 screenshots/version.txt）
  - [x] SubTask 8.3: UI 日志页加按钮「生成诊断包」

- [x] Task 9: refdoc_relink_service 预留接口
  - [x] SubTask 9.1: 新增 `app/services/refdoc_relink_service.py`：relink_refdoc(...) 5 策略 stub
  - [x] SubTask 9.2: pywin32_late 实现（已有 ReplaceViewModel 代码迁过来）；其他 4 策略返回 not_implemented
  - [x] SubTask 9.3: 设置页加「实验性 refdoc 强修」开关，默认关闭

- [x] Task 10: 重打 v1.1 EXE + release_log_v1_1.md
  - [x] SubTask 10.1: build_exe.spec 新增 hiddenimports（health_check / refdoc_relink_service / diagnostics / run_manager / single_part_page + 6 个 UI 页）
  - [x] SubTask 10.2: 清理旧 EXE 进程 + pyinstaller --noconfirm（exit_code=0，135.3 MB）
  - [x] SubTask 10.3: smoke alive 8s（pid=2804） + 7 页截图（全部 ≥ 30KB） + exe_alive.png
  - [x] SubTask 10.4: 真实单件闭环 run_id=b84a04edfd46 / hard_fail=[] / drawing_usable=True / qc_pass=11/12 / vision=65 / 6 类产物齐全
  - [x] SubTask 10.5: 写 release_log_v1_1.md（14 节 + 最终判定 PASS）

# Task Dependencies
- Task 1 与 Task 2 / 5 / 8 / 9 可并行
- Task 3 依赖 Task 1
- Task 4 与 Task 3 可并行
- Task 6 依赖 Task 1 + 3
- Task 7 依赖 Task 1 + 2 + 6 + 8 + 9（UI 调它们）
- Task 10 依赖 Task 1~9
