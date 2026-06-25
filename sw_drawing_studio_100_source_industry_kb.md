# sw_drawing_studio 行业知识库：100+ 高质量低重复来源索引与 AI 检索版知识结构
> 目标：让 AI 在开发 SolidWorks 3D→2D 自动出图、加工图生成、视觉质检、UI 工作台时，先理解制造业工程图行业逻辑，再写代码。
> 适用位置：`AGENTS.md`、`docs/industry_knowledge_base.md`、`.codex/skills/sw-drafter-industry/SKILL.md`、RAG 知识库。

---
## 1. 核心行业结论

- **加工图不是图片**：文件齐全、PNG 清晰、视图数量正确，都不能直接说明图纸可加工。
- **图纸是制造合同**：加工厂、质检员、采购、装配、工艺、文控都从图纸获取约束。
- **自动出图必须先有制图意图**：先判断零件类型、用途、工艺、基准与关键特征，再选择视图、尺寸、备注与标题栏。
- **参考图纸是最高优先级样本**：对标同名 SLDDRW/PDF 中的视图布局、DisplayDim 基线、标题栏、备注栏、符号和图面风格。
- **必须分级交付**：制造图 A/B 级、装配图 B/C 级、采购/标准件图 C 级，不允许把采购说明伪装成制造尺寸。
- **AI 不应单独判图纸合格**：几何 QC、CAD API、视觉 OCR/OBB、参考图对比和人工复核必须形成证据链。

---
## 2. 行业知识地图（AI 检索标签）

```yaml
knowledge_domains:
  standards_and_rules:
    - ISO/ASME/GB drawing standards
    - title blocks
    - projection methods
    - dimensioning
    - GD&T
    - surface texture
  manufacturing_process:
    - CNC milling/turning
    - sheet metal
    - weldment
    - purchased parts
    - fasteners/springs
  drawing_intent:
    - part classification
    - view planning
    - datum planning
    - dimension planning
    - notes planning
  solidworks_automation:
    - OpenDoc6
    - Add-in
    - Document Manager
    - DisplayDim
    - GetOutline
    - MBD/PMI
  visual_quality:
    - PDF 300 DPI render
    - OCR
    - layout analysis
    - OBB detection
    - title block extraction
    - notes extraction
  software_productization:
    - QProcess worker isolation
    - UI robot
    - diagnostics
    - release gates
```

---
## 3. AI 开发时必须执行的行业流程

### 3.1 制图师的工作流 → 软件模块

| 制图师步骤 | 真实目的 | 软件模块 | 不合格表现 |
|---|---|---|---|
| 判断图纸用途 | 加工/装配/采购/报价/检验不同 | `drawing_type_classifier` | 所有零件都按制造图硬判 |
| 理解零件 | 找功能面、基准、孔槽、装配面 | `part_understanding` | 只看 bbox 或文件名 |
| 选择视图 | 最少视图表达最多信息 | `view_plan_builder` | 固定 4 视图或 named view 冒充投影 |
| 规划尺寸 | 标制造/检测/装配关键尺寸 | `dimension_planner` | 只追求 dim_total，缺关键孔位 |
| 规划公差/粗糙度 | 控制功能和成本 | `tolerance_surface_plan` | 全部默认 Ra 或全部缺失 |
| 标题栏与备注 | 文控、采购、制造条件 | `titlebar_resolver` / `notes_blueprint` | 标题栏空、技术要求缺失 |
| 排版 | 可读、可审、可加工 | `layout_composer` | 视图/尺寸/标题栏重叠 |
| 审核 | 防漏标、错标、歧义 | `dimension_validation` + `vision_qc` + `reference_compare` | JSON pass 但截图像乱标 |

### 3.2 必须实现 vs 可以后置

| 等级 | 必须实现 | 可后置 | 原因 |
|---|---|---|---|
| P0 | SolidWorks 独占锁、OpenDoc6 有界调用、UI 不阻塞 | 多项目并行 CAD | 没有稳定会话，真实验证不可信 |
| P0 | 参考图纸配对、DrawingBlueprint、ReferenceCompare | 129 full 直接跑 | 先把 006/样张做对，再放量 |
| P0 | DisplayDim/Note/标准件说明严格分开 | Note 充当尺寸 | 防止采购图伪装制造图 |
| P1 | 标题栏/备注栏学习与生成 | 完整自动 GD&T | 标题栏/备注是中国制造企业高频要求 |
| P1 | Vision issue 必含 bbox/source/confidence/evidence/fix | 整图 LLM 判定 | 可追溯、可人工复核 |
| P2 | MBD/PMI/STEP242 | 首版全部 MBD | 长期方向，不应阻塞 2D 交付 |

---
## 4. 100+ 来源索引（高质量、低重复）

> 字段说明：`用途` 是对 sw_drawing_studio 最应该提取的知识，不代表原文唯一内容。标准类资料多为摘要或需购买全文，开发时以企业授权标准为准。

| ID | 来源 | 类别 | 标签 | 用途 | URL |
|---|---|---|---|---|---|
| S001 | ISO 128-1: Technical product documentation—General principles of representation | 标准/制图表达 | technical drawing; representation; view clarity | 技术图样通用表达、视图/线型/表达规则；作为图纸是否清晰的上位规则。 | https://www.iso.org/standard/65296.html |
| S002 | ISO 129-1: Presentation of dimensions and tolerances | 标准/尺寸表达 | dimensioning; tolerances; 2D drawings | 尺寸与公差表达总原则；用于定义 DimensionValidation 的基础规则。 | https://www.iso.org/obp/ui/en/ |
| S003 | ISO 7200: Data fields in title blocks and document headers | 标准/标题栏 | title block; document headers; metadata | 标题栏字段、名称、长度与交换性；用于 TitlebarResolver。 | https://www.iso.org/standard/35446.html |
| S004 | ASME Y14.5: Dimensioning and Tolerancing | 标准/GD&T | GD&T; feature control frame; datums | GD&T 设计语言；用于形位公差、基准、检测语义。 | https://www.asme.org/codes-standards/find-codes-standards/y14-5-dimensioning-tolerancing |
| S005 | ISO 1101: Geometrical tolerancing—form, orientation, location and run-out | 标准/GPS/GD&T | geometrical tolerancing; GPS; datum | 几何公差的基础规则；用于 Datum/GD&T 检测。 | https://www.iso.org/obp/ui/ |
| S006 | ISO 1302: Indication of surface texture in technical product documentation | 标准/粗糙度 | surface texture; roughness; Ra | 表面结构/粗糙度符号与文字表达；用于 Ra 检查和备注栏。 | https://www.iso.org/standard/28089.html |
| S007 | ISO 5456-2: Orthographic representations | 标准/投影法 | orthographic projection; first angle; third angle | 正投影法、第一/第三角法；用于真实投影视图校验。 | https://www.iso.org/obp/ui/es/ |
| S008 | ISO 2768: General tolerances | 标准/一般公差 | general tolerances; ISO 2768 | 未注尺寸公差；用于备注栏/技术要求模板。 | https://www.iso.org/standard/85741.html |
| S009 | ASME Y14.100: Engineering Drawing Practices | 标准/图纸实践 | drawing practices; revision; associated lists | 工程图准备与修订实践；用于文控与发布门槛。 | https://www.asme.org/codes-standards/find-codes-standards/y14-100-engineering-drawing-practices |
| S010 | ASME Y14.24: Types and Applications of Engineering Drawings | 标准/图纸类型 | drawing types; application | 定义加工图、装配图、详图、列表等；用于 drawing_type 分类。 | https://www.asme.org/codes-standards/find-codes-standards/y14-24-types-applications-engineering-drawings |
| S011 | ASME Y14.34: Associated Lists | 标准/BOM/清单 | parts list; associated list | 图纸关联清单实践；用于 BOM/零件清单页。 | https://www.asme.org/codes-standards/find-codes-standards/y14-34-associated-lists |
| S012 | ASME Y14.35: Revision of Engineering Drawings and Associated Documents | 标准/修订 | revision; change control | 修订、变更和版控；用于 release log/文控模块。 | https://www.asme.org/codes-standards/find-codes-standards/y14-35-revision-engineering-drawings-associated-documents |
| S013 | ASME Y14.41: Digital Product Definition Data Practices | 标准/MBD/数字定义 | model-based definition; digital product definition | 模型定义数据实践；用于 MBD/PMI 路线。 | https://www.asme.org/codes-standards/find-codes-standards/y14-41-digital-product-definition-data-practices |
| S014 | ASME Y14.36: Surface Texture Symbols | 标准/表面纹理 | surface texture; symbols | ASME 体系下表面纹理符号；用于美标客户图纸。 | https://www.asme.org/codes-standards/find-codes-standards/y14-36-surface-texture-symbols |
| S015 | ISO 16792: Digital product definition data practices | 标准/MBD | digital product definition; MBD | 3D 数字产品定义实践；作为未来 MBD 交付补充。 | https://www.iso.org/standard/76126.html |
| S016 | ISO 14405 series: Dimensional tolerancing | 标准/GPS/尺寸公差 | dimensional tolerancing; GPS | 尺寸公差表达更细规则；用于后续公差引擎。 | https://www.iso.org/search.html?q=ISO%2014405 |
| S017 | ISO 14638: GPS matrix model | 标准/GPS体系 | GPS matrix; geometrical product specification | GPS 体系结构；用于知识库标准层级。 | https://www.iso.org/standard/57090.html |
| S018 | GB/T 14689-2008: 技术制图 图纸幅面和格式 | 中国标准/图幅 | GB/T; sheet size; layout | 中国图幅/图框标准；用于中文制造企业图纸模板。 | https://www.codeofchina.com/standard/GBT14689-2008.html |
| S019 | GB/T 4458.4-2003: 机械制图 尺寸注法 | 中国标准/尺寸注法 | GB/T; dimensioning; mechanical drawings | 中国机械制图尺寸注法；用于中文图纸尺寸规则。 | https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=08588A5F3FE19F16B9EE8D5D87E064D5 |
| S020 | GB/T 1182-2018: 几何公差 形状、方向、位置和跳动 | 中国标准/几何公差 | GB/T; geometrical tolerancing | 中国 GPS/几何公差标注；用于 Datum/GD&T 中文图纸。 | https://www.codeofchina.com/standard/GBT1182-2018.html |
| S021 | GB/T 131-2006: 技术产品文件中表面结构的表示法 | 中国标准/粗糙度 | GB/T; surface texture; Ra | 中国粗糙度标注；用于备注栏/符号检测。 | https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=E83E2264601B94071763C2D0537B927A |
| S022 | NASA GSFC Engineering Drawing Standards Manual | 公开手册/工程图实践 | drawing standards manual; notes; title block | 工程图标准手册；大量实务规则可转为 DrawingBlueprint。 | https://s3vi.ndc.nasa.gov/ssri-kb/static/resources/NASA%20GSFC-X-673-64-1F.pdf |
| S023 | NASA KSC Engineering Drawing Practices GP-435 | 公开手册/数字产品定义 | drawing practices; model-only; drawing-only | 数字模型/图纸实践和标题/备注规则。 | https://standards.nasa.gov/sites/default/files/standards/KSC/H/1/GP-435-Vol-I-Chg-H-1.pdf |
| S024 | MIL-STD-100G Engineering Drawing Practices | 历史/军标/图纸实践 | engineering drawing practices; DoD | 历史图纸实践标准，强调图纸与清单完整性。 | https://everyspec.com/MIL-STD/MIL-STD-0100-0299/MIL-STD-100G_10910/ |
| S025 | McGill Engineering Design: Drawing Format and Elements | 教学/图纸元素 | sheet; title block; drawing elements | 图幅、标题栏、格式元素入门；用于 UI/验收口径教育。 | https://www.mcgill.ca/engineeringdesign/step-step-design-process/basics-graphics-communication/drawing-format-and-elements |
| S026 | Engineering Working Drawing Basics | 公开教材/工程图基础 | working drawing; title block; projection | 工作图基础；帮助 AI 理解图纸构成。 | https://s3vi.ndc.nasa.gov/ssri-kb/static/resources/Engineering%2BWorking%2BDrawing%2BBasics.pdf |
| S027 | Hubs: How to prepare a technical drawing for CNC machining | 实操/CNC图纸 | CNC; technical drawing; sourcing | 什么时候必须提供技术图纸、图纸应包含什么。 | https://www.hubs.com/knowledge-base/how-prepare-technical-drawing-cnc-machining/ |
| S028 | Hubs: CNC machining design guide | 实操/CNC设计 | CNC design; manufacturability | CNC 加工能力、限制和 DFM；用于 PartUnderstanding。 | https://www.hubs.com/guides/cnc-machining/ |
| S029 | Hubs: CNC machining ISO-based tolerances and finishes | 实操/公差/表面 | ISO 2768; finish; tolerances | CNC 默认公差和表面处理；用于默认备注栏。 | https://www.hubs.com/knowledge-base/cnc-machining-iso-based-tolerances-and-finishes/ |
| S030 | Hubs: How to design parts for CNC machining | 实操/CNC设计规则 | threads; tolerances; surface finish | CAD 与图纸在交付中扮演不同角色；图纸作为螺纹/公差/表面要求依据。 | https://www.hubs.com/knowledge-base/how-design-parts-cnc-machining/ |
| S031 | Protolabs: CNC milling tolerances and design guide | 实操/快速制造 | CNC milling; standard tolerances | 默认加工公差和薄壁建议；用于合理默认阈值。 | https://www.protolabs.com/services/cnc-machining/cnc-milling/ |
| S032 | Protolabs: Fine-tuning tolerances for CNC parts | 实操/公差成本 | tolerances; GD&T; cost | 不要过度标严公差；用于 AI 生成建议。 | https://www.protolabs.com/resources/design-tips/fine-tuning-tolerances-for-cnc-machined-parts/ |
| S033 | Xometry: Manufacturing standards | 实操/制造标准 | manufacturing standards; tolerances | 供应商平台制造标准；用于默认交付要求。 | https://www.xometry.com/manufacturing-standards/ |
| S034 | Xometry Pro: CNC machining design guide PDF | 实操/CNC工艺 | CNC; tolerance; surface finish | CNC 加工公差和表面要求示例。 | https://xometry.pro/wp-content/uploads/2023/07/UK-CNC-Machining-Design-Guide.pdf |
| S035 | Xometry: Advanced tips for CNC designs and drawings | 实操/图纸沟通 | CNC drawings; design intent | 如何用图纸沟通设计意图和成本影响。 | https://www.xometry.com/resources/blog/advanced-tips-for-cnc-designs-and-drawings-webinar/ |
| S036 | Xometry Pro: CNC machining surface roughness | 实操/粗糙度 | surface roughness; Ra conversion | Ra 等级和应用；用于表面要求知识。 | https://xometry.pro/en/articles/cnc-machining-surface-roughness/ |
| S037 | Fictiv: Creating comprehensive engineering drawings for CNC machining | 实操/CNC图纸 | CNC drawing; tolerancing; notes | 综合工程图的结构、容差和备注建议。 | https://www.fictiv.com/articles/how-to-make-a-cnc-drawing |
| S038 | Fictiv: Tight tolerance parts guide | 实操/紧公差 | tight tolerance; design intent | 紧公差设计和图纸沟通。 | https://www.fictiv.com/ebooks/the-complete-guide-to-designing-tight-tolerance-parts |
| S039 | Fictiv: How design requirements drive manufacturability | 实操/DFM | DFM; tolerance effort | 关键尺寸紧公差，非关键尺寸放宽；用于 AI 不过度标注。 | https://www.fictiv.com/masterclass/dfm-for-cnc-masterclass/how-design-requirements-drive-cnc-manufacturability |
| S040 | Fictiv: Common tolerance mistakes | 实操/质量风险 | tolerance mistakes; manufacturing cost | 公差错误和成本风险；用于图纸自动审查规则。 | https://www.fictiv.com/articles/common-tolerance-mistakes-and-how-to-fix |
| S041 | MakerVerse: Understanding technical drawings | 实操/技术图纸 | technical drawings; manufacturing requirements | 技术图纸构成及制造要求。 | https://www.makerverse.com/resources/cnc-machining-guides/understanding-technical-drawings-a-complete-guide/ |
| S042 | HPPI: Engineering drawings for CNC machining | 实操/CNC工程图 | engineering drawings; tolerances; best practices | 图纸构成、尺寸和公差实务。 | https://hppi.com/knowledge-base/cnc-machining-design/drawings |
| S043 | JLCCNC: How to read engineering drawings | 实操/读图 | reading drawings; symbols; notes | 读图顺序：标题栏、标准、单位、视图、尺寸、公差。 | https://jlccnc.com/blog/how-to-read-engineering-drawings |
| S044 | JLCCNC: ISO 2768 tolerance standards for CNC machining | 实操/公差 | ISO 2768; CNC | ISO 2768 机加工公差理解。 | https://jlccnc.com/help/article/iso-2768-tolerance-standards-for-cnc-machining |
| S045 | MiSUMi: Surface texture technical data | 实操/粗糙度 | surface texture; symbols | 表面结构符号实务解释。 | https://sg.misumi-ec.com/tech-info/categories/technical_data/td01/a0090.html |
| S046 | Quality-One: APQP overview | 质量/APQP | APQP; drawing control; engineering change | APQP 中图纸、规格、变更控制的角色。 | https://quality-one.com/apqp/ |
| S047 | AIAG Quality Core Tools | 质量/汽车工业 | APQP; PPAP; FMEA; MSA; SPC | 汽车供应链核心质量工具。 | https://www.aiag.org/expertise-areas/quality/quality-core-tools |
| S048 | ISO: ISO 9001 explained | 质量/QMS | quality management; documented information | 质量体系与文控；图纸是受控文件。 | https://www.iso.org/home/insights-news/resources/iso-9001-explained.html |
| S049 | Verisurf: First Article Inspection guide | 质量/FAI | FAI; inspection plan | 首件检验需要按图纸特性逐项验证。 | https://www.verisurf.com/blog/article/first-article-inspection/ |
| S050 | Lockheed Martin: Supplier FAI/AS9102 guidance | 质量/供应商检验 | AS9102; supplier quality; FAI | 供应商 FAI 对图纸特性和记录的要求。 | https://www.lockheedmartin.com/content/dam/lockheed-martin/eo/documents/suppliers/rms/rms-quality-fai-July-2022.pdf |
| S051 | SOLIDWORKS API: OpenDoc6 Method | SolidWorks API/打开文件 | OpenDoc6; errors; warnings; silent | 所有真实 CAD job 的打开事务必须记录 errors/warnings。 | https://help.solidworks.com/2024/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ISldWorks~OpenDoc6.html |
| S052 | SOLIDWORKS API: Open Document Silently Example | SolidWorks API/静默打开 | silent open; API example | 静默打开示例；用于 SW session supervisor。 | https://help.solidworks.com/2024/English/api/sldworksapi/Open_Document_Silently_Example_VB.htm |
| S053 | SOLIDWORKS API: swOpenDocOptions_e | SolidWorks API/打开选项 | open options; silent; readonly | OpenDoc 选项枚举；用于安全加载。 | https://help.solidworks.com/2023/english/api/swconst/SOLIDWORKS.Interop.swconst~SOLIDWORKS.Interop.swconst.swOpenDocOptions_e.html |
| S054 | SOLIDWORKS API: IView.GetOutline | SolidWorks API/视图边界 | view outline; layout | 绘图页上视图 bounding box；用于 LayoutSolver。 | https://help.solidworks.com/2018/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IView~GetOutline.html |
| S055 | SOLIDWORKS API: IView.GetDisplayDimensions | SolidWorks API/尺寸读取 | display dimensions; drawing view | 读取视图所有 DisplayDimensions；用于真实尺寸统计。 | https://help.solidworks.com/2022/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IView~GetDisplayDimensions.html |
| S056 | SOLIDWORKS API: IView.GetDisplayDimensionCount | SolidWorks API/尺寸计数 | display dimension count | 快速统计 DisplayDim；用于 QC。 | https://help.solidworks.com/2023/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IView~GetDisplayDimensionCount.html |
| S057 | SOLIDWORKS API: IView.GetDimensionDisplayString5 | SolidWorks API/尺寸文本 | dimension display string | 尺寸显示字符串；用于 OCR/CAD 双重校验。 | https://help.solidworks.com/2024/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IView~GetDimensionDisplayString5.html |
| S058 | SOLIDWORKS API: IView Interface | SolidWorks API/视图对象 | drawing view; model reference | 视图对象能力边界；用于视图族理解。 | https://help.solidworks.com/2023/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IView.html |
| S059 | SOLIDWORKS API: Autodimension Selected Drawing View Example | SolidWorks API/自动尺寸 | AutoDimension; selected view | 自动尺寸示例；只能作为候选，不能替代制图师意图。 | https://help.solidworks.com/2025/english/api/sldworksapi/Autodimension_Selected_Drawing_View_Example_VB.htm |
| S060 | SOLIDWORKS API: InsertModelAnnotations3 | SolidWorks API/导入模型注解 | model annotations; dimensions; PMI | 导入模型尺寸/注解；无 PMI 时可能返回 0。 | https://help.solidworks.com/2025/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IDrawingDoc~InsertModelAnnotations3.html |
| S061 | SOLIDWORKS API: IView.GetVisibleEntities2 | SolidWorks API/可见实体 | visible entities; drawing view edges | 从视图提取边/曲线，用于自动生成外形尺寸。 | https://help.solidworks.com/2023/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.iview~getvisibleentities2.html |
| S062 | SOLIDWORKS Document Manager: GetAllExternalReferences5 | SolidWorks API/引用管理 | external references; broken references | 磁盘级读取 drawing 外部引用，用于 refdoc 修复。 | https://help.solidworks.com/2021/english/api/swdocmgrapi/SolidWorks.Interop.swdocumentmgr~SolidWorks.Interop.swdocumentmgr.ISwDMDocument21~GetAllExternalReferences5.html |
| S063 | CodeStack: Replace references using Document Manager | SolidWorks 实操/引用替换 | Document Manager; ReplaceReference | Document Manager 替换 drawing/assembly 引用示例。 | https://www.codestack.net/solidworks-document-manager-api/document/replace-references/ |
| S064 | SOLIDWORKS MBD product page | SolidWorks MBD/PMI | MBD; PMI; 3D PDF; STEP 242 | 3D PMI、尺寸、公差、BOM 和发布模板；长期方向。 | https://www.solidworks.com/product/solidworks-mbd |
| S065 | SOLIDWORKS STEP 242 sharing | SolidWorks MBD/STEP242 | STEP 242; MBD | MBD 输出 STEP 242，供下游制造/检测。 | https://help.solidworks.com/2026/english/solidworks/sldworks/t_share_models_step242.htm |
| S066 | DriveWorks: Auto Dimension Drawing View | SOLIDWORKS自动化/尺寸 | auto dimension drawing view | 成熟自动化产品的自动标注任务参考。 | https://docs.driveworkspro.com/topic/GTAutoDimensionDrawingView |
| S067 | DriveWorks: Auto Arrange Dimensions | SOLIDWORKS自动化/排版 | auto arrange dimensions | 自动整理尺寸位置；对标 DimensionArrange。 | https://docs.driveworkspro.com/topic/GTAutoArrangeDimensions |
| S068 | DriveWorks: DimensionText helper | SOLIDWORKS自动化/尺寸文本 | dimension text; annotation | 尺寸文字左右/上下附加文本规则。 | https://docs.driveworkspro.com/topic/DrawingRulesAnnotationDimensionText |
| S069 | SOLIDWORKS Partner Product: Drew | SOLIDWORKS自动化/插件 | drawing automation; views; dimensions | Drew 的一键视图/尺寸/表格生成是行业对标。 | https://www.solidworks.com/partner-product/drew |
| S070 | CAD Booster Drew product page | SOLIDWORKS自动化/插件 | drawing automation; sheet per body; dimensions | 偏好/模板/视图/外形尺寸/钣金/weldment 自动化。 | https://cadbooster.com/solidworks-add-in/drew/ |
| S071 | CAD Booster Drew improvements | SOLIDWORKS自动化/外形尺寸 | outer dimensions; sheet metal; weldment | 外形尺寸、平板展开、曲线尺寸优化思路。 | https://cadbooster.com/50-drew-improvements-better-automatic-dimensions-progress-bar/ |
| S072 | CodeStack: Dimension visible drawing entities from view | SOLIDWORKS API 实操/尺寸 | visible drawing entities; dimension longest edge | 用可见实体加尺寸的可行路径。 | https://www.codestack.net/solidworks-api/document/drawing/view-dimension-drawing-entities/ |
| S073 | xarial xCAD GitHub | 开源/SolidWorks Add-in框架 | SOLIDWORKS add-in; .NET framework | Add-in 架构、公共 API、插件化开发参考。 | https://github.com/xarial/xcad |
| S074 | SolidDNA GitHub | 开源/SolidWorks Add-in框架 | SolidWorks API wrapper; add-in | SolidWorks Add-in 封装框架参考。 | https://github.com/CAD-Booster/SolidDNA |
| S075 | SOLIDWORKS Automatic Drawing Operations | SOLIDWORKS帮助/自动图纸 | automatic drawing operations; dimensions | SOLIDWORKS 自带自动导入尺寸/注解功能范围。 | https://help.solidworks.com/2020/english/SolidWorks/acadhelp/c_automatic_drawing_operations_acadhelp.htm |
| S076 | PyMuPDF images recipe | 视觉/PDF渲染 | PDF to PNG; 300 DPI | PDF→300 DPI PNG 的稳定输入基线。 | https://pymupdf.readthedocs.io/en/latest/recipes-images.html |
| S077 | PaddleOCR GitHub | 视觉/OCR | OCR; structure; layout; tables | 中文/英文 OCR 和结构化输出；适合标题栏/备注栏。 | https://github.com/PaddlePaddle/PaddleOCR |
| S078 | PaddleOCR PP-Structure docs | 视觉/版面分析 | layout analysis; table recognition | 文档版面与表格结构识别；用于 titleblock/notes。 | https://paddlepaddle.github.io/PaddleOCR/main/en/version2.x/ppstructure/overview.html |
| S079 | PaddleOCR 3.0 Technical Report | 视觉/OCR论文 | PP-StructureV3; document parsing | 新版 PaddleOCR 结构化文档理解思路。 | https://arxiv.org/html/2507.05595v1 |
| S080 | Ultralytics YOLO OBB task docs | 视觉/OBB检测 | oriented bounding boxes; rotated objects | 旋转框检测适合尺寸文字、箭头、粗糙度符号。 | https://docs.ultralytics.com/tasks/obb |
| S081 | Ultralytics OBB dataset guide | 视觉/数据集格式 | OBB dataset; annotation format | 训练工程图目标检测模型的数据格式。 | https://docs.ultralytics.com/datasets/obb |
| S082 | Automated Parsing of Engineering Drawings for Structured Manufacturing Knowledge | 论文/工程图解析 | YOLOv11-OBB; Donut; drawing parsing | 九类制造标注 OBB + 结构化 JSON；适合 Vision QC 架构。 | https://arxiv.org/pdf/2505.01530 |
| S083 | eDOCr: OCR on engineering drawings for production quality control | 论文/OCR | engineering drawing OCR; feature control frames; info blocks | 工程图分区 OCR：信息块/表格、特征控制框、其余区域。 | https://www.frontiersin.org/journals/manufacturing-technology/articles/10.3389/fmtec.2023.1154132/full |
| S084 | eDOCr GitHub | 开源/OCR工程图 | engineering drawing OCR; Python | 可复用工程图 OCR pipeline 实现思路。 | https://github.com/javvi51/eDOCr |
| S085 | eDOCr2: Optimizing Text Recognition in Mechanical Drawings | 论文/OCR升级 | structured extraction; mechanical drawings | 工程图结构化信息抽取升级，强调分区与图像处理。 | https://www.mdpi.com/2075-1702/13/3/254 |
| S086 | AI-powered text extraction from engineering drawings thesis | 论文/OCR综述 | OCR benchmark; engineering documents | 工程图 OCR 方法比较和数据集稀缺性。 | https://www.utupub.fi/bitstreams/85f13f4b-276a-41eb-b933-be3134af9788/download |
| S087 | Title Block Detection and Information Extraction | 论文/标题栏 | title block detection; information extraction | 标题栏检测和信息抽取任务建模。 | https://arxiv.org/pdf/2504.08645 |
| S088 | Title block detection and processing research | 论文/标题栏/AEC | title block; drawing organization | 标题栏是工程图组织与检索关键区域。 | https://www.researchgate.net/publication/368515747_An_Approach_to_Engineering_Drawing_Organization_Title_Block_Detection_and_Processing |
| S089 | NCSA: Information Extraction from Scanned Engineering Drawings | 论文/扫描图纸 | scanned drawings; OCR; metadata | 扫描工程图 OCR 精度和人工校正框架。 | https://www.academia.edu/21829351/Information_Extraction_from_Scanned_Engineering_Drawings |
| S090 | A Study of Structured/Semantic Data Extraction from Mechanical Engineering Drawings | 论文/结构化抽取 | mechanical drawings; semantic extraction | 机械图纸中非均质数据的结构化抽取。 | https://hal.science/hal-05002280v1/file/drawing_interpretation_AR1-1.pdf |
| S091 | Automatic raster engineering drawing digitisation | 论文/图纸矢量化 | raster engineering drawing digitisation | 栅格工程图数字化和几何重建。 | https://hal.science/hal-04842487v1/document |
| S092 | HuggingFace: engineering drawing title block/BOM/notes detector | 模型/工程图检测 | RT-DETR; title block; BOM; notes | 可用于 titleblock/BOM/notes 检测的模型参考。 | https://huggingface.co/hsarfraz/eng-drawing-title-block-bill-of-material-extractor |
| S093 | PubLayNet dataset | 数据集/版面分析 | document layout; PubLayNet | 通用文档版面检测基础数据集。 | https://arxiv.org/abs/1908.07836 |
| S094 | DocLayNet dataset | 数据集/版面分析 | document layout; annotations | 通用文档版面检测，有助于训练 title/figure/table 模型。 | https://arxiv.org/abs/2206.01062 |
| S095 | TableBank dataset | 数据集/表格识别 | table detection; table recognition | 备注栏/标题栏表格结构识别参考。 | https://arxiv.org/abs/1903.01949 |
| S096 | Donut: OCR-free Document Understanding Transformer | 模型/文档解析 | OCR-free document understanding | OBB crop 后结构化解析的候选模型。 | https://arxiv.org/abs/2111.15664 |
| S097 | LayoutLMv3 | 模型/文档理解 | document AI; layout; text-image | 文档理解多模态模型参考。 | https://arxiv.org/abs/2204.08387 |
| S098 | Qt QProcess Class | 软件工程/UI进程隔离 | QProcess; stdout; finished; errorOccurred | UI 不阻塞、worker JSONL 的官方依据。 | https://doc.qt.io/qt-6/qprocess.html |
| S099 | PySide6 QProcess docs | 软件工程/PySide | PySide6; QProcess; I/O | PySide 应用进程隔离。 | https://doc.qt.io/qtforpython-6/PySide6/QtCore/QProcess.html |
| S100 | pywinauto GitHub | 测试/UI 自动化 | Windows UI automation; testing | EXE 级模拟人工点击和截图验收。 | https://github.com/pywinauto/pywinauto |
| S101 | Microsoft UI Automation overview | 测试/UI 自动化 | Windows UI Automation | Windows UI 自动化官方概念。 | https://learn.microsoft.com/en-us/windows/win32/winauto/entry-uiauto-win32 |
| S102 | PyAutoGUI docs | 测试/鼠标键盘截图 | screenshot; click; keyboard | UI robot fallback，截图/点击。 | https://pyautogui.readthedocs.io/en/latest/ |
| S103 | Python GUIs: QProcess in PySide6 | 软件工程/QProcess实践 | PySide6; QProcess; progress | 非阻塞外部进程实操。 | https://www.pythonguis.com/tutorials/pyside6-qprocess-external-programs/ |
| S104 | OpenAI Codex AGENTS.md guide | AI开发流程/项目规则 | AGENTS.md; project instructions | 固化项目目标、验收门槛和禁令。 | https://developers.openai.com/codex/guides/agents-md |
| S105 | OpenAI Codex Skills guide | AI开发流程/skills | skills; reusable workflows | 把 EXE UI robot/SolidWorks 验证/视觉审计封装成 skill。 | https://developers.openai.com/codex/skills |
| S106 | OpenAI Codex Subagents guide | AI开发流程/subagents | subagents; parallel tasks | 拆分 UI、CAD、视觉、发布等子代理。 | https://developers.openai.com/codex/subagents |
| S107 | Windows COM IMessageFilter RetryRejectedCall | 软件工程/COM稳定性 | COM busy; retry rejected call | COM server 忙碌/拒绝调用时要有 message filter 和超时策略。 | https://learn.microsoft.com/en-us/windows/win32/api/objidl/nf-objidl-imessagefilter-retryrejectedcall |
| S108 | SOLIDWORKS Error Report dialog help | SolidWorks稳定性/错误报告 | SolidWorks crash; error report; Rx | slduiu/崩溃类问题应记录 Rx、事件、上下文，而非只看 Python。 | https://help.solidworks.com/2026/english/SolidWorks/Sldworks/c_SW_error_report_db.htm |

---
## 5. 面向 AI 的 RAG 检索卡片

### S001｜ISO 128-1: Technical product documentation—General principles of representation
- 类别：标准/制图表达
- 检索标签：technical drawing; representation; view clarity
- 应用于项目：技术图样通用表达、视图/线型/表达规则；作为图纸是否清晰的上位规则。
- 优先级：P0
- URL：https://www.iso.org/standard/65296.html

### S002｜ISO 129-1: Presentation of dimensions and tolerances
- 类别：标准/尺寸表达
- 检索标签：dimensioning; tolerances; 2D drawings
- 应用于项目：尺寸与公差表达总原则；用于定义 DimensionValidation 的基础规则。
- 优先级：P0
- URL：https://www.iso.org/obp/ui/en/

### S003｜ISO 7200: Data fields in title blocks and document headers
- 类别：标准/标题栏
- 检索标签：title block; document headers; metadata
- 应用于项目：标题栏字段、名称、长度与交换性；用于 TitlebarResolver。
- 优先级：P0
- URL：https://www.iso.org/standard/35446.html

### S004｜ASME Y14.5: Dimensioning and Tolerancing
- 类别：标准/GD&T
- 检索标签：GD&T; feature control frame; datums
- 应用于项目：GD&T 设计语言；用于形位公差、基准、检测语义。
- 优先级：P0
- URL：https://www.asme.org/codes-standards/find-codes-standards/y14-5-dimensioning-tolerancing

### S005｜ISO 1101: Geometrical tolerancing—form, orientation, location and run-out
- 类别：标准/GPS/GD&T
- 检索标签：geometrical tolerancing; GPS; datum
- 应用于项目：几何公差的基础规则；用于 Datum/GD&T 检测。
- 优先级：P1
- URL：https://www.iso.org/obp/ui/

### S006｜ISO 1302: Indication of surface texture in technical product documentation
- 类别：标准/粗糙度
- 检索标签：surface texture; roughness; Ra
- 应用于项目：表面结构/粗糙度符号与文字表达；用于 Ra 检查和备注栏。
- 优先级：P1
- URL：https://www.iso.org/standard/28089.html

### S007｜ISO 5456-2: Orthographic representations
- 类别：标准/投影法
- 检索标签：orthographic projection; first angle; third angle
- 应用于项目：正投影法、第一/第三角法；用于真实投影视图校验。
- 优先级：P1
- URL：https://www.iso.org/obp/ui/es/

### S008｜ISO 2768: General tolerances
- 类别：标准/一般公差
- 检索标签：general tolerances; ISO 2768
- 应用于项目：未注尺寸公差；用于备注栏/技术要求模板。
- 优先级：P1
- URL：https://www.iso.org/standard/85741.html

### S009｜ASME Y14.100: Engineering Drawing Practices
- 类别：标准/图纸实践
- 检索标签：drawing practices; revision; associated lists
- 应用于项目：工程图准备与修订实践；用于文控与发布门槛。
- 优先级：P1
- URL：https://www.asme.org/codes-standards/find-codes-standards/y14-100-engineering-drawing-practices

### S010｜ASME Y14.24: Types and Applications of Engineering Drawings
- 类别：标准/图纸类型
- 检索标签：drawing types; application
- 应用于项目：定义加工图、装配图、详图、列表等；用于 drawing_type 分类。
- 优先级：P1
- URL：https://www.asme.org/codes-standards/find-codes-standards/y14-24-types-applications-engineering-drawings

### S011｜ASME Y14.34: Associated Lists
- 类别：标准/BOM/清单
- 检索标签：parts list; associated list
- 应用于项目：图纸关联清单实践；用于 BOM/零件清单页。
- 优先级：P1
- URL：https://www.asme.org/codes-standards/find-codes-standards/y14-34-associated-lists

### S012｜ASME Y14.35: Revision of Engineering Drawings and Associated Documents
- 类别：标准/修订
- 检索标签：revision; change control
- 应用于项目：修订、变更和版控；用于 release log/文控模块。
- 优先级：P1
- URL：https://www.asme.org/codes-standards/find-codes-standards/y14-35-revision-engineering-drawings-associated-documents

### S013｜ASME Y14.41: Digital Product Definition Data Practices
- 类别：标准/MBD/数字定义
- 检索标签：model-based definition; digital product definition
- 应用于项目：模型定义数据实践；用于 MBD/PMI 路线。
- 优先级：P1
- URL：https://www.asme.org/codes-standards/find-codes-standards/y14-41-digital-product-definition-data-practices

### S014｜ASME Y14.36: Surface Texture Symbols
- 类别：标准/表面纹理
- 检索标签：surface texture; symbols
- 应用于项目：ASME 体系下表面纹理符号；用于美标客户图纸。
- 优先级：P1
- URL：https://www.asme.org/codes-standards/find-codes-standards/y14-36-surface-texture-symbols

### S015｜ISO 16792: Digital product definition data practices
- 类别：标准/MBD
- 检索标签：digital product definition; MBD
- 应用于项目：3D 数字产品定义实践；作为未来 MBD 交付补充。
- 优先级：P1
- URL：https://www.iso.org/standard/76126.html

### S016｜ISO 14405 series: Dimensional tolerancing
- 类别：标准/GPS/尺寸公差
- 检索标签：dimensional tolerancing; GPS
- 应用于项目：尺寸公差表达更细规则；用于后续公差引擎。
- 优先级：P1
- URL：https://www.iso.org/search.html?q=ISO%2014405

### S017｜ISO 14638: GPS matrix model
- 类别：标准/GPS体系
- 检索标签：GPS matrix; geometrical product specification
- 应用于项目：GPS 体系结构；用于知识库标准层级。
- 优先级：P1
- URL：https://www.iso.org/standard/57090.html

### S018｜GB/T 14689-2008: 技术制图 图纸幅面和格式
- 类别：中国标准/图幅
- 检索标签：GB/T; sheet size; layout
- 应用于项目：中国图幅/图框标准；用于中文制造企业图纸模板。
- 优先级：P0
- URL：https://www.codeofchina.com/standard/GBT14689-2008.html

### S019｜GB/T 4458.4-2003: 机械制图 尺寸注法
- 类别：中国标准/尺寸注法
- 检索标签：GB/T; dimensioning; mechanical drawings
- 应用于项目：中国机械制图尺寸注法；用于中文图纸尺寸规则。
- 优先级：P0
- URL：https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=08588A5F3FE19F16B9EE8D5D87E064D5

### S020｜GB/T 1182-2018: 几何公差 形状、方向、位置和跳动
- 类别：中国标准/几何公差
- 检索标签：GB/T; geometrical tolerancing
- 应用于项目：中国 GPS/几何公差标注；用于 Datum/GD&T 中文图纸。
- 优先级：P1
- URL：https://www.codeofchina.com/standard/GBT1182-2018.html

### S021｜GB/T 131-2006: 技术产品文件中表面结构的表示法
- 类别：中国标准/粗糙度
- 检索标签：GB/T; surface texture; Ra
- 应用于项目：中国粗糙度标注；用于备注栏/符号检测。
- 优先级：P1
- URL：https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=E83E2264601B94071763C2D0537B927A

### S022｜NASA GSFC Engineering Drawing Standards Manual
- 类别：公开手册/工程图实践
- 检索标签：drawing standards manual; notes; title block
- 应用于项目：工程图标准手册；大量实务规则可转为 DrawingBlueprint。
- 优先级：P0
- URL：https://s3vi.ndc.nasa.gov/ssri-kb/static/resources/NASA%20GSFC-X-673-64-1F.pdf

### S023｜NASA KSC Engineering Drawing Practices GP-435
- 类别：公开手册/数字产品定义
- 检索标签：drawing practices; model-only; drawing-only
- 应用于项目：数字模型/图纸实践和标题/备注规则。
- 优先级：P1
- URL：https://standards.nasa.gov/sites/default/files/standards/KSC/H/1/GP-435-Vol-I-Chg-H-1.pdf

### S024｜MIL-STD-100G Engineering Drawing Practices
- 类别：历史/军标/图纸实践
- 检索标签：engineering drawing practices; DoD
- 应用于项目：历史图纸实践标准，强调图纸与清单完整性。
- 优先级：P1
- URL：https://everyspec.com/MIL-STD/MIL-STD-0100-0299/MIL-STD-100G_10910/

### S025｜McGill Engineering Design: Drawing Format and Elements
- 类别：教学/图纸元素
- 检索标签：sheet; title block; drawing elements
- 应用于项目：图幅、标题栏、格式元素入门；用于 UI/验收口径教育。
- 优先级：P1
- URL：https://www.mcgill.ca/engineeringdesign/step-step-design-process/basics-graphics-communication/drawing-format-and-elements

### S026｜Engineering Working Drawing Basics
- 类别：公开教材/工程图基础
- 检索标签：working drawing; title block; projection
- 应用于项目：工作图基础；帮助 AI 理解图纸构成。
- 优先级：P1
- URL：https://s3vi.ndc.nasa.gov/ssri-kb/static/resources/Engineering%2BWorking%2BDrawing%2BBasics.pdf

### S027｜Hubs: How to prepare a technical drawing for CNC machining
- 类别：实操/CNC图纸
- 检索标签：CNC; technical drawing; sourcing
- 应用于项目：什么时候必须提供技术图纸、图纸应包含什么。
- 优先级：P0
- URL：https://www.hubs.com/knowledge-base/how-prepare-technical-drawing-cnc-machining/

### S028｜Hubs: CNC machining design guide
- 类别：实操/CNC设计
- 检索标签：CNC design; manufacturability
- 应用于项目：CNC 加工能力、限制和 DFM；用于 PartUnderstanding。
- 优先级：P1
- URL：https://www.hubs.com/guides/cnc-machining/

### S029｜Hubs: CNC machining ISO-based tolerances and finishes
- 类别：实操/公差/表面
- 检索标签：ISO 2768; finish; tolerances
- 应用于项目：CNC 默认公差和表面处理；用于默认备注栏。
- 优先级：P1
- URL：https://www.hubs.com/knowledge-base/cnc-machining-iso-based-tolerances-and-finishes/

### S030｜Hubs: How to design parts for CNC machining
- 类别：实操/CNC设计规则
- 检索标签：threads; tolerances; surface finish
- 应用于项目：CAD 与图纸在交付中扮演不同角色；图纸作为螺纹/公差/表面要求依据。
- 优先级：P1
- URL：https://www.hubs.com/knowledge-base/how-design-parts-cnc-machining/

### S031｜Protolabs: CNC milling tolerances and design guide
- 类别：实操/快速制造
- 检索标签：CNC milling; standard tolerances
- 应用于项目：默认加工公差和薄壁建议；用于合理默认阈值。
- 优先级：P1
- URL：https://www.protolabs.com/services/cnc-machining/cnc-milling/

### S032｜Protolabs: Fine-tuning tolerances for CNC parts
- 类别：实操/公差成本
- 检索标签：tolerances; GD&T; cost
- 应用于项目：不要过度标严公差；用于 AI 生成建议。
- 优先级：P1
- URL：https://www.protolabs.com/resources/design-tips/fine-tuning-tolerances-for-cnc-machined-parts/

### S033｜Xometry: Manufacturing standards
- 类别：实操/制造标准
- 检索标签：manufacturing standards; tolerances
- 应用于项目：供应商平台制造标准；用于默认交付要求。
- 优先级：P1
- URL：https://www.xometry.com/manufacturing-standards/

### S034｜Xometry Pro: CNC machining design guide PDF
- 类别：实操/CNC工艺
- 检索标签：CNC; tolerance; surface finish
- 应用于项目：CNC 加工公差和表面要求示例。
- 优先级：P1
- URL：https://xometry.pro/wp-content/uploads/2023/07/UK-CNC-Machining-Design-Guide.pdf

### S035｜Xometry: Advanced tips for CNC designs and drawings
- 类别：实操/图纸沟通
- 检索标签：CNC drawings; design intent
- 应用于项目：如何用图纸沟通设计意图和成本影响。
- 优先级：P1
- URL：https://www.xometry.com/resources/blog/advanced-tips-for-cnc-designs-and-drawings-webinar/

### S036｜Xometry Pro: CNC machining surface roughness
- 类别：实操/粗糙度
- 检索标签：surface roughness; Ra conversion
- 应用于项目：Ra 等级和应用；用于表面要求知识。
- 优先级：P1
- URL：https://xometry.pro/en/articles/cnc-machining-surface-roughness/

### S037｜Fictiv: Creating comprehensive engineering drawings for CNC machining
- 类别：实操/CNC图纸
- 检索标签：CNC drawing; tolerancing; notes
- 应用于项目：综合工程图的结构、容差和备注建议。
- 优先级：P1
- URL：https://www.fictiv.com/articles/how-to-make-a-cnc-drawing

### S038｜Fictiv: Tight tolerance parts guide
- 类别：实操/紧公差
- 检索标签：tight tolerance; design intent
- 应用于项目：紧公差设计和图纸沟通。
- 优先级：P1
- URL：https://www.fictiv.com/ebooks/the-complete-guide-to-designing-tight-tolerance-parts

### S039｜Fictiv: How design requirements drive manufacturability
- 类别：实操/DFM
- 检索标签：DFM; tolerance effort
- 应用于项目：关键尺寸紧公差，非关键尺寸放宽；用于 AI 不过度标注。
- 优先级：P1
- URL：https://www.fictiv.com/masterclass/dfm-for-cnc-masterclass/how-design-requirements-drive-cnc-manufacturability

### S040｜Fictiv: Common tolerance mistakes
- 类别：实操/质量风险
- 检索标签：tolerance mistakes; manufacturing cost
- 应用于项目：公差错误和成本风险；用于图纸自动审查规则。
- 优先级：P1
- URL：https://www.fictiv.com/articles/common-tolerance-mistakes-and-how-to-fix

### S041｜MakerVerse: Understanding technical drawings
- 类别：实操/技术图纸
- 检索标签：technical drawings; manufacturing requirements
- 应用于项目：技术图纸构成及制造要求。
- 优先级：P1
- URL：https://www.makerverse.com/resources/cnc-machining-guides/understanding-technical-drawings-a-complete-guide/

### S042｜HPPI: Engineering drawings for CNC machining
- 类别：实操/CNC工程图
- 检索标签：engineering drawings; tolerances; best practices
- 应用于项目：图纸构成、尺寸和公差实务。
- 优先级：P1
- URL：https://hppi.com/knowledge-base/cnc-machining-design/drawings

### S043｜JLCCNC: How to read engineering drawings
- 类别：实操/读图
- 检索标签：reading drawings; symbols; notes
- 应用于项目：读图顺序：标题栏、标准、单位、视图、尺寸、公差。
- 优先级：P1
- URL：https://jlccnc.com/blog/how-to-read-engineering-drawings

### S044｜JLCCNC: ISO 2768 tolerance standards for CNC machining
- 类别：实操/公差
- 检索标签：ISO 2768; CNC
- 应用于项目：ISO 2768 机加工公差理解。
- 优先级：P1
- URL：https://jlccnc.com/help/article/iso-2768-tolerance-standards-for-cnc-machining

### S045｜MiSUMi: Surface texture technical data
- 类别：实操/粗糙度
- 检索标签：surface texture; symbols
- 应用于项目：表面结构符号实务解释。
- 优先级：P1
- URL：https://sg.misumi-ec.com/tech-info/categories/technical_data/td01/a0090.html

### S046｜Quality-One: APQP overview
- 类别：质量/APQP
- 检索标签：APQP; drawing control; engineering change
- 应用于项目：APQP 中图纸、规格、变更控制的角色。
- 优先级：P1
- URL：https://quality-one.com/apqp/

### S047｜AIAG Quality Core Tools
- 类别：质量/汽车工业
- 检索标签：APQP; PPAP; FMEA; MSA; SPC
- 应用于项目：汽车供应链核心质量工具。
- 优先级：P1
- URL：https://www.aiag.org/expertise-areas/quality/quality-core-tools

### S048｜ISO: ISO 9001 explained
- 类别：质量/QMS
- 检索标签：quality management; documented information
- 应用于项目：质量体系与文控；图纸是受控文件。
- 优先级：P1
- URL：https://www.iso.org/home/insights-news/resources/iso-9001-explained.html

### S049｜Verisurf: First Article Inspection guide
- 类别：质量/FAI
- 检索标签：FAI; inspection plan
- 应用于项目：首件检验需要按图纸特性逐项验证。
- 优先级：P1
- URL：https://www.verisurf.com/blog/article/first-article-inspection/

### S050｜Lockheed Martin: Supplier FAI/AS9102 guidance
- 类别：质量/供应商检验
- 检索标签：AS9102; supplier quality; FAI
- 应用于项目：供应商 FAI 对图纸特性和记录的要求。
- 优先级：P1
- URL：https://www.lockheedmartin.com/content/dam/lockheed-martin/eo/documents/suppliers/rms/rms-quality-fai-July-2022.pdf

### S051｜SOLIDWORKS API: OpenDoc6 Method
- 类别：SolidWorks API/打开文件
- 检索标签：OpenDoc6; errors; warnings; silent
- 应用于项目：所有真实 CAD job 的打开事务必须记录 errors/warnings。
- 优先级：P0
- URL：https://help.solidworks.com/2024/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ISldWorks~OpenDoc6.html

### S052｜SOLIDWORKS API: Open Document Silently Example
- 类别：SolidWorks API/静默打开
- 检索标签：silent open; API example
- 应用于项目：静默打开示例；用于 SW session supervisor。
- 优先级：P1
- URL：https://help.solidworks.com/2024/English/api/sldworksapi/Open_Document_Silently_Example_VB.htm

### S053｜SOLIDWORKS API: swOpenDocOptions_e
- 类别：SolidWorks API/打开选项
- 检索标签：open options; silent; readonly
- 应用于项目：OpenDoc 选项枚举；用于安全加载。
- 优先级：P1
- URL：https://help.solidworks.com/2023/english/api/swconst/SOLIDWORKS.Interop.swconst~SOLIDWORKS.Interop.swconst.swOpenDocOptions_e.html

### S054｜SOLIDWORKS API: IView.GetOutline
- 类别：SolidWorks API/视图边界
- 检索标签：view outline; layout
- 应用于项目：绘图页上视图 bounding box；用于 LayoutSolver。
- 优先级：P0
- URL：https://help.solidworks.com/2018/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IView~GetOutline.html

### S055｜SOLIDWORKS API: IView.GetDisplayDimensions
- 类别：SolidWorks API/尺寸读取
- 检索标签：display dimensions; drawing view
- 应用于项目：读取视图所有 DisplayDimensions；用于真实尺寸统计。
- 优先级：P0
- URL：https://help.solidworks.com/2022/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IView~GetDisplayDimensions.html

### S056｜SOLIDWORKS API: IView.GetDisplayDimensionCount
- 类别：SolidWorks API/尺寸计数
- 检索标签：display dimension count
- 应用于项目：快速统计 DisplayDim；用于 QC。
- 优先级：P1
- URL：https://help.solidworks.com/2023/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IView~GetDisplayDimensionCount.html

### S057｜SOLIDWORKS API: IView.GetDimensionDisplayString5
- 类别：SolidWorks API/尺寸文本
- 检索标签：dimension display string
- 应用于项目：尺寸显示字符串；用于 OCR/CAD 双重校验。
- 优先级：P1
- URL：https://help.solidworks.com/2024/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IView~GetDimensionDisplayString5.html

### S058｜SOLIDWORKS API: IView Interface
- 类别：SolidWorks API/视图对象
- 检索标签：drawing view; model reference
- 应用于项目：视图对象能力边界；用于视图族理解。
- 优先级：P1
- URL：https://help.solidworks.com/2023/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IView.html

### S059｜SOLIDWORKS API: Autodimension Selected Drawing View Example
- 类别：SolidWorks API/自动尺寸
- 检索标签：AutoDimension; selected view
- 应用于项目：自动尺寸示例；只能作为候选，不能替代制图师意图。
- 优先级：P1
- URL：https://help.solidworks.com/2025/english/api/sldworksapi/Autodimension_Selected_Drawing_View_Example_VB.htm

### S060｜SOLIDWORKS API: InsertModelAnnotations3
- 类别：SolidWorks API/导入模型注解
- 检索标签：model annotations; dimensions; PMI
- 应用于项目：导入模型尺寸/注解；无 PMI 时可能返回 0。
- 优先级：P1
- URL：https://help.solidworks.com/2025/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IDrawingDoc~InsertModelAnnotations3.html

### S061｜SOLIDWORKS API: IView.GetVisibleEntities2
- 类别：SolidWorks API/可见实体
- 检索标签：visible entities; drawing view edges
- 应用于项目：从视图提取边/曲线，用于自动生成外形尺寸。
- 优先级：P1
- URL：https://help.solidworks.com/2023/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.iview~getvisibleentities2.html

### S062｜SOLIDWORKS Document Manager: GetAllExternalReferences5
- 类别：SolidWorks API/引用管理
- 检索标签：external references; broken references
- 应用于项目：磁盘级读取 drawing 外部引用，用于 refdoc 修复。
- 优先级：P1
- URL：https://help.solidworks.com/2021/english/api/swdocmgrapi/SolidWorks.Interop.swdocumentmgr~SolidWorks.Interop.swdocumentmgr.ISwDMDocument21~GetAllExternalReferences5.html

### S063｜CodeStack: Replace references using Document Manager
- 类别：SolidWorks 实操/引用替换
- 检索标签：Document Manager; ReplaceReference
- 应用于项目：Document Manager 替换 drawing/assembly 引用示例。
- 优先级：P1
- URL：https://www.codestack.net/solidworks-document-manager-api/document/replace-references/

### S064｜SOLIDWORKS MBD product page
- 类别：SolidWorks MBD/PMI
- 检索标签：MBD; PMI; 3D PDF; STEP 242
- 应用于项目：3D PMI、尺寸、公差、BOM 和发布模板；长期方向。
- 优先级：P1
- URL：https://www.solidworks.com/product/solidworks-mbd

### S065｜SOLIDWORKS STEP 242 sharing
- 类别：SolidWorks MBD/STEP242
- 检索标签：STEP 242; MBD
- 应用于项目：MBD 输出 STEP 242，供下游制造/检测。
- 优先级：P1
- URL：https://help.solidworks.com/2026/english/solidworks/sldworks/t_share_models_step242.htm

### S066｜DriveWorks: Auto Dimension Drawing View
- 类别：SOLIDWORKS自动化/尺寸
- 检索标签：auto dimension drawing view
- 应用于项目：成熟自动化产品的自动标注任务参考。
- 优先级：P1
- URL：https://docs.driveworkspro.com/topic/GTAutoDimensionDrawingView

### S067｜DriveWorks: Auto Arrange Dimensions
- 类别：SOLIDWORKS自动化/排版
- 检索标签：auto arrange dimensions
- 应用于项目：自动整理尺寸位置；对标 DimensionArrange。
- 优先级：P1
- URL：https://docs.driveworkspro.com/topic/GTAutoArrangeDimensions

### S068｜DriveWorks: DimensionText helper
- 类别：SOLIDWORKS自动化/尺寸文本
- 检索标签：dimension text; annotation
- 应用于项目：尺寸文字左右/上下附加文本规则。
- 优先级：P1
- URL：https://docs.driveworkspro.com/topic/DrawingRulesAnnotationDimensionText

### S069｜SOLIDWORKS Partner Product: Drew
- 类别：SOLIDWORKS自动化/插件
- 检索标签：drawing automation; views; dimensions
- 应用于项目：Drew 的一键视图/尺寸/表格生成是行业对标。
- 优先级：P1
- URL：https://www.solidworks.com/partner-product/drew

### S070｜CAD Booster Drew product page
- 类别：SOLIDWORKS自动化/插件
- 检索标签：drawing automation; sheet per body; dimensions
- 应用于项目：偏好/模板/视图/外形尺寸/钣金/weldment 自动化。
- 优先级：P1
- URL：https://cadbooster.com/solidworks-add-in/drew/

### S071｜CAD Booster Drew improvements
- 类别：SOLIDWORKS自动化/外形尺寸
- 检索标签：outer dimensions; sheet metal; weldment
- 应用于项目：外形尺寸、平板展开、曲线尺寸优化思路。
- 优先级：P1
- URL：https://cadbooster.com/50-drew-improvements-better-automatic-dimensions-progress-bar/

### S072｜CodeStack: Dimension visible drawing entities from view
- 类别：SOLIDWORKS API 实操/尺寸
- 检索标签：visible drawing entities; dimension longest edge
- 应用于项目：用可见实体加尺寸的可行路径。
- 优先级：P1
- URL：https://www.codestack.net/solidworks-api/document/drawing/view-dimension-drawing-entities/

### S073｜xarial xCAD GitHub
- 类别：开源/SolidWorks Add-in框架
- 检索标签：SOLIDWORKS add-in; .NET framework
- 应用于项目：Add-in 架构、公共 API、插件化开发参考。
- 优先级：P1
- URL：https://github.com/xarial/xcad

### S074｜SolidDNA GitHub
- 类别：开源/SolidWorks Add-in框架
- 检索标签：SolidWorks API wrapper; add-in
- 应用于项目：SolidWorks Add-in 封装框架参考。
- 优先级：P1
- URL：https://github.com/CAD-Booster/SolidDNA

### S075｜SOLIDWORKS Automatic Drawing Operations
- 类别：SOLIDWORKS帮助/自动图纸
- 检索标签：automatic drawing operations; dimensions
- 应用于项目：SOLIDWORKS 自带自动导入尺寸/注解功能范围。
- 优先级：P1
- URL：https://help.solidworks.com/2020/english/SolidWorks/acadhelp/c_automatic_drawing_operations_acadhelp.htm

### S076｜PyMuPDF images recipe
- 类别：视觉/PDF渲染
- 检索标签：PDF to PNG; 300 DPI
- 应用于项目：PDF→300 DPI PNG 的稳定输入基线。
- 优先级：P0
- URL：https://pymupdf.readthedocs.io/en/latest/recipes-images.html

### S077｜PaddleOCR GitHub
- 类别：视觉/OCR
- 检索标签：OCR; structure; layout; tables
- 应用于项目：中文/英文 OCR 和结构化输出；适合标题栏/备注栏。
- 优先级：P1
- URL：https://github.com/PaddlePaddle/PaddleOCR

### S078｜PaddleOCR PP-Structure docs
- 类别：视觉/版面分析
- 检索标签：layout analysis; table recognition
- 应用于项目：文档版面与表格结构识别；用于 titleblock/notes。
- 优先级：P1
- URL：https://paddlepaddle.github.io/PaddleOCR/main/en/version2.x/ppstructure/overview.html

### S079｜PaddleOCR 3.0 Technical Report
- 类别：视觉/OCR论文
- 检索标签：PP-StructureV3; document parsing
- 应用于项目：新版 PaddleOCR 结构化文档理解思路。
- 优先级：P1
- URL：https://arxiv.org/html/2507.05595v1

### S080｜Ultralytics YOLO OBB task docs
- 类别：视觉/OBB检测
- 检索标签：oriented bounding boxes; rotated objects
- 应用于项目：旋转框检测适合尺寸文字、箭头、粗糙度符号。
- 优先级：P1
- URL：https://docs.ultralytics.com/tasks/obb

### S081｜Ultralytics OBB dataset guide
- 类别：视觉/数据集格式
- 检索标签：OBB dataset; annotation format
- 应用于项目：训练工程图目标检测模型的数据格式。
- 优先级：P2
- URL：https://docs.ultralytics.com/datasets/obb

### S082｜Automated Parsing of Engineering Drawings for Structured Manufacturing Knowledge
- 类别：论文/工程图解析
- 检索标签：YOLOv11-OBB; Donut; drawing parsing
- 应用于项目：九类制造标注 OBB + 结构化 JSON；适合 Vision QC 架构。
- 优先级：P2
- URL：https://arxiv.org/pdf/2505.01530

### S083｜eDOCr: OCR on engineering drawings for production quality control
- 类别：论文/OCR
- 检索标签：engineering drawing OCR; feature control frames; info blocks
- 应用于项目：工程图分区 OCR：信息块/表格、特征控制框、其余区域。
- 优先级：P0
- URL：https://www.frontiersin.org/journals/manufacturing-technology/articles/10.3389/fmtec.2023.1154132/full

### S084｜eDOCr GitHub
- 类别：开源/OCR工程图
- 检索标签：engineering drawing OCR; Python
- 应用于项目：可复用工程图 OCR pipeline 实现思路。
- 优先级：P2
- URL：https://github.com/javvi51/eDOCr

### S085｜eDOCr2: Optimizing Text Recognition in Mechanical Drawings
- 类别：论文/OCR升级
- 检索标签：structured extraction; mechanical drawings
- 应用于项目：工程图结构化信息抽取升级，强调分区与图像处理。
- 优先级：P2
- URL：https://www.mdpi.com/2075-1702/13/3/254

### S086｜AI-powered text extraction from engineering drawings thesis
- 类别：论文/OCR综述
- 检索标签：OCR benchmark; engineering documents
- 应用于项目：工程图 OCR 方法比较和数据集稀缺性。
- 优先级：P2
- URL：https://www.utupub.fi/bitstreams/85f13f4b-276a-41eb-b933-be3134af9788/download

### S087｜Title Block Detection and Information Extraction
- 类别：论文/标题栏
- 检索标签：title block detection; information extraction
- 应用于项目：标题栏检测和信息抽取任务建模。
- 优先级：P2
- URL：https://arxiv.org/pdf/2504.08645

### S088｜Title block detection and processing research
- 类别：论文/标题栏/AEC
- 检索标签：title block; drawing organization
- 应用于项目：标题栏是工程图组织与检索关键区域。
- 优先级：P2
- URL：https://www.researchgate.net/publication/368515747_An_Approach_to_Engineering_Drawing_Organization_Title_Block_Detection_and_Processing

### S089｜NCSA: Information Extraction from Scanned Engineering Drawings
- 类别：论文/扫描图纸
- 检索标签：scanned drawings; OCR; metadata
- 应用于项目：扫描工程图 OCR 精度和人工校正框架。
- 优先级：P2
- URL：https://www.academia.edu/21829351/Information_Extraction_from_Scanned_Engineering_Drawings

### S090｜A Study of Structured/Semantic Data Extraction from Mechanical Engineering Drawings
- 类别：论文/结构化抽取
- 检索标签：mechanical drawings; semantic extraction
- 应用于项目：机械图纸中非均质数据的结构化抽取。
- 优先级：P2
- URL：https://hal.science/hal-05002280v1/file/drawing_interpretation_AR1-1.pdf

### S091｜Automatic raster engineering drawing digitisation
- 类别：论文/图纸矢量化
- 检索标签：raster engineering drawing digitisation
- 应用于项目：栅格工程图数字化和几何重建。
- 优先级：P2
- URL：https://hal.science/hal-04842487v1/document

### S092｜HuggingFace: engineering drawing title block/BOM/notes detector
- 类别：模型/工程图检测
- 检索标签：RT-DETR; title block; BOM; notes
- 应用于项目：可用于 titleblock/BOM/notes 检测的模型参考。
- 优先级：P2
- URL：https://huggingface.co/hsarfraz/eng-drawing-title-block-bill-of-material-extractor

### S093｜PubLayNet dataset
- 类别：数据集/版面分析
- 检索标签：document layout; PubLayNet
- 应用于项目：通用文档版面检测基础数据集。
- 优先级：P2
- URL：https://arxiv.org/abs/1908.07836

### S094｜DocLayNet dataset
- 类别：数据集/版面分析
- 检索标签：document layout; annotations
- 应用于项目：通用文档版面检测，有助于训练 title/figure/table 模型。
- 优先级：P2
- URL：https://arxiv.org/abs/2206.01062

### S095｜TableBank dataset
- 类别：数据集/表格识别
- 检索标签：table detection; table recognition
- 应用于项目：备注栏/标题栏表格结构识别参考。
- 优先级：P2
- URL：https://arxiv.org/abs/1903.01949

### S096｜Donut: OCR-free Document Understanding Transformer
- 类别：模型/文档解析
- 检索标签：OCR-free document understanding
- 应用于项目：OBB crop 后结构化解析的候选模型。
- 优先级：P2
- URL：https://arxiv.org/abs/2111.15664

### S097｜LayoutLMv3
- 类别：模型/文档理解
- 检索标签：document AI; layout; text-image
- 应用于项目：文档理解多模态模型参考。
- 优先级：P2
- URL：https://arxiv.org/abs/2204.08387

### S098｜Qt QProcess Class
- 类别：软件工程/UI进程隔离
- 检索标签：QProcess; stdout; finished; errorOccurred
- 应用于项目：UI 不阻塞、worker JSONL 的官方依据。
- 优先级：P0
- URL：https://doc.qt.io/qt-6/qprocess.html

### S099｜PySide6 QProcess docs
- 类别：软件工程/PySide
- 检索标签：PySide6; QProcess; I/O
- 应用于项目：PySide 应用进程隔离。
- 优先级：P2
- URL：https://doc.qt.io/qtforpython-6/PySide6/QtCore/QProcess.html

### S100｜pywinauto GitHub
- 类别：测试/UI 自动化
- 检索标签：Windows UI automation; testing
- 应用于项目：EXE 级模拟人工点击和截图验收。
- 优先级：P2
- URL：https://github.com/pywinauto/pywinauto

### S101｜Microsoft UI Automation overview
- 类别：测试/UI 自动化
- 检索标签：Windows UI Automation
- 应用于项目：Windows UI 自动化官方概念。
- 优先级：P2
- URL：https://learn.microsoft.com/en-us/windows/win32/winauto/entry-uiauto-win32

### S102｜PyAutoGUI docs
- 类别：测试/鼠标键盘截图
- 检索标签：screenshot; click; keyboard
- 应用于项目：UI robot fallback，截图/点击。
- 优先级：P2
- URL：https://pyautogui.readthedocs.io/en/latest/

### S103｜Python GUIs: QProcess in PySide6
- 类别：软件工程/QProcess实践
- 检索标签：PySide6; QProcess; progress
- 应用于项目：非阻塞外部进程实操。
- 优先级：P2
- URL：https://www.pythonguis.com/tutorials/pyside6-qprocess-external-programs/

### S104｜OpenAI Codex AGENTS.md guide
- 类别：AI开发流程/项目规则
- 检索标签：AGENTS.md; project instructions
- 应用于项目：固化项目目标、验收门槛和禁令。
- 优先级：P2
- URL：https://developers.openai.com/codex/guides/agents-md

### S105｜OpenAI Codex Skills guide
- 类别：AI开发流程/skills
- 检索标签：skills; reusable workflows
- 应用于项目：把 EXE UI robot/SolidWorks 验证/视觉审计封装成 skill。
- 优先级：P2
- URL：https://developers.openai.com/codex/skills

### S106｜OpenAI Codex Subagents guide
- 类别：AI开发流程/subagents
- 检索标签：subagents; parallel tasks
- 应用于项目：拆分 UI、CAD、视觉、发布等子代理。
- 优先级：P2
- URL：https://developers.openai.com/codex/subagents

### S107｜Windows COM IMessageFilter RetryRejectedCall
- 类别：软件工程/COM稳定性
- 检索标签：COM busy; retry rejected call
- 应用于项目：COM server 忙碌/拒绝调用时要有 message filter 和超时策略。
- 优先级：P2
- URL：https://learn.microsoft.com/en-us/windows/win32/api/objidl/nf-objidl-imessagefilter-retryrejectedcall

### S108｜SOLIDWORKS Error Report dialog help
- 类别：SolidWorks稳定性/错误报告
- 检索标签：SolidWorks crash; error report; Rx
- 应用于项目：slduiu/崩溃类问题应记录 Rx、事件、上下文，而非只看 Python。
- 优先级：P2
- URL：https://help.solidworks.com/2026/english/SolidWorks/Sldworks/c_SW_error_report_db.htm

---
## 6. sw_drawing_studio 设计落地规则

### 6.1 DrawingBlueprint 是中心，不是出图脚本

```json
{
  "drawing_blueprint": {
    "drawing_type": "manufacturing|assembly|procurement|inspection",
    "part_class": "machined_part|sheet_metal|fastener|spring|purchased_part|weldment",
    "reference_source": "同名参考 SLDDRW/PDF/PNG",
    "view_plan": {"required_views": [], "projection_method": "first_angle|third_angle|reference_matched"},
    "dimension_plan": {"display_dim_floor": 0, "required_dimensions": []},
    "annotation_plan": {"roughness_required": true, "datum_required": false},
    "titlebar_plan": {"fields": ["图号", "品名", "材质", "数量", "比例"]},
    "notes_plan": {"required_notes": []}
  }
}
```

### 6.2 验证门槛

- `files_exist` 只证明导出成功。
- `dimension_validation` 证明尺寸来源和关键尺寸覆盖。
- `reference_compare` 证明生成图接近对标图纸。
- `vision_qc` 证明可读性、标题栏、备注栏、符号和布局。
- `ui_visual_review` 证明应用界面中图纸可被人复核。
- 任何一项缺失，不得写 PASS。

### 6.3 Failure buckets

```yaml
failure_buckets:
  sw_session:
    - sw_lock_conflict
    - opendoc_timeout
    - sw_not_responding
    - dialog_blocked
  drawing_intent:
    - missing_blueprint
    - view_type_mismatch
    - display_dim_below_reference
    - reference_intent_not_followed
  layout:
    - view_overlap
    - out_of_frame
    - titlebar_collision
    - dimension_text_overlap
  annotation:
    - titlebar_incomplete
    - notes_missing
    - roughness_missing
    - datum_missing
  visual:
    - issue_schema_incomplete
    - bbox_missing
    - low_confidence
    - screenshot_visual_acceptance_not_passed
```

---
## 7. 给 Codex/AI 的行业提示词

```text
你是一个懂制造业工程图的数字制图师，不只是代码生成器。
你的目标是让 sw_drawing_studio 输出真实可加工、可检验、可采购、可追溯的 2D 工程图。

你必须先理解：
1. 工程图是制造合同，不是图片。
2. 文件存在不等于图纸合格。
3. DisplayDim、Note、标准件说明、采购说明必须严格区分。
4. 参考图纸是学习制图意图的最高优先级。
5. 制造图必须覆盖关键制造/检测尺寸；采购图必须覆盖规格、数量、外购说明；装配图必须覆盖装配关键尺寸。
6. 标题栏和备注栏不是装饰，而是文控、工艺、采购和质量的入口。
7. AI 视觉不能单独判 PASS；必须融合 CAD API、参考图对比、OCR/OBB、人工复核。
8. SolidWorks 真实操作必须持全局锁，不能并发抢同一个 COM/UI 会话。

每次开发前先问：
- 这会让图纸更像制图师画的吗？
- 这能让加工厂少问问题吗？
- 这能让质检员按图检测吗？
- 这能从参考图纸中学到规则并复用吗？
- 这能在 UI 中被人审查和诊断吗？

如果只是让 JSON 通过、让文件生成、让截图存在，但图纸仍不能加工，则不能标记完成。
```
