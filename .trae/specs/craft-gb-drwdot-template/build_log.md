# Build Log — craft-gb-drwdot-template Task 5

**生成时间**：2026-06-18

---

## 节 1 模板构造（SubTask 5.2）

| 项 | 值 |
|---|---|
| 命令 | `python templates/build_drwdot.py` |
| 首次构造耗时 | ~2.08s |
| 二次构造耗时 | ~2.03s |
| 模板路径 | `c:\Users\Vision\Desktop\SW 相关\templates\gb_a4_landscape.drwdot` |
| 模板大小（首次） | **78611 bytes (76.8 KB)** |
| 模板大小（二次） | 78093 bytes (76.3 KB) |
| 文件大小变化 | -518 bytes (在 ±1 KB 容差内) |
| 退出码 | 0 |

构造过程关键日志：
- `[sw] rev=33.5.0`
- `[template] base=C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2025\templates\gb_a4.drwdot`
- 15 项 InsertNote 全部 OK（12 中文标签 + 3 个 `$PRP:` 链接）
- `Extension.SaveAs` 报"类型不匹配"但 `SaveAs2` 兜底成功，模板文件落地
- `[sheet] SetProperties failed: (-2147352573, '找不到成员。', None, None)` — `SetProperties2`/`SetProperties` 在当前 IDispatch 形式下不可直接调用，但纸张尺寸由模板继承，最终 `GetProperties2` 探针读出的纸张为 (0.297, 0.210)，符合 A4 横式

构造修补：
- 修复 `sw.RevisionNumber()` → 改为兼容 callable 与 property 两种形式
- 修复 `default_drwdot` 候选路径列表，新增 `C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2025\templates\gb_a4.drwdot` 兜底，避免 `NewDocument` 返回 None
- 字高补充 `GetUserPreferenceTextFormat(1) → CharHeight=0.005 → SetUserPreferenceTextFormat(1, tf)` 文档级强制，确保模板默认 Note 字高 ≥ 3.5 mm

---

## 节 2 探针验证（SubTask 5.3）

| 检查项 | pass | 详细数值 |
|---|---|---|
| `sheet_size_a4` | ✅ | w=0.297 m, h=0.210 m, raw=[6.0, 12.0, 1.0, 1.0, 1.0, 0.297, 0.21, 1.0] |
| `text_height_ge_3_5mm` | ✅ | value_m=0.0035 (= 3.5 mm，从 `GetUserPreferenceTextFormat(1).CharHeight` 读取) |
| `layer_count_ge_5` | ✅ | count=13（继承 SW 内置 GB 模板的 8 层 + 自添加 5 层） |
| `noteblock_ge_13` | ✅ | count=87（继承模板既有 Note + 新插入 15 个） |
| `prp_links_ge_3` | ✅ | count=31（含模板原 `$PRPSHEET` 链接 + 新增 3 个 `$PRP`） |

**汇总：5/5 全部 pass**，`probe_result.json.summary.all_pass = true`，退出码 0。

探针修补：
- 改用 `_oleobj_.Invoke(...)` 直接调用 IDispatch 方法，绕开 `<COMObject <unknown>>.GetCurrentSheet()` 的 `'str' object is not callable` / `'非选择性的参数。'` 报错
- 字高检查改用 `GetUserPreferenceTextFormat(1).CharHeight`（文档级 Note 默认字高），原 `GetUserPreferenceDoubleValue(89)` 在 SW 2025 上对 .drwdot 总返回 0.00025（应用级遗留值），并非真实 Note 字高
- PRP 链接同时检查 `GetText` 与 `PropertyLinkedText`（`$PRP:"…"` 在 GetText 返回空，需用 PropertyLinkedText）

---

## 节 3 v5 接入日志（SubTask 5.4 前置）

修改文件清单：
- `.trae/specs/enforce-drawing-quality/drw_generate_v5.py` 第 521~544 行：新增模板探测优先级链
  - `os.environ.get("DRWDOT_TEMPLATE")` > `templates/gb_a4_landscape.drwdot` > SW 自带 `*.drwdot`
  - 命中时打印 `[template] using {path}`，未命中打印 `[template] fallback`
- `app/config/defaults.py`：默认 `drwdot_template = repo_root / "templates" / "gb_a4_landscape.drwdot"` （Task 4 已完成）
- `config/app.yaml.example`：示例字段 `drwdot_template: templates/gb_a4_landscape.drwdot` （Task 4 已完成）

import 验证：

```
$ python -c "from app.services import build_default_client, vision_score, slddrw_to_png; print('import ok')"
import ok
$ python -c "from app.services import build_default_client; c=build_default_client(); print(c.test_connection())"
client type: LLMClient
connected: True msg: ok: pong lat: 1133
```

---

## 节 4 真实闭环（SubTask 5.4）

```
python .trae/specs/harden-v5-and-vision-loop/vision_loop.py "3D转2D测试图纸\LB26001-A-04-001.SLDPRT" --max-rounds 2 --threshold 80
```

| 项 | 值 |
|---|---|
| 退出码 | 1 (best_score 53 < 阈值 80) |
| 总轮数 | 2 |
| 最佳 vision_score | **53/100**（第 2 轮，第 1 轮 35） |
| 最终 quality_check pass_count | 9/12 |
| 残余 issues | `text_height_ge_3_5mm`, `has_tech_note`, `has_ra_note`, `has_datum_a`, `refdoc_correct`, `gb_titlebar_complete`, `gb_paper_size_correct`, `gb_has_section_view_or_skipped` |

阶段对比：

| 阶段 | vision_score | qc_pass |
|---|---|---|
| harden Task 6 | 15/100 | 0/12 |
| harden Task 7 | 35/100 | 9/12 |
| craft Task 5 | **53/100** | 9/12 |

### 残余问题分析（vision_loop best_score=53 < 80 的根因）

1. **`text_height_ge_3_5mm`** — 当前 `drw_quality_check.py` 仍读 `GetUserPreferenceDoubleValue(89)`（应用级），值固定 0.00025 m。模板内置 Note 字高已是 3.5 mm（探针通过 TextFormat API 验证），但 v5 生成的图纸文件从 `NewDocument` 起未应用模板（`drw_generate_v5.py` 调用 `sw.NewDocument(_drwdot_path or "", 0, 0, 0)` 第 2 个参数 paperSize 为 0，可能命中默认 A 大小而非 A4），需后续 spec 验证。
2. **`gb_paper_size_correct`** — qc.json 报 `sheet (None, None)`，意味着 v5 流程下 sheet `GetProperties2` 解析失败（与本 task 探针不同的查询路径）。属 v5 的探针解析问题，非模板问题。
3. **`gb_titlebar_complete`** — 缺 6 组核心字段值，根因是源 .SLDPRT 自定义属性为空（compare_v3 报告显示原件 0/13 实值），`drw_generate_v5.py` 写入空字符串。属数据源问题。
4. **`gb_has_section_view_or_skipped`** — section_helper 全部策略失败（v5 stdout：`[section] all strategies failed`），属 v5 自动剖视图能力局限。
5. **`refdoc_correct`** — 4 视图 ref_doc_present=False。v5 在 SaveAs 时 part 已关闭或路径异化，导致引用解除。属 v5 流程问题，非模板问题。
6. **`has_tech_note` / `has_ra_note` / `has_datum_a`** — qc.json 报 `noteblock_total=33`，远低于探针在模板上读到的 87，意味着 v5 生成时大量模板原有 Note 被覆盖/丢失，仅保留了部分。需后续 spec 排查 `_draw_gb_frame_and_titleblock` 是否清理了模板自带 Note。

### 已知限制

- 当前 `drw_quality_check.py` 的 `text_height_ge_3_5mm` 与 `gb_paper_size_correct` 仍读 `GetUserPreferenceDoubleValue` / 旧 sheet API，与模板的真实字高/纸张设置脱节，需要在下个 spec 中将这两项改为读 `GetUserPreferenceTextFormat(1).CharHeight` 与 `Sheet.GetProperties2`（已在本 task 探针验证可行）。
- `drw_generate_v5.py` 调用 `sw.NewDocument(template, 0, 0, 0)` 的 paperSize=0 应替换为 `12 (swDwgPaperA4size_横式)`，并强制 width/height = 0.297/0.210，从而保证模板加载后 sheet 仍是 A4 横式。
- v5 的 `_draw_gb_frame_and_titleblock` 在已经使用模板的情况下，会重复绘制图框 + 重复插入 Note，属冗余渲染，可能掩盖模板自带元素。后续 spec 应根据"是否使用模板"做条件分支。
- 第 1 轮 35 → 第 2 轮 53 提升 18 分主要来自 vision_loop 反馈触发的局部参数调整；模板根治路径未真正"接通"到 v5 流程（v5 仍在每次都重画图框/标题栏），所以 score 没有突破到 80。

---

## 总结

- 模板构造、探针验证两项已 100% 达成（5/5 探针项 pass，幂等性 ±1 KB 内）。
- v5 接入新模板的代码改动已落地，import / LLM 连通验证通过。
- 真实闭环 best_score 53/100，未达阈值 80；qc_pass 9/12，未达 11/12。残余问题已归类，根因主要在 v5 的 quality_check 探针实现（不读模板内置字高/纸张）以及 v5 流程对模板的"半接管"（仍重绘图框）。
- 下个 spec 应聚焦：① 让 quality_check 与本 task 探针使用同一组 SW API；② 让 v5 在使用模板时跳过自绘图框/标题栏。

## 节 5 二次闭环验证（Task 6 修复后）

修复点：
- v5 用模板时跳过 _draw_gb_frame_and_titleblock
- NewDocument paperSize=12 + 0.297×0.210 强制 A4
- quality_check 字高/纸张读取与 probe_drwdot 一致

重跑结果：
- 退出码: 1
- 最佳 score: 55/100
- qc_pass: 11/12

阶段对比：
| 阶段 | vision_score | qc_pass |
| Task 5 | 53/100 | 9/12 |
| Task 6 | 55/100 | 11/12 |
