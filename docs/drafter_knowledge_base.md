# v4.0 制图师知识库

当前项目状态仍为 `WARNING / NOT RELEASE READY`。本文件定义制图师知识内核的最低规则，目的是让软件先生成可解释的 `DrawingBlueprint`，再按蓝图生成、验证和复核工程图。能够导出 PNG 不等于图纸合格。

## 加工图用途

加工图用于指导制造、检验、装配和采购沟通。制造类图纸必须能表达零件形状、关键尺寸、孔槽位置、表面粗糙度、必要公差、技术要求和标题栏信息。采购件、弹簧、紧固件和标准件可以是采购/装配说明图，但不能被伪装成完整制造图。

## 制图师知识结构

制图知识由以下层组成：

- `part_class`: 区分 machined_part、sheet_metal、long_thin、tiny_part、fastener、spring、purchased_part、assembly。
- `reference_profile`: 同名参考图的视图族、视图位置、DisplayDim 基线、备注、标题栏和符号。
- `drawing_blueprint`: 将参考图和零件理解合并成可执行计划。
- `dimension_plan`: 定义真实 SolidWorks DisplayDim 的数量、类型、优先级和失败策略。
- `notes_plan`: 定义技术要求、粗糙度、去毛刺、采购/标准件说明。
- `validation_plan`: 定义结构化验证、视觉截图复核和 failure_bucket。

## 视图选择规则

有同名参考图时，优先采用参考图的 view_count、view_types 和 view_positions。投影视图必须通过 SolidWorks projection API 从父视图创建，不能用 named view 冒充 projected view。参考图含 `7x2/4x2` 时，生成图必须保留相同视图族；参考图只有两视图时，不得自动添加多余剖视/详图。

无参考图时，按 part_class 选择默认视图：

- machined_part: front/top/right/iso，必要时剖视。
- sheet_metal: front/flat_pattern，必要时折弯相关视图。
- long_thin: 长向主视图，必要时端面/局部剖视。
- tiny_part: 放大比例主视/俯视。
- fastener/spring/purchased_part: 采购或标准件说明优先，不强行制造图视图族。

## 尺寸标注规则

制造图必须使用真实 DisplayDim。Note、OCR 文本、sidecar 计数不能替代 DisplayDim。参考图给出 DisplayDim 基线时，生成图不能低于基线；例如 006 参考基线为 12，022 参考基线为 25。

尺寸优先级：

1. 外形总长、总宽、总高或总厚。
2. 孔径、孔位、孔距、沉孔/螺纹。
3. 槽宽、槽长、槽位。
4. 圆角、倒角、角度。
5. 检验关键尺寸和装配关键尺寸。

尺寸不能堆叠遮挡主视图，不能跨越标题栏或备注区，不能用过密 AutoDimension 代替参考图的标注风格。无法生成真实 DisplayDim 时，必须进入 `need_review`，不得 silent fallback。

## 公差和形位公差规则

默认未注线性尺寸公差可按 GB/T 1804-m 类规则表达。关键孔位、配合面、装配基准和检验尺寸应优先保留参考图中出现的 Datum、位置度、平行度、垂直度等形位公差信息。若参考图包含基准符号，生成图必须在 `AnnotationPlan` 中记录并在验证中检查。

## 粗糙度规则

加工件默认需要未注粗糙度说明，常见形式为未注粗糙度 Ra3.2 或按参考图原文。参考图已有粗糙度符号或备注时，生成图必须复制其语义和放置区域。采购件、标准件可改为按供应商规格执行，但必须明确说明。

## 标题栏规则

标题栏至少需要图号、名称、材料、比例、日期、数量、设计/审核信息中的核心字段。字段来源优先级：

1. UI 输入。
2. SLDPRT/SLDASM 自定义属性。
3. 同名参考图标题栏。
4. 文件名解析。
5. 默认值并产生 warning。

缺字段不能静默通过，应进入标题栏差距报告。

## 备注栏规则

备注栏必须按 part_class 区分：

- machined_part: 技术要求、未注倒角、未注粗糙度、去毛刺、表面不得划伤。
- sheet_metal: 展开尺寸、折弯半径、去毛刺、表面处理。
- long_thin: 总长关键、装配关键尺寸、未注粗糙度、去毛刺。
- tiny_part: 放大比例说明、检验关键尺寸。
- fastener: 标准件，按标准或采购规格执行。
- spring: 线径、外径、自由长、圈数、旋向或供应商规格。
- purchased_part: 外购件，按供应商图纸或规格书执行。
- assembly: 装配关系、关键装配尺寸、BOM/数量说明。

参考图中的红色警示、特殊加工说明、热处理、表面处理和检验要求必须进入 `NotesPlan`，不能被通用模板覆盖。

## 零件类型差异

machined_part、sheet_metal 和 long_thin 通常要求 A/B 级制造图。fastener、spring、purchased_part 可以是 C 级采购/装配图，但必须说明规格和执行依据。assembly 图纸强调装配关键尺寸和 BOM，不要求把每个零件的制造尺寸全部展开。

## 制图师工作流程

1. 识别 part_class 和制造意图。
2. 查找同名参考图并生成 reference_profile。
3. 生成 DrawingBlueprint。
4. 按 ViewPlan 创建视图，投影视图使用投影 API。
5. 按 DimensionPlan 插入真实 DisplayDim。
6. 按 NotesPlan 和 TitlebarPlan 填写备注与标题栏。
7. 保存、重开并验证真实视图和 DisplayDim。
8. 运行 dimension_validation、reference_compare、vision_qc。
9. 通过应用 UI 截图逐张人工/自动复核。
10. 失败时输出 failure_bucket、bbox、evidence 和 fix_suggestion。

## 软件模块映射

- `app/services/drawing_blueprint_model.py`: v4 蓝图数据结构和 JSON schema。
- `app/services/reference_style_profile_service.py`: 参考图视图/布局/DisplayDim profile。
- `app/services/reference_dimension_profile_service.py`: 参考尺寸基线和分类。
- `app/services/reference_notes_profile_service.py`: 备注与技术要求提取。
- `app/services/reference_titlebar_profile_service.py`: 标题栏字段提取。
- `app/services/notes_blueprint_builder.py`: part_class 备注蓝图。
- `app/services/dimension_planner.py`: 真实 DisplayDim 计划。
- `app/services/drawing_layout_composer.py`: 视图、备注、尺寸安全区布局计划。
- `app/services/drawing_blueprint_builder.py`: 生成 `drawing_blueprint.json`。
- `drw_generate_v6.py`: 后续必须读取并执行 `drawing_blueprint.json`。
- `tools/ui_robot/drawing_visual_review_suite.py`: 应用 UI 截图复核，不接受历史 PNG fallback。
