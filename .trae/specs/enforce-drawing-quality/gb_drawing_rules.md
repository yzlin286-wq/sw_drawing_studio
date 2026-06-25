# 中国机加工 2D 制图核心 GB 规范 + SolidWorks API 落地手册

> 适用范围：基于 SolidWorks 2025 的工程图自动化生成（pywin32 / COM）。
> 本文档把 GB/T 14689、14690、14691、4457.4、17452、4458.4、131-2006、1182-2008、1804-m 中
> 与 2D 工程图直接相关的核心条款，逐条映射到 `IDrawingDoc` / `IModelDocExtension` /
> `ILayerMgr` 的具体调用与正确参数（米单位）。

---

## 1. 图纸幅面 (GB/T 14689)

### 1.1 幅面尺寸（基本幅面 A0~A4，单位 mm）

| 代号 | 横向 (B×L)   | 纵向 (B×L)   | 周边边框 c | 装订侧边框 a |
|------|--------------|--------------|------------|--------------|
| A0   | 1189 × 841   | 841 × 1189   | 10         | 25           |
| A1   | 841 × 594    | 594 × 841    | 10         | 25           |
| A2   | 594 × 420    | 420 × 594    | 10         | 25           |
| A3   | 420 × 297    | 297 × 420    | 10         | 25           |
| A4   | 297 × 210    | 210 × 297    | 5          | 25           |

### 1.2 图框与标题栏

- 图框线粗：**0.7 mm**（粗实线）。
- 标题栏（A4）尺寸：**30 mm（高） × 130 mm（宽）**，靠右下角。
- 标题栏外框线粗 0.7 mm，内分隔线粗 0.35 mm。
- 第一角投影符号（中国标准）必须出现在标题栏正上方。

### 1.3 SolidWorks API 调用

```python
# 创建 A4 横向工程图（米单位）
drw = swApp.NewDocument(template_path, 0, 0.297, 0.210)
# 设置 sheet 参数（关键：paperSize=6 即 swDwgPaperA4size 横向；firstAngle=True）
drw.SetupSheet5(
    "Sheet1",   # name
    6,          # paperSize: 6=swDwgPaperA4size (Landscape)
    13,         # templateIn: 13=swDwgTemplateNone (用自定义图框)
    1,          # scale1 (numerator)
    1,          # scale2 (denominator)
    True,       # firstAngle = True (中国第一角投影)
    "",         # templateName
    0.297,      # width (m)
    0.210,      # height (m)
    "",         # propertyViewName
    True        # zoneSetup
)
```

### 1.4 对应 SolidWorks 调用快速表（图纸幅面）

| GB 条款            | SolidWorks API                                  | 关键参数                                |
|--------------------|--------------------------------------------------|-----------------------------------------|
| A4 横 297×210      | `IDrawingDoc.SetupSheet5`                        | paperSize=6, w=0.297, h=0.210           |
| A4 纵 210×297      | `IDrawingDoc.SetupSheet5`                        | paperSize=8 (A4 Portrait), w=0.210      |
| A3 横 420×297      | `IDrawingDoc.SetupSheet5`                        | paperSize=5 (swDwgPaperA3size)          |
| 第一角投影         | `SetupSheet5` 第 6 参                            | firstAngle=True                         |
| 图框线粗 0.7 mm    | `LayerMgr.AddLayer("Frame",..,8)`                | weight=8 (=0.70mm 索引)                 |

---

## 2. 比例 (GB/T 14690)

### 2.1 标准比例集

- 放大：**5:1, 2:1**（必要时 50:1, 20:1, 10:1）
- 原值：**1:1**
- 缩小：**1:2, 1:5, 1:10, 1:20**（必要时 1:50, 1:100）

### 2.2 视图比例选取规则

- 主视图首先尝试 **1:1**；若塞不进图框可用区，则按 1:2 → 1:5 → 1:10 顺序回退。
- 视图比例必须取标准集中的值，**不允许 1:3、1:4、1:7 等非标准比例**。
- 同张图所有视图原则上同一比例；局部放大图可用更大比例并标注。

### 2.3 SolidWorks API 调用

```python
view = drw.CreateDrawViewFromModelView3(model_path, "*Front", x, y, 0)
view.ScaleDecimal = 1.0    # 1:1
# 1:2 → 0.5；2:1 → 2.0；1:5 → 0.2
view.ScaleRatio = (1, 2)   # 工厂推荐写法（保留可读分数）
```

### 2.4 对应 SolidWorks 调用快速表（比例）

| GB 比例 | `ScaleDecimal` | `ScaleRatio` |
|---------|----------------|--------------|
| 5:1     | 5.0            | (5, 1)       |
| 2:1     | 2.0            | (2, 1)       |
| 1:1     | 1.0            | (1, 1)       |
| 1:2     | 0.5            | (1, 2)       |
| 1:5     | 0.2            | (1, 5)       |
| 1:10    | 0.1            | (1, 10)      |
| 1:20    | 0.05           | (1, 20)      |

---

## 3. 字体 (GB/T 14691)

### 3.1 字体规则

- 汉字：**长仿宋体**（GB/T 14691 规定），字宽 = 字高 × 2/3。
- 数字与字母：**直体或斜体（斜 75°）**，宽高比 7:10。
- 标准字高（mm）：**1.8 / 2.5 / 3.5 / 5 / 7 / 10 / 14 / 20**。
- 工程图常用：**汉字 5 mm；尺寸数字 3.5 mm；标题栏标题 7 mm 或 10 mm**。

### 3.2 SolidWorks API 调用

```python
# 设置默认 Note 字高 = 5 mm（米单位）
drw.SetUserPreferenceDoubleValue(89, 0.005)   # 89 = swDetailingNoteTextHeight
# 设置默认尺寸字高 = 3.5 mm
drw.SetUserPreferenceDoubleValue(91, 0.0035)  # 91 = swDetailingDimTextHeight

# 单条 Note 字体改为长仿宋
note = ann.GetSpecificAnnotation()  # IAnnotation
fmt  = note.GetTextFormat(0)        # ITextFormat
fmt.TypeFaceName = "仿宋_GB2312"
fmt.CharHeight   = 0.005             # 5 mm
fmt.Italic       = False
fmt.Bold         = False
note.SetTextFormat(0, True, fmt)     # useDoc=False 才能生效
```

### 3.3 对应 SolidWorks 调用快速表（字体）

| GB 字号 | 高度 (m) | API                                              |
|---------|----------|--------------------------------------------------|
| 3.5     | 0.0035   | `SetUserPreferenceDoubleValue(91, 0.0035)`       |
| 5       | 0.005    | `SetUserPreferenceDoubleValue(89, 0.005)`        |
| 7       | 0.007    | `SetUserPreferenceDoubleValue(89, 0.007)`        |
| 10      | 0.010    | `SetUserPreferenceDoubleValue(89, 0.010)`        |
| 长仿宋  | —        | `ITextFormat.TypeFaceName = "仿宋_GB2312"`       |

---

## 4. 线型 (GB/T 4457.4)

### 4.1 七大线型

| 线型       | 用途                       | 线粗     | SolidWorks 枚举                  |
|------------|----------------------------|----------|----------------------------------|
| 粗实线     | 可见轮廓 / 图框            | d=0.5/0.7| `swLineCONTINUOUS (0)`           |
| 细实线     | 尺寸线 / 尺寸界线 / 剖面线 | d/2      | `swLineCONTINUOUS (0)`           |
| 虚线       | 不可见轮廓                 | d/2      | `swLineHIDDEN (1)`               |
| 细点划线   | 中心线 / 对称中心          | d/2      | `swLineCHAIN (3)`                |
| 双点划线   | 极限位置 / 假想轮廓        | d/2      | `swLinePHANTOM (4)`              |
| 波浪线     | 断裂边界                   | d/2      | 草图 + `swLineCONTINUOUS`        |
| 双折线     | 长断裂                     | d/2      | 草图 + `swLineZIGZAG (5)`        |

### 4.2 SolidWorks 图层 API

```python
lm = drw.GetLayerManager()  # ILayerMgr
# AddLayer(name, desc, color_RGB, lineStyle, lineWeight)
lm.AddLayer("Outline",  "粗实线",   0x000000, 0, 8)   # weight 8 = 0.70mm
lm.AddLayer("Dim",      "细实线",   0x000000, 0, 4)   # weight 4 = 0.25mm
lm.AddLayer("Hidden",   "虚线",     0x000000, 1, 4)
lm.AddLayer("Center",   "中心线",   0xFF0000, 3, 4)
lm.AddLayer("Phantom",  "双点划线", 0x800080, 4, 4)
```

### 4.3 对应 SolidWorks 调用快速表（线型）

| GB 名称   | lineStyle 索引 | 默认 weight | 推荐颜色 RGB |
|-----------|----------------|-------------|--------------|
| 粗实线    | 0              | 8 (0.70 mm) | 0x000000     |
| 细实线    | 0              | 4 (0.25 mm) | 0x000000     |
| 虚线      | 1              | 4           | 0x808080     |
| 中心线    | 3              | 4           | 0xFF0000     |
| 双点划线  | 4              | 4           | 0x800080     |
| 折断线    | 5              | 4           | 0x000000     |

---

## 5. 视图布局 (GB/T 17452)

### 5.1 投影规则

- 中国采用 **第一角投影法**（与欧洲一致，与美国第三角相反）。
- 主视图（前视）必须选择 **信息量最大** 的方向（特征最多、轮廓最完整、加工基准面）。
- **上视图位于主视图的正下方**（第一角：物体在投影面与观察者之间）。
- **左视图位于主视图的正右方**。
- 后视图放右视图的右侧；下视图放主视图正上方；右视图放主视图正左方。

### 5.2 间距与边距

- 视图与视图之间的间距 ≥ **20 mm**。
- 视图与图框边的边距 ≥ **10 mm**。
- 标题栏区不放置视图。

### 5.3 避免视图重叠的核心原则

> **每个视图占用一个互不相交的矩形 outline。**
> 算法：先用 `view.GetOutline()` 取每个视图的 (xmin, ymin, xmax, ymax)，
> 再以 20 mm 为最小间距做矩形不重叠校验；冲突时按 “主→上→左→等轴测” 顺序
> 沿 +X / -Y 方向平移，直到所有矩形互不相交且都在图框可用区内。

### 5.4 SolidWorks API 调用

```python
view = drw.CreateDrawViewFromModelView3(path, "*Front", 0.10, 0.15, 0)
proj_top  = drw.CreateUnfoldedViewAt3(0.10, 0.05, 0, False)  # 主视下方
proj_left = drw.CreateUnfoldedViewAt3(0.20, 0.15, 0, False)  # 主视右方
iso       = drw.CreateDrawViewFromModelView3(path, "*Isometric", 0.24, 0.05, 0)

# 校验 outline 不重叠
xmin, ymin, xmax, ymax = view.GetOutline()
```

### 5.5 对应 SolidWorks 调用快速表（视图布局）

| 操作              | API                                       | 关键参数                |
|-------------------|-------------------------------------------|-------------------------|
| 主视图            | `CreateDrawViewFromModelView3`            | viewName="*Front"       |
| 投影上视/左视     | `CreateUnfoldedViewAt3`                   | x, y, z（米）           |
| 等轴测            | `CreateDrawViewFromModelView3`            | viewName="*Isometric"   |
| 取视图边界        | `IView.GetOutline()`                      | 返回 (xmin..ymax) 米    |
| 移动视图          | `IView.Position = (x, y)`                 | 米                      |

---

## 6. 尺寸标注 (GB/T 4458.4)

### 6.1 标注总则

- 标注顺序：**定型 → 定位 → 其他**。
  - 定型：直径、半径、长宽高、孔深。
  - 定位：孔距、基准距离、对称中心距。
  - 其他：倒角、圆角、退刀槽。
- 尺寸数字字高：**3.5 mm**；尺寸线粗：**0.25 mm**（细实线）。
- 箭头长 = 字高 × 1.5 ≈ **5 mm**；箭头宽 = 字高 × 0.4。
- 同一图样上同类尺寸（如孔径）必须使用同一表达方式。
- 尺寸数字一律不可被任何线穿过；遇线必须断开尺寸线让位。

### 6.2 SolidWorks API 调用

```python
# 一键插入模型尺寸到工程图
ext = drw.Extension
ok = ext.InsertModelAnnotations3(
    0,        # source: 0 = swImportModelItemsFromEntireModel
    32,       # types : 32 = swDimensionMarkedForDrawing
    True,     # allViews
    True,     # importItemsIntoAllViews
    False,    # ignoreHidesInDoc
    False     # includeItemsFromHiddenFeatures
)

# 单条线性尺寸
dim = drw.AddDimension2(x, y, 0)   # 在 (x,y) 处放置
# 设置箭头与字高
drw.SetUserPreferenceDoubleValue(91,  0.0035)   # 字高 3.5 mm
drw.SetUserPreferenceDoubleValue(105, 0.005)    # 箭头长 5 mm = swDetailingArrowLength
```

### 6.3 对应 SolidWorks 调用快速表（尺寸）

| GB 项                | API                                             | 参数                               |
|----------------------|--------------------------------------------------|------------------------------------|
| 导入模型尺寸         | `Extension.InsertModelAnnotations3`              | source=0, types=32                 |
| 添加单条尺寸         | `IDrawingDoc.AddDimension2(x, y, z)`             | 米                                 |
| 字高 3.5 mm          | `SetUserPreferenceDoubleValue(91, 0.0035)`       | swDetailingDimTextHeight           |
| 箭头长 5 mm          | `SetUserPreferenceDoubleValue(105, 0.005)`       | swDetailingArrowLength             |
| 尺寸线粗 0.25 mm     | 图层 weight=4                                    | `LayerMgr.AddLayer(...,4)`         |

---

## 7. 表面粗糙度 (GB/T 131-2006)

### 7.1 标注规则

- Ra 标准值（μm）：**0.4 / 0.8 / 1.6 / 3.2 / 6.3 / 12.5**（首选）；细分 0.1 / 0.2 / 25 / 50。
- 机加工件 **默认 Ra 3.2**；铸件、毛坯默认 Ra 12.5。
- 符号种类：基本符号 √（不指定）、扩展 √+实线（去除材料）、√+圆圈（不去除材料）。
- 标注位置：标在轮廓线、尺寸界线或引出线上，**符号尖端必须指向被加工表面**。
- 不在图样中重复出现的统一粗糙度，可在标题栏附近用 “其余 √Ra3.2” 标示。

### 7.2 SolidWorks API 调用

```python
ext = drw.Extension
sf = ext.InsertSurfaceFinishSymbol3(
    1,           # symbolType: 1 = swSFRequireRemoval (去除材料)
    -1,          # lay
    "3.2",       # roughness1 (Ra 上限)
    "",          # roughness2
    "",          # otherValues
    "",          # samplingLength
    "",          # machiningAllowance
    True,        # leader
    x, y, z      # 放置坐标 (m)
)

# 已知问题：SW2025 + pywin32 marshaling 偶现失败 → 用 Note 兜底
if sf is None:
    drw.CreateText2("Ra 3.2", x, y, 0, 0.005, 0)
```

### 7.3 对应 SolidWorks 调用快速表（粗糙度）

| GB 表达      | API                                            | 关键参数                  |
|--------------|------------------------------------------------|---------------------------|
| √ 基本       | `InsertSurfaceFinishSymbol3(0,..)`             | symbolType=0              |
| √ 去除材料   | `InsertSurfaceFinishSymbol3(1,..)`             | symbolType=1              |
| √ 不去除材料 | `InsertSurfaceFinishSymbol3(2,..)`             | symbolType=2              |
| Ra 值        | roughness1 字段                                 | "0.8" / "1.6" / "3.2"     |
| 兜底 Note    | `IDrawingDoc.CreateText2(text, x,y,z, h, ang)` | h=0.0035 (3.5 mm)         |

---

## 8. 形位公差 (GB/T 1182-2008) + 通用公差 (GB/T 1804-m)

### 8.1 形位公差 14 种代号

| 类别     | 项目     | 代号符号 |
|----------|----------|----------|
| 形状公差 | 直线度   | —        |
|          | 平面度   | ▱        |
|          | 圆度     | ○        |
|          | 圆柱度   | ⌭        |
|          | 线轮廓度 | ⌒        |
|          | 面轮廓度 | ⌓        |
| 方向公差 | 平行度   | ∥        |
|          | 垂直度   | ⊥        |
|          | 倾斜度   | ∠        |
| 位置公差 | 位置度   | ⌖        |
|          | 同轴度   | ◎        |
|          | 对称度   | ⌯        |
| 跳动公差 | 圆跳动   | ↗        |
|          | 全跳动   | ↗↗       |

### 8.2 基准

- 基准代号：大写英文字母 **A、B、C…**（不用 I、O、Q、X、Y、Z）。
- 基准符号为带方框的字母 + 三角形指引线。

### 8.3 通用公差 GB/T 1804-m（中等级）

| 公称尺寸段 (mm) | 0.5~3 | >3~6 | >6~30 | >30~120 | >120~400 | >400~1000 |
|-----------------|-------|------|-------|---------|----------|-----------|
| 极限偏差 ±      | 0.1   | 0.1  | 0.1   | 0.2     | 0.3      | 0.5       |

未注公差按上表自动适用，工程图标题栏注 "GB/T 1804-m"。

### 8.4 SolidWorks API 调用

```python
ext = drw.Extension

# 形位公差框
gtol = ext.InsertGTOL2(
    "",          # frameValues 由后续设置
    True,        # leader
    x, y, z      # 放置点 (m)
)
gtol.SetFrameValues2(
    0,           # frameIndex
    "POSITION",  # 形位项目
    "0.05",      # 公差值
    "M",         # 材料条件 (M/L/S 或空)
    "A",         # 基准1
    "B",         # 基准2
    "C"          # 基准3
)

# 基准符号
datum = ext.InsertDatumTagSymbol2(
    x, y, z,     # 放置点
    1,           # leaderType: 1 = swDatumLeaderFilledTriangle
    "A"          # 基准字母
)
```

### 8.5 对应 SolidWorks 调用快速表（形位 / 通用公差）

| GB 项              | API                                            | 关键参数                       |
|--------------------|------------------------------------------------|--------------------------------|
| 插入形位公差框     | `Extension.InsertGTOL2`                        | x, y, z, leader=True           |
| 设置框内值         | `IGtol.SetFrameValues2`                        | symbol, tol, mod, A, B, C      |
| 插入基准符号       | `Extension.InsertDatumTagSymbol2`              | x, y, z, leaderType=1, "A"     |
| 通用公差 1804-m    | `ITitleBlock` Note                             | "未注公差按 GB/T 1804-m"       |

---

## 9. 总览速查表

### 9.1 主视图选择决策表（按零件类型 → 推荐主视图方向）

| 零件类型           | 典型特征                | 推荐主视图方向         | SolidWorks viewName |
|--------------------|-------------------------|------------------------|---------------------|
| 轴类（细长回转体） | 多台阶 / 螺纹 / 倒角    | 轴线水平，键槽朝上     | `*Front`            |
| 盘盖类（扁平回转） | 多孔 / 沉孔 / 螺纹孔    | 主视取剖视，俯视看孔   | `*Top` 作主视       |
| 箱体类             | 多面加工 / 内腔         | 信息最多面 + 全剖      | `*Front`            |
| 叉架类             | 不规则 + 加强筋         | 工作位置 / 安装基准面  | `*Front`            |
| 板类（钣金）       | 厚度均匀 / 多孔阵列     | 大面朝向观察者         | `*Front`            |
| 标准件（螺丝/销）  | 回转 + 头部             | 轴线水平，头部朝左     | `*Right` 翻转       |

### 9.2 视图间距推荐表（A4 横 297×210，4 视图布局，单位 mm）

| 视图     | 矩形 outline (xmin, ymin, xmax, ymax) | 占用区域大小 |
|----------|----------------------------------------|--------------|
| 前视图   | (15, 110, 135, 195)                    | 120 × 85     |
| 上视图   | (15, 25,  135, 95)                     | 120 × 70     |
| 右视图   | (155, 110, 270, 195)                   | 115 × 85     |
| 等轴测   | (155, 25,  270, 95)                    | 115 × 70     |
| 标题栏   | (137, 5,   267, 35)（30×130）          | 30 × 130     |

> 视图间距：水平 20 mm（135↔155），垂直 15 mm（95↔110），均 ≥ GB 最小 20/10 mm。

### 9.3 字高映射表（GB 字号 → SolidWorks API 数值，米单位）

| GB 字号 (mm) | 米单位  | 用途             | SolidWorks PreferenceID            |
|--------------|---------|------------------|------------------------------------|
| 1.8          | 0.0018  | 角注 / 副标      | 89 = NoteTextHeight                |
| 2.5          | 0.0025  | 副尺寸           | 91 = DimTextHeight                 |
| 3.5          | 0.0035  | 尺寸数字（默认） | 91 = DimTextHeight                 |
| 5            | 0.005   | 汉字默认 / Note  | 89 = NoteTextHeight                |
| 7            | 0.007   | 标题栏小字       | 89                                 |
| 10           | 0.010   | 标题栏标题       | 89                                 |
| 14           | 0.014   | 图号             | 89                                 |
| 20           | 0.020   | 大幅面图名       | 89                                 |

### 9.4 线宽映射表（GB d 值 → SolidWorks layer weight 枚举）

| GB 线宽 (mm) | SW weight 索引 | swLineWeights_e            | 用途           |
|--------------|----------------|----------------------------|----------------|
| 0.13         | 1              | swLW_THIN                  | 极细           |
| 0.18         | 2              | swLW_NORMAL_THIN           | 细辅助线       |
| 0.25         | 4              | swLW_NORMAL                | 细实线 / 尺寸  |
| 0.35         | 5              | swLW_NORMAL_THICK          | 中粗           |
| 0.50         | 6              | swLW_THICK                 | 粗实线（标准） |
| 0.70         | 8              | swLW_THICK2                | 图框 / 加粗轮廓|
| 1.00         | 10             | swLW_THICK3                | 强调线         |
| 1.40         | 12             | swLW_THICK4                | 特殊强调       |

### 9.5 比例选取算法（伪代码）

```text
function pickScale(bbox_mm, frame_mm):
    # bbox_mm：零件最大轮廓 (W, H)
    # frame_mm：图框可用区 (Wf, Hf)，A4 横向 ≈ (250, 160)，预留视图间距后取 100×100
    target = 100  # 单视图允许的最大尺寸 mm
    standard_scales = [5, 2, 1, 0.5, 0.2, 0.1, 0.05, 0.02, 0.01]
    max_dim = max(bbox_mm.W, bbox_mm.H)

    for s in standard_scales:          # 从大到小尝试
        if max_dim * s <= target:      # 关键判据：放大后塞得下
            return s                   # 返回最大可用比例
    return 0.01                        # 最小兜底 1:100

# 用法
scale = pickScale((W, H), (250, 160))
view.ScaleDecimal = scale
```

---

## 10. 8 章 + 5 表 索引

- 章节：图纸幅面 / 比例 / 字体 / 线型 / 视图布局 / 尺寸标注 / 表面粗糙度 / 形位公差。
- 速查表：主视图决策 / 视图间距 / 字高映射 / 线宽映射 / 比例算法。

---

## 11. QC 开关位（drw_quality_check.py 扩展规则）

> 所有 GB 强化规则默认开启；如需在临时项目上关闭，可在 `drw_quality_check.py` 顶部修改 `GB_RULE_TOGGLES`（或在外部设环境变量后续支持）。

| 规则 key | 默认 | 说明 |
|---|---|---|
| `gb_titlebar_complete` | True | 标题栏 6 组核心字段（品名/机型、图号、材质/Material、数量、设计、日期）至少各填 1 项 |
| `gb_font_is_changfangsong` | True | 至少 1 个 NoteBlock 字体名含「仿宋」/「FangSong」 |
| `gb_paper_size_correct` | True | sheet 宽×高 与 A0~A4（横/纵）任一标准幅面差 ≤ 5mm |
| `gb_has_section_view_or_skipped` | True | 至少 1 个 IView.Type==3 剖视图；可关闭 `GB_REQUIRE_SECTION=False` |
| `gb_scale_in_extended_set` | True | sheet.scale ∈ GB/T 14690 全集（不含 1:3 / 1:4） |

注：原 `scale_in_set` 同步收紧至同一白名单（去除 1:3、1:4、3:1）。

