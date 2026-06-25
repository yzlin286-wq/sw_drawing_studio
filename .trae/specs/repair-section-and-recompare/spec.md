# 修复剖视图与重对标 2D 工程图规范 Spec

## Why
当前自动生成的 2D 工程图虽然在纸张/视图/标题栏对齐 A4 + 第一角 + 13 项属性，但 (1) 始终生成不出剖视图（`CreateSectionViewAt5` 在 SolidWorks 2025 + pywin32 IDispatch 下返回 None，因为剖切线必须先在前视图所在的 sketch context 中被真正选中）；(2) 用户反馈"完全不符合对标文件的规范"，说明此前归纳的规范偏向几何骨架，没有抓住公司真实图纸（LB26001-A-04-048、LB26001-A-04-004 等）里的标题栏块布局、视图组合策略、剖视图/局部放大用法、技术要求文本块、字体和层结构等关键细节。

## What Changes
- 重新深度采样 `LB26001-A-04-048.SLDDRW` 与 `LB26001-A-04-004.SLDDRW` 等真实图纸，提取**视图组合 / 剖视图位置 / 标注块 / 字体 / 图层 / 标题栏 BlockInst 文本** 等高保真规范。
- 把"机加工件 vs 钣金件 vs 组件件" 三类典型公司图纸的**视图组合 + 剖视图策略**抽取为模板。
- **修复剖视图功能**：用 SolidWorks 宏 (VBA) + `RunMacro2` 的方式触发 `CreateSectionViewAt5`，绕开 pywin32 IDispatch 在 14 参函数 + 选中 sketch segment 上的兼容问题。
- 升级生成脚本到 v4：按"对标模板"自动选择视图组合 + 自动生成剖视图 + 还原标题栏字段填充策略。
- 升级对比脚本到 v3：按真实公司图纸的"加工件标准模板"重新打分，覆盖剖视图、技术要求位置、字体、图层、Note 块文本一致度等。
- **不修改任何 SLDPRT/SLDASM/SLDDRW 工程文件**；所有产物落到 `drw_output/` 与 `.trae/specs/repair-section-and-recompare/`。

## Impact
- 影响范围：在 `.trae/specs/repair-section-and-recompare/` 下生成研究/规范/工具脚本/报告。
- 影响代码：在原 `study-solidworks-skill/` 旁新增脚本（不覆盖 v3）；只读你目录下的 SLDDRW 做对标。
- 不调用 SolidWorks 之前必须先 `sw_preflight` 检查；运行时 SolidWorks 必须打开。

## ADDED Requirements

### Requirement: 真实公司图纸深度采样
系统 SHALL 对 `LB26001-A-04-048.SLDDRW`、`LB26001-A-04-004.SLDDRW` 等 5~8 张真实公司图纸做"显微镜级"采样：标题栏 BlockInst 的文本/位置、视图列表（含剖视图 SectionView/局部放大 DetailView）、所有 Note/Dimension/SurfaceFinish/DatumTag/GTOL 的文本与坐标、图层与字体、剖切线坐标。

#### Scenario: 用户拿到的样本足以驱动模板生成
- **WHEN** 用户打开新生成的 `drawing_standard_v2.md`
- **THEN** 能找到"加工件 / 钣金件 / 组件件" 各自的**视图组合表 + 剖视图策略 + 技术要求文本模板**

### Requirement: 剖视图功能修复
系统 SHALL 通过 SolidWorks VBA 宏 + `ISldWorks.RunMacro2` 的方式实现可重复的"在前视图水平中线生成剖视图 A-A"，并把剖视图 `Type=4` 写入工程图。

#### Scenario: 单零件出图含剖视图
- **WHEN** 跑 `drw_generate_v4.py` 处理某个有内部腔体的零件
- **THEN** 生成的 SLDDRW 中有 1 个 type=4 的剖视图，包含 `AreaHatch` 剖面线，并被对比脚本识别

### Requirement: 升级对比评分覆盖真实规范
系统 SHALL 在 `drw_compare_v3.py` 中加入"剖视图存在 / 标题栏 Block 文本一致度 / 视图组合策略匹配度"三个新维度。

#### Scenario: 高保真对比
- **WHEN** 用户跑对比脚本
- **THEN** 报告里能看到"剖视图 ✅ / 标题栏字段填写一致度 N/13 / 视图组合策略 = 加工件 4 视图模式"等明确指标

## MODIFIED Requirements

### Requirement: 2D 工程图对标规范文档
原 `drawing_standard.md` 是"统计平均值"。新版 `drawing_standard_v2.md` SHALL 按"加工件 / 钣金件 / 组件件" 分组，给出每类的**模板视图列表 + 剖视图位置策略 + 标题栏字段填充建议 + 字体高度 + 注释文本模板**。

## REMOVED Requirements
（无）
