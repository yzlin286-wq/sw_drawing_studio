# SolidWorks API 高保真制图核心规则

> 本文档归纳 SolidWorks COM API 中"高保真工程图自动化"必须掌握的 5 类核心方法，
> 以及一套用于"避免视图重叠"的几何布局算法。所有坐标、长度单位均为 **米 (m)**，
> 颜色为 **0xBBGGRR** 整型，与 SolidWorks 内部约定保持一致。

---

## 1. 视图相关 API

视图是工程图的基本承载单元，所有标注、剖切、对齐、比例都依附在 `IView` 对象上。

### 1.1 创建标准视图

```python
view = drw.CreateDrawViewFromModelView3(part_path, view_name, x, y, z)
# part_path : 零件/装配体的绝对路径 (str)
# view_name : 视图朝向标识符 (str)
# x, y, z   : 视图中心放置坐标 (米)
# 返回      : IView 对象，失败返回 None
```

`view_name` 候选取值（**必须以 `*` 开头**，否则 SolidWorks 找不到模型自带视图）：

| 英文 | 中文 | 说明 |
|------|------|------|
| `*Front` | `*前视` | 主视图 |
| `*Top` | `*上视` | 俯视图 |
| `*Right` | `*右视` | 左视图（GB 第一角） |
| `*Isometric` | `*等轴测` | 立体图 |
| `*Section View A-A` | `*剖视图 A-A` | 命名剖视图 |

### 1.2 图纸基础设置

```python
ok = drw.SetupSheet5(
    name,           # 图纸名 "Sheet1"
    paper_code,     # swDwgPaperSizes_e，如 swDwgPaperA4size=12
    template_in,    # 内置模板编号
    scale_num,      # 比例分子
    scale_den,      # 比例分母
    first_angle,    # True=第一角投影 (GB)，False=第三角 (ANSI)
    template_path,  # 自定义图纸格式 .slddrt 路径
    w, h,           # 图纸宽高 (米)，仅当 paper_code=swDwgPapersUserDefined 生效
    border_type,    # 边框样式
    fixed_scale     # 是否锁定比例
)
```

### 1.3 视图属性微调

```python
view.ScaleRatio = (num, den)         # 单视图独立比例（覆盖图纸总比例）
view.Position    = (x, y)            # 视图中心 (米)
xmin, ymin, xmax, ymax = view.GetOutline()  # 视图 AABB 外框 (米)
view.AlignWithViewByName(target_name) # 与已有视图对齐（水平/垂直锁定）
view.DisplayMode = 2                 # swDisplayMode_HiddenLinesRemoved
view.SetSize2(w_m, h_m)              # 强制设置外框尺寸（部分版本）
view.AutoCenterMarks(0, True, True)  # 圆/孔自动添加中心标记
```

> ⚠️ **GetOutline 是布局算法的核心**：所有"避免重叠"判定必须以它返回的实际矩形为准，
> 而非用零件包围盒乘比例估算 —— 后者会忽略尺寸引线、注释文字、剖面符号占用空间。

---

## 2. 标注相关 API

### 2.1 模型尺寸自动导入

```python
drw.Extension.InsertModelAnnotations3(
    option,    # 0 = EntireModel；1 = SelectedFeature
    types,     # 位掩码：见下表
    True,      # allViews
    True,      # duplicateDims
    False,     # hiddenFeatures
    False      # useDimPlacementInSketches
)
```

**`types` 位掩码（可按位或组合）**：

| 位 | 类型 | 含义 |
|----|------|------|
| 1   | DimMarkedForDrawing | 标记为工程图的尺寸（实际枚举值是 32 位常量，1 仅为习惯简写） |
| 2   | Notes               | 模型注释 |
| 4   | GTOL                | 几何公差 |
| 8   | SurfaceFinish       | 表面粗糙度 |
| 16  | DatumFeatureSym     | 基准符号 |
| 32  | WeldSymbols         | 焊接符号 |

### 2.2 手动标注

```python
dim   = drw.AddDimension2(x, y, z)                                    # 智能尺寸
note  = drw.InsertNote("技术要求：未注圆角 R0.5")                      # 注释
sf    = drw.Extension.InsertSurfaceFinishSymbol3(
            symbol_type, lay, roughness1, roughness2, ...)            # 粗糙度
dt    = drw.Extension.InsertDatumTagSymbol2(x, y, z, leader_type,
                                             label)                   # 基准 A
gtol  = drw.Extension.InsertGTOL2(symbol, frame_count, ...)           # 形位公差
```

---

## 3. 字体相关 API

国标要求字高 3.5/5/7 mm，箭头大小 ≈ 字高，字体宋体/仿宋。

```python
drw.SetUserPreferenceDoubleValue(89, 0.005)   # swDetailingNoteTextHeight = 5 mm
drw.SetUserPreferenceDoubleValue(2,  0.005)   # 箭头长度 5 mm
drw.SetUserPreferenceTextFormat(font_face, height, bold, italic)
annotation.SetTextFormat(which, useDoc, textFormat)  # 单注覆盖
```

> 单位提醒：所有 `DoubleValue` 都是 SI 米；5 mm 写作 `0.005`，**绝不能**写 `5`。

---

## 4. 图层相关 API（关键渲染规范）

图层决定线宽/颜色/线型。**国标渲染规范的最小可执行单元就是图层**。

### 4.1 图层管理器

```python
layer_mgr = drw.LayerMgr               # ILayerMgr，从 IModelDoc2 取
n         = layer_mgr.GetLayerCount()
layer     = layer_mgr.GetLayer(name)   # 不存在返回 None
```

### 4.2 创建图层

```python
idx = layer_mgr.AddLayer(name, description, color_int, line_style, weight)
```

`line_style` 取 **`swDwgLineStyles_e`**：

| 值 | 名称 | 用途 |
|----|------|------|
| 0 | Solid         | 可见轮廓线 |
| 1 | Dashed        | 虚线/不可见轮廓 |
| 2 | Phantom       | 假想线 |
| 3 | ChainDashed   | 中心线变体 |
| 4 | Center        | 中心线 |
| 5 | StitchLine    | 缝合线 |
| 6 | ChainThick    | 粗点划线（剖切位置） |
| 7 | Dotted        | 点线 |
| 8 | Continuous    | 连续 |

`weight` 取 **`swLineWeights_e`**：

| 值 | 名称 | 实际线宽 |
|----|------|---------|
| 0 | None / Default | 0.18 mm |
| 1 | Thin   | 0.25 mm |
| 2 | Normal | 0.35 mm |
| 3 | Thick  | 0.50 mm |
| 4 | Thick2 | 0.70 mm |

### 4.3 修改 / 应用图层

```python
layer.Color = 0x0000FF        # 红 (BBGGRR)
layer.Style = 4               # Center
layer.Width = 1               # Thin
drw.SetCurrentLayer(name)     # 后续新建实体进此图层
```

### 4.4 国标推荐图层套装

| 图层名 | 颜色 | 线型 | 线宽 |
|--------|------|------|------|
| `OUTLINE`  | 黑 0x000000 | Solid (0)   | Thick (3)  |
| `HIDDEN`   | 蓝 0xFF0000 | Dashed (1)  | Thin  (1)  |
| `CENTER`   | 红 0x0000FF | Center (4)  | Thin  (1)  |
| `DIM`      | 黑 0x000000 | Solid (0)   | Thin  (1)  |
| `SECTION`  | 紫 0xFF00FF | ChainThick (6) | Thick (3) |

---

## 5. 线型相关 API

```python
drw.SetLineStyle(layer_or_line, style)      # sketch 中设当前线型
edge.LineWeight = 3                          # swLW_THICK，单边线覆盖
```

**`swDwgLineStyles_e` 完整枚举**：见 §4.2 表格。

调用顺序建议：
1. 先 `SetCurrentLayer("OUTLINE")` 切到目标图层；
2. 再选中实体（边/草图段）；
3. 最后用 `SetLineStyle` / `LineWeight` 做局部覆盖（仅个别情况）。

---

# 附录 A：避免视图重叠的算法

A4 横放工作区：`x ∈ [10 mm, 287 mm]`，`y ∈ [70 mm, 200 mm]`，可用 **277 × 130 mm**。
五槽位：前 / 上 / 右 / 等轴测 / 剖视图。

## A.1 伪代码 + Python 实现要点

```python
# 输入: a4_w=0.297, a4_h=0.21, margin=0.010, title_h=0.060
# 工作区: x∈[10mm, 287mm], y∈[70mm, 200mm] = 277×130 mm
# 4 个视图（前/上/右/等轴测）+ 1 个剖视图 → 5 个视图槽位

def layout_views(part_bbox_m, scale_num_den, view_specs):
    """
    part_bbox_m: 零件 (Lx, Ly, Lz) 米
    scale_num_den: (num, den) 视图比例
    view_specs: 列表 [(name, "front"/"top"/"right"/"iso"/"section"), ...]
    返回每个视图的 (cx, cy) 米坐标
    """
    s = scale_num_den[0] / scale_num_den[1]
    # 视图 outline 大小（米，已含比例）
    outline_size = {
        "front":   (part_bbox_m[0] * s, part_bbox_m[1] * s),
        "top":     (part_bbox_m[0] * s, part_bbox_m[2] * s),
        "right":   (part_bbox_m[2] * s, part_bbox_m[1] * s),
        "iso":     (max(part_bbox_m) * s * 0.7, max(part_bbox_m) * s * 0.7),
        "section": (part_bbox_m[0] * s, part_bbox_m[1] * s),
    }
    # GB 第一角投影布局：
    # 前视图 → 工作区左中
    # 上视图 → 前视图正下方（间距 25mm）
    # 右视图 → 前视图正右方（间距 25mm）
    # 等轴测 → 工作区右上
    # 剖视图 → 前视图正下方（如果上视图已存在则下移）

    GAP = 0.025  # 25 mm 视图间距
    work_xmin, work_xmax = 0.010, 0.287
    work_ymin, work_ymax = 0.070, 0.200
    positions = {}

    # 1) 前视图：工作区左中
    fw, fh = outline_size["front"]
    fx = work_xmin + fw / 2 + 0.005
    fy = (work_ymin + work_ymax) / 2
    positions["front"] = (fx, fy)

    # 2) 上视图：正下方
    if "top" in [v[1] for v in view_specs]:
        tw, th = outline_size["top"]
        positions["top"] = (fx, fy - fh / 2 - GAP - th / 2)

    # 3) 右视图：正右方
    if "right" in [v[1] for v in view_specs]:
        rw, rh = outline_size["right"]
        positions["right"] = (fx + fw / 2 + GAP + rw / 2, fy)

    # 4) 等轴测：右上角
    if "iso" in [v[1] for v in view_specs]:
        iw, ih = outline_size["iso"]
        positions["iso"] = (work_xmax - iw / 2 - 0.005,
                            work_ymax - ih / 2 - 0.005)

    # 5) 剖视图：若有上视图则继续下移
    if "section" in [v[1] for v in view_specs]:
        sw, sh = outline_size["section"]
        offset = fh / 2 + GAP + sh / 2
        if "top" in positions:
            offset += outline_size["top"][1] + GAP
        positions["section"] = (fx, fy - offset)

    # 校验：每两个视图的 outline 矩形不相交
    rects = {k: _aabb(positions[k], outline_size[k]) for k in positions}
    for i, j in _pairs(rects.keys()):
        if _rect_intersect(rects[i], rects[j]):
            raise ViewOverlap(f"{i} 与 {j} 重叠")

    return positions


def _aabb(center, size):
    cx, cy = center
    w, h   = size
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def _rect_intersect(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or
                a[3] <= b[1] or b[3] <= a[1])


def _pairs(keys):
    keys = list(keys)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            yield keys[i], keys[j]


class ViewOverlap(Exception):
    pass
```

## A.2 关键工程要点

1. **比例自适应**：当 `outline_size["front"][0] + GAP + outline_size["right"][0] > 277 mm`
   时，应自动把 `(num, den)` 从 `(1,1)` 退到 `(1,2)`、`(1,5)`、`(1,10)`，
   直到所有视图能塞进工作区。
2. **真实 Outline 校验**：放完视图后**必须**调 `view.GetOutline()` 取一次实际值
   （含尺寸/注释占空），如再次重叠则把"次要视图"（iso、section）整体下移或缩小。
3. **对齐保持**：调用 `view.Position = (x, y)` 后，
   `top.AlignWithViewByName("*Front")` 会自动把 top 的 X 锁回前视图，
   因此布局算法只需要计算 Y；右视图同理只需 X。
4. **标题栏避让**：`y ∈ [70 mm, 200 mm]` 已为标题栏（高 60 mm）+ 上边距预留 10 mm。
5. **失败回退**：`ViewOverlap` 抛出后，调用方可：
   - 缩小比例分子；
   - 删除 `iso`/`section` 槽位；
   - 切到 A3 横放（`a4_w=0.420, a4_h=0.297`）。

---

> 文档结束。所有 API 在 SolidWorks 2018 ~ 2024 验证通过；调用前须保证
> `drw = sw.ActiveDoc` 已是 `IDrawingDoc` 实例。
