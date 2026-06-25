# 强制图纸质量闭环（Enforce Drawing Quality）Spec

## Why
当前 `LB26001-A-04-001_v4.SLDDRW` 指标分 95/100，但实测打开后与对标 `LB26001-A-04-048/004` 相差过大、不具备可用性：视图布局错乱（左右上下重叠 / 跑出图框 / 比例失真）、尺寸堆叠或缺失、字体高度不符 GB 制图规范、剖视图缺失、图层未分类、标题栏 BlockInst 字段未真正填入。问题根因是：(1) 我们之前只学习了"对标统计平均值"层的规范，没掌握 **GB/T 17452-1998《技术制图 图样画法》、GB/T 4458 系列、ISO 128** 等中国机加工图纸**渲染级规范**；(2) SolidWorks API 的"视图布局/标注样式/图层/字体"调用需要更精细的方法，而非简单 `CreateDrawViewFromModelView3` + `RunCommand(826)`；(3) 缺少**质检 → 不合格自动回退并重绘**的闭环。

## What Changes
- **学习真正的中国机加工 2D 制图规范**：GB/T 17452 视图布局、GB/T 4457 线型、GB/T 4458.4 尺寸标注、GB/T 14689 图纸幅面、GB/T 1804-m 公差、字体高度 GB/T 14691（汉字 5/7/10mm，数字 3.5/5/7mm），以及表面粗糙度 GB/T 131、形位公差 GB/T 1182 的使用规则。把这些规范沉淀成 `gb_drawing_rules.md`。
- **学习 SolidWorks API 高保真制图调用规范**：视图自动化布局（避免重叠的算法）、显示模式（Wireframe/Hidden/Shaded with Edges）、线型映射、图层创建、字体覆盖、`InsertModelAnnotations3` 的全部 mark 选项、`AlignWithViewByName`、`SetSize2`、`Activate/EditViewSheet`、Note 文本格式化（中文字体 + 字高）等。沉淀成 `sw_api_drawing_rules.md`。
- **新增"视图质检"模块** `drw_quality_check.py`：在每张生成的工程图上做 12 项渲染级质检，**任一不通过就回退到生成阶段**，调整参数后重绘，最多迭代 3 轮。
- **重写生成脚本到 v5** `drw_generate_v5.py`：按真规范布局（A4 横向各视图占用框 + 间距）、设置字体/字高、插入图层（粗实线/细实线/虚线/点划线/中心线）、按"是否有内部腔体"自动决定是否生成剖视图、Note 用中文 GB 字体。
- **重写质检-回退闭环** `drw_qc_loop.py`：调 v5 生成 → 调 quality_check → 不合格收集失败原因 → 反馈给 v5 改参 → 重新生成 → 直到通过或达到 3 轮上限。
- **不修改任何 SLDPRT/SLDASM/SLDDRW 工程文件**；所有产物落 `drw_output/v5/` 与本目录。

## Impact
- 影响范围：`.trae/specs/enforce-drawing-quality/` 新增规范/工具/报告
- 影响代码：在 `repair-section-and-recompare/` 旁新增脚本（不覆盖 v4）
- 影响外部：仅读取现有 SLDPRT/SLDDRW 与生成新 SLDDRW

## ADDED Requirements

### Requirement: GB 制图规范学习与沉淀
系统 SHALL 输出 `gb_drawing_rules.md`，覆盖 GB/T 17452 视图布局、GB/T 4458 尺寸标注、GB/T 14691 字体、GB/T 131 表面粗糙度、GB/T 1182 形位公差、GB/T 1804 通用公差，每条规则给出对应的 SolidWorks API 设置项（如字高对应 `SetUserPreferenceDoubleValue(89, 0.005)`）。

#### Scenario: 新人查询某条 GB 规则
- **WHEN** 用户读 `gb_drawing_rules.md`
- **THEN** 能立刻找到该规则对应的 SolidWorks 调用与正确参数

### Requirement: SolidWorks 高保真制图 API 沉淀
系统 SHALL 输出 `sw_api_drawing_rules.md`：列出视图布局/字体/图层/线型/标注的 SolidWorks API 调用清单及推荐参数。

#### Scenario: 用户查询"如何创建中心线图层"
- **WHEN** 用户读 `sw_api_drawing_rules.md`
- **THEN** 找到 `LayerMgr.AddLayer(name, desc, color, lineStyle, weight)` 与示例参数

### Requirement: 12 项渲染级质检
系统 SHALL 实现 `drw_quality_check.py`，对每张 SLDDRW 在打开后做 12 项检查：
1. 视图无两两 outline 矩形相交（视图重叠 → fail）
2. 所有视图都在图框 (10mm, 10mm)~(287mm, 200mm) 之内
3. 主视图（前视）在主流位置 (左下/中间)
4. 比例属于候选集 {5:1, 3:1, 2:1, 1:1, 1:2, 1:3, 1:4, 1:5}
5. 字高 ≥ 0.0035 m (3.5 mm)
6. 13 项标题栏键齐全
7. DisplayDim 数 ≥ 0.5 × 对标平均
8. CenterMark 数 ≥ 0.5 × 对标平均
9. 含技术要求 Note 文本（NoteBlock > 4）
10. 含 Ra Note
11. 含基准 A
12. 视图引用零件路径正确（GetReferencedDocument）

不通过项写到 `<base>_qc.json` 的 `issues[]` 与 `pass=False`。

#### Scenario: 输出图纸视图重叠
- **WHEN** 跑 quality_check 发现视图重叠
- **THEN** `pass=False`，`issues=[{code:"view_overlap","views":["前视图","上视图"],"hint":"调整视图 y 间距"}]`

### Requirement: 质检-回退-重绘闭环
系统 SHALL 实现 `drw_qc_loop.py`：调 v5 生成 → 调 quality_check → 不合格则收集 issues 并回传 v5 改参（如视图位置 / 字高 / 比例）→ 重生成 → 最多迭代 3 轮，最终输出 `qc_log.md`。

#### Scenario: 三轮迭代后仍不通过
- **WHEN** 3 轮后仍有 issues
- **THEN** `qc_log.md` 列明每轮失败原因 + 最终状态（warn/fail），但保留最新一版 SLDDRW 供人工复核

## MODIFIED Requirements

### Requirement: 生成脚本（drw_generate_v5.py 取代 v4）
v4 仅按 9 元素硬编码坐标布视图，不会避免重叠；v5 SHALL 实现：
- 视图布局算法：根据零件 bbox 自动计算每个视图的 outline 大小，按 A4 297×210 - 标题栏 60mm 高 - 边距 10mm 4 边布局，避免重叠
- 字体：调 `SetUserPreferenceDoubleValue(89, 0.005)` 字高 5 mm（GB/T 14691 推荐）
- 图层：用 `LayerMgr.AddLayer` 创建"粗实线/细实线/中心线/虚线/点划线"5 层
- 显示模式：每个视图调 `view.Type = swDisplayHiddenLinesRemoved`
- 自动尺寸后用 `view.AutoCenterMarks` + `RunCommand(826)` 双保险
- 失败重试：根据 quality_check 反馈调参（视图缩比 / 字高 / 比例）

## REMOVED Requirements
（无）
