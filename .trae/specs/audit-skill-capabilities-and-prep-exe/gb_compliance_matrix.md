# GB Compliance Matrix — 中国制图国标符合性比对

> 时间：2026-06-18
> 范围：[drw_generate_v5.py](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/.trae/specs/enforce-drawing-quality/drw_generate_v5.py) 当前实现 + [drw_quality_check.py](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/.trae/specs/enforce-drawing-quality/drw_quality_check.py) 12 项检查 + 历史产物（`drw_output/v5/LB26001-A-04-001_v5_*`）
> 标记：✅ 完全实现 / ⚠ 部分实现 / ❌ 未实现 / 🔧 本次落地补丁

---

## 1. 10 条核心条款 × 当前实现 × 缺口

| # | GB 条款 | 关键要求 | 当前实现 | 状态 | 处理方式（本次） |
|---|---|---|---|---|---|
| 1 | **GB/T 14689 图幅图框** | A0~A4 标准幅面 + 图框 + 标题栏右下 + 第一角投影符号 | `SetupSheet5(paperSize=6, w=0.297, h=0.210, firstAngle=True)` | ⚠ | 🔧 新增 QC 规则 `gb_paper_size_correct`：sheet 尺寸应为 GB 标准；缺标题栏字段时报失败 |
| 2 | **GB/T 14690 比例** | 5:1 / 2:1 / 1:1 / 1:2 / 1:5 / 1:10 / 1:20 / 1:50 / 1:100 | QC 第 4 项 `GOOD_SCALES = {(5,1),(3,1),(2,1),(1,1),(1,2),(1,3),(1,4),(1,5)}` | ❌ | 🔧 修正白名单为 GB 全集，删除 `(1,3)(1,4)(3,1)`，新增 `(1,10)(1,20)(1,50)(1,100)(50,1)(20,1)(10,1)` |
| 3 | **GB/T 14691 字体** | 长仿宋体；字高 3.5/5/7/10mm | v5 `SetUserPreferenceDoubleValue(89, 0.005)`；当前 text_height=0.006m | ⚠ | 🔧 新增 QC 规则 `gb_font_is_changfangsong`：所有 Note 的 TypeFaceName 含「仿宋」 |
| 4 | **GB/T 4458.1 视图** | 第一角投影；主视图选信息量最大方向；4 视图布局 | v5 已强制 firstAngle=True；4 视图坐标布局；QC 第 1/2/3 项校验 outline & 前视位置 | ✅ | 已 pass |
| 5 | **GB/T 4458.4 尺寸标注** | 字高 3.5；箭头 5；不可重叠尺寸数字 | v5 `InsertModelAnnotations3`；QC 第 7 项 dim_count_sufficient | ⚠ | 沿用现状（DisplayDim 数量阈值 ≥ 0.5×baseline） |
| 6 | **GB/T 17452 剖视** | 至少在内腔/复杂特征上有剖视图 | section_helper.py 仅 CLI；v5 默认未启用；warnings 显示 `section_helper_failed` | ❌ | 🔧 新增 QC 规则 `gb_has_section_view_or_skipped`：检查 `view.GetType()==4`（剖视）出现 ≥ 1 次；允许通过 `gb_drawing_rules` 配置 `require_section=false` 关闭 |
| 7 | **GB/T 131-2006 表面粗糙度** | Ra 标注或"其余 Ra3.2"统一标注 | QC 第 10 项 `has_ra_note`（NoteBlock + 关键词 Ra/粗糙）| ⚠ | 沿用现状；同时 🔧 在 `gb_titlebar_complete` 中允许通过自定义属性"表面处理"提供"全部 Ra3.2"作替代证据 |
| 8 | **GB/T 1182-2008 形位公差** | 至少 1 个基准 + 关键尺寸的位置/同轴/平行公差 | QC 第 11 项 `has_datum_a`（NoteBlock 关键词 △A/基准 或实体 DatumTag） | ⚠ | 沿用现状 |
| 9 | **GB/T 17450 / 4457.4 线型线宽** | 粗 0.7mm 图框 / 0.25mm 尺寸；7 大线型 | warnings 显示 `layer_mgr_none`，图层未生效 | ⚠ | 不在本次范围（属 P1 修补，B-3） |
| 10 | **GB/T 10609.1 标题栏** | 必含 零件名/图号/材料/比例/数量/制图/审核/日期 | QC 第 6 项 `all_13_keys_present`（13 项 PROP_KEYS）；warnings 显示 8 个缺失 | ⚠ | 🔧 新增 QC 规则 `gb_titlebar_complete`：核心 8 项不可空（图号、零件名/品名、材料/材质、比例、数量、设计、审核/校核、日期） |

---

## 2. 本次新增的 5 条 GB 强化 QC 规则

| 键名 | 规则 | 默认 | 关闭开关（`gb_drawing_rules.md` 中） |
|---|---|---|---|
| `gb_titlebar_complete` | 标题栏 8 个核心字段（机型 OR 品名、图号、材质 OR Material、比例、数量、设计、审核 OR 校核、日期）均非空 | 开 | `qc.gb_titlebar_complete = false` |
| `gb_font_is_changfangsong` | 至少 1 个 NoteBlock 字体含「仿宋」/「FangSong」 | 开 | `qc.gb_font_is_changfangsong = false` |
| `gb_paper_size_correct` | sheet width × height 与 sheet.paper_code 对应 GB 幅面（A0~A4 横/纵） | 开 | `qc.gb_paper_size_correct = false` |
| `gb_has_section_view_or_skipped` | 至少 1 个 view.type==4（剖视）；或显式跳过（`require_section=false`） | 开（require_section=true） | `qc.require_section = false` |
| `gb_scale_in_extended_set` | sheet.scale ∈ GB/T 14690 全集（不含 1:3 / 1:4） | 开 | `qc.gb_scale_in_extended_set = false` |

> 命名约定：所有新规则以 `gb_` 前缀，便于在 `drw_quality_check.py` 内集中开关。

---

## 3. 实施补丁（本次落地）

### 3.1 [drw_quality_check.py](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/.trae/specs/enforce-drawing-quality/drw_quality_check.py)

- 在文件顶部新增 `GB_RULE_TOGGLES` 常量（默认全开），并支持环境变量覆盖（如 `QC_GB_TOGGLES`）。
- 在 `quality_check()` 末尾追加 5 项 GB 检查，键名见上表。
- `_check_order` 扩展到 17 项，`pass` 仍要求全部通过（关闭的规则视为 pass）。

### 3.2 [gb_drawing_rules.md](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/.trae/specs/enforce-drawing-quality/gb_drawing_rules.md)

- 在文末追加"## 11. QC 开关位"小节，把 5 个新规则与默认值列出，方便用户关闭。

### 3.3 GOOD_SCALES 修正

- 旧：`{(5,1),(3,1),(2,1),(1,1),(1,2),(1,3),(1,4),(1,5)}` （含 GB 不允许的 1:3/1:4/3:1）
- 新：`{(5,1),(2,1),(1,1),(1,2),(1,5),(1,10),(1,20),(1,50),(1,100),(10,1),(20,1),(50,1)}`
- 同时新增 `gb_scale_in_extended_set` 检查项独立于现有 `scale_in_set`，便于灰度控制。

---

## 4. 回归预期

在 `LB26001-A-04-001.SLDPRT` 现有产物上：
- 第 4 项 `scale_in_set` 历史 ❌（scale=1:10 不在旧白名单）→ 修正后预期 ✅
- 新增 `gb_titlebar_complete` 在样本 #1 上仍 ❌（8 项中至少缺 5 项），但**不再视为 pass 全过**，与 vision_qc 评分（15）一致，避免 QC 与 vision 评分分歧
- 新增 `gb_font_is_changfangsong` 取决于模板；若模板未设仿宋将 ⚠（用户可关闭开关）
- 新增 `gb_paper_size_correct` 在 297×210 标准 sheet 下 ✅
- 新增 `gb_has_section_view_or_skipped` 历史 ❌；用户可改 `require_section=false` 立即转 ✅
