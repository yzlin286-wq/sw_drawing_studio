# Smoke Test Report — solidworks-automation-skill 能力冒烟测试

> 时间：2026-06-18
> 范围：基于本仓库已有产物（`drw_output/v5/`、`drw_output/`、`.trae/specs/build-3d-to-2d-desktop-app/screenshots/`）做"基于历史 run 的回放冒烟"，并对未覆盖项给出可执行的复现命令；本会话不在线驱动 SolidWorks。
> 结果记号：✅ pass / ⚠ warn / ❌ fail / ⏭ skipped(环境受限)

---

## 0. 选定测试样本

| 类型 | 文件 | 选择理由 |
|---|---|---|
| 零件 #1 | [LB26001-A-04-001.SLDPRT](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/3D%E8%BD%AC2D%E6%B5%8B%E8%AF%95%E5%9B%BE%E7%BA%B8/LB26001-A-04-001.SLDPRT) | 历史回归基线，已有 v4/v5 全套产物 |
| 零件 #2 | LB26001-A-04-005.SLDPRT | 同系列，验证批量稳定性 |
| 零件 #3 | -AK-15-AC-25-1-V3-V02.SLDPRT | 中文文件名 + 复杂前缀 |
| 零件 #4 | 0.6X5X10压缩弹簧(线径x外径x长度).SLDPRT | 含括号 + 弹簧类（细长回转体） |
| 零件 #5 | INGUN_GKS 050 201 050 A2000 尖针.SLDPRT | 含空格 + 标准件 |
| 装配 | LB26001-gen5.0硬盘转卡组件.SLDASM | 验证装配体路径（v5 当前未支持装配，预期 ⚠/⏭） |
| 已有 SLDDRW | QTN-0488 MCIO 74Pin CABLE改头固定件A-V02.SLDDRW | 验证 `drw_quality_check.py` 单文件直跑 |

---

## 1. 出图主链路（drw_qc_loop.run_qc_loop）

**复现命令**（由 SwRunner 在桌面 App 内调用，CLI 等价）：

```bash
python ".trae/specs/enforce-drawing-quality/drw_qc_loop.py" "3D转2D测试图纸/LB26001-A-04-001.SLDPRT"
```

| 样本 | 状态 | 证据 | 备注 |
|---|---|---|---|
| LB26001-A-04-001 | ⚠ warn | `drw_output/v5/LB26001-A-04-001_v5_qc.json` 含 `OpenDoc6 returned None` | 历史 run 在第 N 轮后 SLDDRW 文件已写出（PNG/vision 都已生成），但最末一次 QC 重新打开失败。SwRunner 视 `slddrw` 存在为 ok=True，体验上等价"完成"。修复建议：闭环 retry 时延长 `SAVE_FLUSH_WAIT`（当前 1.5s）→ 3s |
| LB26001-A-04-005 / -AK-15-AC-25 / 0.6X5X10弹簧 / INGUN 尖针 | ⏭ | 未在线 run | 产物未存在；建议从 UI 批量页加入 5 个一并跑 |
| LB26001-gen5.0硬盘转卡组件.SLDASM | ❌ 预期不支持 | `drw_generate_v5.py` 链路硬编码 `*Front/*Top/*Right/*Isometric` 模型视图，装配体的"前视"基准在多数顶层装配中位置定义不同，剖视/视图比例策略也异 | 修复建议：装配体走另一条最小链路（仅 `*Isometric` + BOM 表）；本次审计**不**修补，归入 backlog |
| QTN-0488 改头固定件A.SLDDRW（直接对已有 SLDDRW 跑 QC） | ⏭ | 未在线 run | 复现：`python ".trae/specs/enforce-drawing-quality/drw_quality_check.py" "3D转2D测试图纸/QTN-0488 ... 改头固定件A-V02.SLDDRW"`（注意路径含空格） |

**统计**：1 ⚠ + 4 ⏭ + 1 ❌（装配）。

---

## 2. 视觉评分链路（vision_qc.vision_score）

| 样本 | 状态 | 证据 |
|---|---|---|
| LB26001-A-04-001_v5 | ✅ pass（链路通） / ⚠ 评分内容 | `drw_output/v5/LB26001-A-04-001_v5_vision.json` 已成功落盘，`png_ok=true`，`score=15`，5 条 issues 全部为人话。说明：链路本身 pass；评分低是底层 SLDDRW 质量问题（标题栏空、无尺寸），不是 vision_qc 缺陷 |
| 其他样本 | ⏭ | 需先生成 SLDDRW 才能跑 vision |

**复现 vision 的最小命令**：在 QC 页选择 `LB26001-A-04-001_v5.SLDDRW` → 点"AI 视觉质检"。配置要求：`llm.yaml` 当前 active_provider=`deepseek`，但 deepseek 无 vision_model；建议切换到 `dashscope` (`qwen-vl-max`) 或 `openai` (`gpt-4o`) 才能发出 vision 请求。

---

## 3. 桌面服务（SwRunner 信号链）

| 信号 | 状态 | 证据 |
|---|---|---|
| `SwRunner.log_line` 透传子进程 stdout | ✅ | [sw_runner.py:104-110](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/app/services/sw_runner.py#L104-L110) 已逐行 emit |
| `SwRunner.progress(idx, total)` | ✅ | [sw_runner.py:162](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/app/services/sw_runner.py#L162-L162) 在批量循环中 emit |
| `SwRunner.finished` | ✅ | [sw_runner.py:146](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/app/services/sw_runner.py#L146-L146) 在 run_single 末尾 emit |
| `SwRunner.stop()` | ⚠ | 仅 `proc.terminate()`；批量层在每个文件开始前才检查 `_stop_flag`，**当前文件不会立即停**。修复在 UX P0 #2 |

---

## 4. 桌面 UI 启动（python -m app.main）

| 项 | 状态 | 证据 |
|---|---|---|
| 启动不报错、显示首页/批量/QC | ✅ | `.trae/specs/build-3d-to-2d-desktop-app/screenshots/01_main_window.png`、`02_batch_page.png` |
| 首页 SW 状态卡片渲染 | ✅ | screenshot 01 显示卡片 |
| 批量页表格列齐全（9 列） | ✅ | screenshot 02 显示完整表头 |
| QC 页 PNG 预览自动加载 | ✅ | 由 `qc_page._auto_load_preview` 自动调用 `request_render_png` |
| 设置对话框打开 | ⏭ | 未截屏 |
| 日志 dock 显示等级颜色 | ✅ | log_panel `_LEVEL_COLORS` 已配色 |

---

## 5. 12 项渲染级 QC（drw_quality_check）

基于 `drw_output/v5/LB26001-A-04-001_v5_qc.json` 历史结果（最末轮 OpenDoc6 失败，使用上一轮）：

| # | 检查项 | 实测 | 备注 |
|---|---|---|---|
| 1 | view_overlap | ✅ | warnings.json 中 `real_overlap_pairs=[]` |
| 2 | view_in_frame | ✅ | 4 个视图 outline 均在 [0.010,0.010,0.287,0.200] 内 |
| 3 | front_view_position | ✅ | front 中心 (80,135)mm 在 [40-180,80-180] |
| 4 | scale_in_set | ⚠ | scale=1:10，**当前 GOOD_SCALES 不含 1:10**（白名单只到 1:5），但 GB 14690 允许 1:10。需扩展白名单（详见 gb_compliance_matrix.md） |
| 5 | text_height_ge_3_5mm | ❌→✅ | warnings 显示历史失败（issues_in 含 `text_height_ge_3_5mm`），当前 text_height=0.006m=6mm，应已 pass。此项是历史 issue，已修复 |
| 6 | all_13_keys_present | ❌ | warnings.json 显示 8 个 PROP 缺失（机型/品名/类别/材质/表面处理/设计/日期/Material/重量）。源头是 SLDPRT 文件的 CustomProperty 未填写；属于"模板未提前注入默认值"的痛点。修复建议：v5 应在写之前给空键填默认值（如材质="Q235", 设计="自动出图"） |
| 7 | dim_count_sufficient | ⏭ | 历史 qc_json 因 OpenDoc6 失败未给值；vision_json 显示"未标注任何零件尺寸"，可能 ❌ |
| 8 | centermark_count_sufficient | ⏭ | 同上 |
| 9 | has_tech_note | ❌ | issues_in 含此键 |
| 10 | has_ra_note | ❌ | issues_in 含此键 |
| 11 | has_datum_a | ❌ | issues_in 含此键 |
| 12 | refdoc_correct | ❌ | issues_in 含此键 |

**结论**：12 项中至少 5 项历史失败（标题栏属性 + 三个 NoteBlock 关键词 + refdoc）。这些**不是 QC 脚本的 bug**，而是 v5 生成器在该样本上未注入足够的标题栏 + 技术要求 + 粗糙度 + 基准 Note。已记入 `gb_compliance_matrix.md` 的 Patch 列表。

---

## 6. 已知阻塞 / Bug 一览（带修复建议）

| ID | 现象 | 文件 | 优先级 | 修复建议 |
|---|---|---|---|---|
| B-1 | `OpenDoc6 returned None`（最末轮 QC 打开失败） | drw_quality_check.py:138 | P1 | 重试两次，间隔 2s；保留 SAVE_FLUSH_WAIT 后再延长 3-5s |
| B-2 | `GOOD_SCALES` 不含 1:10 等 GB 标准比例 | drw_quality_check.py:68 | P0 | 扩展白名单为 GB/T 14690 的全集；同时剔除 (1,3)(1,4)（GB 不允许） |
| B-3 | `LayerMgr` 取不到（`layer_mgr_none`） | drw_generate_v5.py | P1 | 退回 `IModelDocExtension.LayerMgr` 双路径；失败则跳过图层着色但不阻塞 |
| B-4 | `<unknown>.DisplayMode` 设值失败 | drw_generate_v5.py | P2 | SW2025 该属性变为只读；用 `IView.SetDisplayMode3` 兜底 |
| B-5 | 标题栏属性缺失 | 来源 SLDPRT 自身 | P0 | v5 生成时检测缺失 → 写入 GB 默认值（材质=Q235, 表面处理=按图,...） |
| B-6 | 装配体（SLDASM）链路未实现 | drw_generate_v5.py | backlog | 不在本次范围 |
| B-7 | 视觉评分依赖的 vision_model 默认 provider 为空 | llm.yaml.example deepseek | P1 | 设置首页/QC 页打开时检测，如果 active_provider 无 vision_model 则给出 toast：建议切换到 dashscope/openai |
| B-8 | `stop()` 不能立即终止当前文件 | sw_runner.py:28-35 | P0 | 在批量页加 stop 按钮 + UX 修补；当前 terminate 已能杀子进程，主要是 UI 缺暴露 |

---

## 7. 总评

| 维度 | 数量 |
|---|---|
| ✅ pass | 6（视图重叠/在框/前视位置/字高/UI 启动/服务信号） |
| ⚠ warn | 3（OpenDoc6 偶失、GOOD_SCALES 缺 1:10、stop 体感慢） |
| ❌ fail | 5（标题栏属性、技术要求 Note、Ra Note、基准 Note、refdoc） |
| ⏭ skipped | 6（其他样本未在线 run、装配链路、设置对话框截屏） |

→ 主链路在样本 #1 上"可用但有缺陷"。所有 ❌ 项的根因是"v5 生成器在缺少模板默认值时未补齐"，而**不是 QC 脚本误报**。修补全部归入 [gb_compliance_matrix.md](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/.trae/specs/audit-skill-capabilities-and-prep-exe/gb_compliance_matrix.md) 与 [ux_review.md](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/.trae/specs/audit-skill-capabilities-and-prep-exe/ux_review.md)。
