# 公司 2D 工程图对标规范（基于 41 张现有 SLDDRW 自动归纳）

> 数据来源：`3D转2D测试图纸\` 下 41 张 SLDDRW，通过 SolidWorks COM (`GetCurrentSheet/GetProperties2/GetFirstView/CustomPropertyManager`) 全量扫描得到。统计原始数据：[drw_full_stats.json](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/.trae/specs/study-solidworks-skill/drw_full_stats.json)

## 1. 图纸基本规范（强制）
| 项 | 公司标准 | 说明 |
|---|---|---|
| 纸张 | **A4 横向**（297×210 mm，`paper_code=6 swDwgPaperA4size`） | 41/41 一致，新出图必须延续 |
| 投影法 | **第一角投影**（`firstAngle=1`） | 41/41 一致；DriveWorks/3rdAngle 不允许 |
| 默认比例 | **1:1**（20/41）；机加工小件常用 2:1/5:1，大件用 1:2~1:5 | 出图时按零件最大轮廓自动适配（见 §5） |
| 单位 | 长度 mm（`swUnitsLinear=2`），角度 度 | 标注精度小数位默认 0（整数尺寸） |
| 字体 | SolidWorks 默认 + 文字高度 ≈ 3 mm | `swDetailingNoteTextFont` |
| 箭头 | Height 3 mm / Length 3.5 mm | `GetUserPreferenceDoubleValue(0/1)` |
| 模板 | `*.drwdot`（建议放统一目录，由 `GetUserPreferenceStringValue(26)` 指向） | 当前 41 张 `GetTemplateName=""` 表示走默认模板 |

## 2. 标题栏 / 自定义属性（13 项强制存在）
所有图纸都包含这 13 个 Custom Properties，按下表填写后会被标题栏 `$PRP:"xxx"` 自动引用：

| 键名 | 含义 | 示例 / 类型 |
|---|---|---|
| `SWFormatSize` | 图纸幅面（仅记录，自动） | `210mm*297mm` |
| `机型` | 项目机型代号 | LB26001、QTN-0488 等 |
| `品名` | 零件中文名 | 上模板、固定件 A、仿生头 |
| `图号` | 零件图号 | LB26001-A-04-001 |
| `类别` | 加工类别 | **机加工** / 钣金 / 焊件 |
| `数量` | 单图纸件数 | `1`（默认） |
| `材质` | 中文材质 | 1060 铝、SUS304… |
| `表面处理` | 中文表处 | 阳极氧化、无、镀镍… |
| `设计` | 设计者签名 | 名字拼音/工号 |
| `日期` | 出图日期 | YYYY-MM-DD |
| `UNIT_OF_MEASURE` | 单位 | mm |
| `Material` | 英文材料（同步用，方便 BOM） | AL6061-T6 |
| `重量` | 重量 (g) | 由 `MassProperties` 自动写回 |

> ⚠️ 出图脚本必须确保以上 13 个键都存在；缺失或为空时给警告，让人工补齐再出 PDF。

## 3. 视图组合规范（按统计反推）
- 默认视图：`*前视` 主视图 + `*上视`（俯视）+ `*右视`（如必要）+ `*等轴测` 一张参考视图。
- 41 张样本里出现频次最高的是 **type=4 投影视图（83 个）+ type=7 命名视图（65 个）**，平均每张图 ≈ 3~4 个视图。
- 主视图方向应**按零件最长轴水平**摆放；
- 如有内部腔体或非贯穿孔，必须再加 1 张**剖视图**（type=12 swDrawingSectionView）。
- 局部放大视图（type=8 swDrawingDetailView）按需加，比例 **2× 当前 sheet 比例**。

## 4. 标注规范
| 类别 | 规则 |
|---|---|
| 尺寸 | 优先 **导入模型项**（`InsertModelAnnotations3(0, 32, True, True, False, False)`），再人工拖位；尺寸文字字高 3 mm，箭头 Height/Length=3/3.5 mm |
| 中心标记 / 中心线 | 圆/弧自动加（统计中 `CenterMark`、`DimensionLine` 占比很高） |
| 公差 | 默认通用公差（标题栏注明 GB/T 1804-m）；关键尺寸单独写 ±公差 |
| 表面粗糙度 | 用 `swSfSym`（type=9）+ Ra 默认 3.2，关键面 1.6/0.8 |
| 形位公差 | 用 `swGTOL`（type=3）+ 基准 `swDatumTag`（type=4），按 GB/T 1182 |
| 注释 / 技术要求 | 右上或左下区块；`swNote`（type=2）；常用模板：①未注圆角 R0.5 ②去毛刺 ③未注公差按 GB/T 1804-m |
| 剖面线 | type=15 `AreaHatch`，由 SolidWorks 自动生成；保持 ANSI31 标准 |

## 5. 出图自动比例规则
1. 取零件外形最大尺寸 `L = max(bbox.x, bbox.y, bbox.z)`（米）。
2. 视图最大可放尺寸 `D = 0.10 m`（A4 减去标题栏后单视图边长上限）。
3. 候选比例集合（公司样本里出现过的）：`5:1, 3:1, 2:1, 1:1, 1:2, 1:3, 1:4, 1:5`。
4. 选择最大的比例 `s`，使得 `L * s ≤ D`。

## 6. 输出物（每个零件出图必交付）
- `<图号>.SLDDRW`（落到与 SLDPRT 同目录）
- `<图号>.PDF`（A4 横向，1 页）
- `<图号>.DXF`（全图，便于激光/线切割对照）
- `<图号>_review.json` + 4 视角 BMP（`sw_review.run_review`）

## 7. 程序化访问 API 速查
- 读 Sheet 属性：`drw.GetCurrentSheet().GetProperties2()` → `[paperCode, templateIn, scaleNum, scaleDen, firstAngle, width_m, height_m, useCustom]`
- 设 Sheet：`drw.SetupSheet5(name, paperCode, templateIn, scaleNum, scaleDen, firstAngle, templatePath, w, h, "", True)`
- 添加视图：`drw.CreateDrawViewFromModelView3(part_path, "*Front" | "*Top" | "*Right" | "*Isometric", x, y, 0)` → `IView`，再 `view.ScaleRatio = (1.0, 1.0/scale)`
- 自动尺寸：`drw.Extension.InsertModelAnnotations3(0, 32, True, True, False, False)`
- 写自定义属性：`drw.Extension.CustomPropertyManager("").Add3(name, swCustomInfoText=30, value, swCustomPropertyDeleteAndAdd=2)`
- 出 PDF：`pdf=sw.GetExportFileData(1); pdf.SetSheets(0, [sheetName]); drw.Extension.SaveAs(out, 0, 1, pdf, errors, warnings)`
- 出 DXF：`drw.Extension.SaveAs(out_dxf, 0, 1, VARIANT(VT_DISPATCH,None), errors, warnings)`

## 8. 不合规的常见情形（用于自审查）
- ❌ 纸张不是 A4 → 规范化为 A4 横向
- ❌ 投影法不是第一角 → `SetupSheet5(... firstAngle=1 ...)`
- ❌ 13 个标题栏键缺失或为空 → 报警并跳过 PDF 输出
- ❌ 视图为空（仅图框） → 重新调用 `CreateDrawViewFromModelView3`
- ❌ 比例不在样本集 `{5:1,3:1,2:1,1:1,1:2,1:3,1:4,1:5}` → 取最近值

