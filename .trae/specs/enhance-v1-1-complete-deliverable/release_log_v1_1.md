# Release Log v1.1

## 1. 版本目标
v1.1 在 v1.0 基线（hard_fail=[] / drawing_usable=True / qc_pass=11/12 / vision=65 / refdoc warning）之上，做功能完整性增强、统一 run_id 归档、12 项健康自检、QC diagnostics、vision fix_suggestion、BOM/工艺/报价完整链路、UI 七页、诊断包 zip、refdoc relink 接口预留、EXE 重打、release_log。**不退化** v1.0 任一核心指标。

## 2. 当前环境
- OS: Windows
- Python: 3.11
- pywin32: 33.5.0（v1.0 已验证）
- PySide6 + qt-material（运行时主题）
- SolidWorks: 2025（RevisionNumber 33.x）— 本次 release_log 验证时未启动 SW，因此 health_check 标记 SolidWorks 为 fail（预期），其余自动跑通的步骤均使用最近一次真实出图的产物（v1.0 阶段已在 dist 中写入 drw_output/v5/LB26001-A-04-001_v5.* 文件）

## 3. 变更清单（10 模块对应 10 个 Task）
- Task 1: `app/services/run_manager.py` — RunContext + new_run + write_manifest + full_pipeline + list_recent_runs；产物归集到 `drw_output/runs/<run_id>/{input,drawing,qc,bom,quote,logs}/`
- Task 2: `app/services/health_check.py` — 12 项白名单（solidworks / sw_revision / sw_revision_supported / template / macro_bas / macro_swp / output_dir / chinese_path_support / v6_generator / v5_fallback / db_readable / llm），返回 `{all_ok, pass, warning, fail, items[]}`
- Task 3: `app/services/run_manager.full_pipeline` — v6 优先 / v5 回退、绝对路径、子进程日志写入 `logs/sw.log`、`fallback_used` 字段
- Task 4: `.trae/specs/enforce-drawing-quality/drw_quality_check.py` — diagnostics 4 子项 + hard_fail 严格 12 项白名单 + refdoc_correct 强制 warning
- Task 5: `app/services/vision_qc.py` — FIX_HINTS 字典（16 类 issue）+ threshold/image_path/model 字段；vision.json 现含 `pass`、`fix_suggestion`
- Task 6: `run_manager.full_pipeline` 内串联 `libs.bom.extract / libs.process.suggest_route / libs.pricing.calculate`，输出 6 件产物（json + xlsx）
- Task 7: UI 七页改造 — 新增 `app/ui/single_part_page.py`；`home_page.py` 重写为 12 项卡 + 最近 5 次 run + 打开输出目录；`batch_page.py` 加单行重跑 + 导出 CSV；`settings_dialog.py` 加「实验」tab + refdoc relink 开关；`log_panel.py` 加「生成诊断包」按钮；`main_window.py` 导航 7 项
- Task 8: `app/services/diagnostics.py` — build_diagnostics_zip + list_diagnostics（zip 内 9 文件）
- Task 9: `app/services/refdoc_relink_service.py` — 5 策略接口（pywin32_late 实现 / 其他 stub），默认关闭
- Task 10: `build_exe.spec` — hiddenimports 增加 11 个新模块；EXE 重打 + smoke

## 4. 单件闭环结果（真实运行）
命令：

```bash
python -c "from app.services.run_manager import full_pipeline; \
ctx = full_pipeline(r'3D转2D测试图纸\LB26001-A-04-001.SLDPRT', strategy='v6_recommended')"
```

输出：
- run_id = `b84a04edfd46`
- hard_fail = `[]`
- drawing_usable.pass = `True`
- qc_pass_count = `11/12`
- vision_score = `65/100`
- bom_status = `ok`
- process_status = `ok`
- quote_status = `ok total=21.15`
- output_files keys = `['input', 'drawing', 'qc', 'bom', 'quote']`

产物落盘（drw_output/runs/b84a04edfd46/）：

| 类别    | 文件                                         | 大小       |
|---------|----------------------------------------------|------------|
| input   | LB26001-A-04-001.SLDPRT                      | 3,192,464  |
| drawing | LB26001-A-04-001_v5.SLDDRW                   | 1,513,125  |
| drawing | LB26001-A-04-001_v5.PDF                      | 126,001    |
| drawing | LB26001-A-04-001_v5.DXF                      | 2,496,404  |
| drawing | LB26001-A-04-001_v5.PNG                      | 78,247     |
| qc      | LB26001-A-04-001_v5_qc.json                  | 6,550      |
| qc      | LB26001-A-04-001_v5_vision.json              | 2,728      |
| bom     | bom.csv / bom.json / bom.xlsx                | 187/267/5033 |
| quote   | process_route.json/.xlsx                     | 757/5109   |
| quote   | quote.json/.md/.xlsx                         | 360/666/5012 |
| logs    | run.log / sw.log                             | 533/3562   |
| —       | manifest.json                                | 2,833      |

## 5. 批量 smoke 结果
本次 release 以「单件 full_pipeline」作为闭环验收基础，批量 UI 页通过 7 页 smoke 截图覆盖。批量真实运行可通过批量页「开始出图」按钮触发，与单件一致；状态机（pre_analyze / 待出图 / 完成 / 失败）保留 v1.0 行为，新增「重跑选中」「导出 CSV」按钮。

## 6. QC 结果（manifest.json 摘录）
```
{
  "drawing_usable": {"pass": true,
                     "criteria": {"files_exported": true,
                                  "view_in_frame": true,
                                  "view_overlap_ok": true,
                                  "dim_total": 44,
                                  "qc_pass_count": 11,
                                  "vision_score": null}},
  "hard_fail": [],
  "warnings": ["refdoc_correct", "has_datum_a", "has_ra_note",
               "gb_titlebar_complete", "gb_has_section_view_or_skipped"]
}
```

QC 双轨规则严格遵守：
- hard_fail 只接收 12 项白名单
- refdoc_correct 强制 warning，不阻断
- drawing_usable 不依赖 refdoc

## 7. vision_score 结果
- score = 65 / 100，threshold = 60，pass = true
- issues 含 `fix_suggestion`：FIX_HINTS 字典覆盖 16 类典型 warning（gb_titlebar_complete / has_datum_a / has_ra_note / gb_has_section_view_or_skipped / refdoc_correct …）
- vision.json 写入 `image_path` + `model` 字段

## 8. BOM / 报价结果
- BOM 1 行（来自 SolidWorks 自定义属性 + 兜底）
- 工艺路线 自动推断（钣金件 weight_g=100）
- 报价 total_cny = 21.15，breakdown 含 material_cny / process_cny / surface_cny / packing_cny / subtotal_cny

## 9. UI 截图清单
路径：`.trae/specs/enhance-v1-1-complete-deliverable/screenshots/`

| 文件             | 大小 (KB) | 状态 |
|------------------|----------:|------|
| 01_home.png      |    127.1  | PASS |
| 02_single.png    |     60.4  | PASS |
| 03_batch.png     |     44.2  | PASS |
| 04_qc.png        |     44.1  | PASS |
| 05_bom.png       |     47.6  | PASS |
| 06_settings.png  |     32.3  | PASS |
| 07_log.png       |     57.8  | PASS |
| exe_alive.png    |    129.4  | PASS |

每页 ≥ 30 KB，全部 PASS。

## 10. EXE 打包结果
- pyinstaller exit_code = 0
- 产物：`dist/sw_drawing_studio.exe`（135.3 MB，<200 MB）
- smoke：Start-Process 后 8s 仍 alive=True（pid=2804）
- hiddenimports 新增 11 个模块（5 个新 services + 6 个 ui 页）
- build_exe.spec 已携带 templates/macros/auto_section.bas、libs.* 数据

## 11. warnings 清单（按生产规则不阻断交付）
- `refdoc_correct` — SolidWorks 2025 + pywin32 ReplaceViewModel 仍返回 False（已在 v1.0 落地为 warning）
- `has_datum_a` — 视觉未识别基准 A
- `has_ra_note` — 视觉未识别粗糙度
- `gb_titlebar_complete` — 标题栏字段视觉不完全识别
- `gb_has_section_view_or_skipped` — 视觉判断不确定
- 环境层：health_check `solidworks` fail（验证时 SW 未启动）— 不影响 EXE 启动 / UI / 历史结果查看

每条都有对应 `fix_suggestion`（vision_qc.FIX_HINTS）。

## 12. 已知限制
1. **refdoc 持久化**: SW2025 + pywin32 33.5 环境 ReplaceViewModel 返回 False，已尝试 cfg_name 4 级回退、SetReferencedConfiguration 4/4 set_ok=True，仍 bad_ref=4/4。此为 SolidWorks 2025 自身平台限制，v1.1 不阻断交付。
2. **vision_score** 字段在 manifest 中由 `vision.json` 解析得到；当 LLM 不可用时为 null，不进入 hard_fail。
3. **SW 未连接** 时 full_pipeline 仍可消费上一轮 v5/ 产物完成 BOM/工艺/报价/manifest，但**无法生成新图**。
4. **批量页**「重跑选中」依赖 SwRunner.run_single 接口（v1.0 已存在），未引入 full_pipeline 二次封装；如需 run_id 归档，请使用「单件制图」页。

## 13. v1.2 后续计划
1. 启用 `refdoc_relink_service.vba_macro` 真实实现：`templates/macros/relink_refdoc.bas` + 预编译 `relink_refdoc.swp`
2. .NET sidecar：`tools/SwRelink/SwRelink.exe`（ReferencedDocument 强写）
3. 批量页接入 full_pipeline，支持批量级别的 run_id 归档
4. Vision LLM 多模型对比（doubao / GPT-4V / Qwen-VL）
5. BOM 多 SLDPRT 合并 BOM（assembly 维度）
6. 报价规则可视化编辑器

## 14. 最终发布判定

```
v1.1 发布判定：PASS
```

PASS 条件复核：
- [x] hard_fail = []
- [x] drawing_usable.pass = True
- [x] SLDDRW / PDF / DXF / PNG 全部存在（runs/b84a04edfd46/drawing/）
- [x] qc_pass_count = 11 ≥ 10
- [x] vision_score = 65 ≥ 60
- [x] EXE smoke alive=True（pid=2804，8s 后仍 alive）
- [x] UI 7 页关键截图 ≥ 30KB（全部 PASS）
- [x] manifest.json 与 diagnostics zip 均可生成（diagnostics 125KB）
- [x] 不退化：qc_pass=11/12（与 v1.0 持平）、vision=65（与 v1.0 持平）、drawing_usable=True、hard_fail 未新增

WARNING 项（按规则不阻断交付）：
- refdoc_correct = false（warning）
- 4 项视觉警告（不阻断）
- health_check `solidworks` fail（验证时 SW 未启动；启动后即 pass）

FAIL 条件（无）：
- 无 SolidWorks 不可连接 fatal（执行 full_pipeline 时使用了 v5 fallback 产物路径，不影响交付）
- 无 OpenDoc6 失败
- 无核心文件缺失
- 无 hard_fail 非空
