# SolidWorks Automation Skill 与 SolidWorks COM 接口学习笔记

> 资料来源：`https://github.com/wzyn20051216/solidworks-automation-skill`（Skill 源码）+ SolidWorks API Help（COM 部分）。
> 全文 Python 例子均使用 SolidWorks COM "米/弧度" 单位制；通过 `mm()` / `deg()` 做用户单位转换。

## 目录
1. [Skill 仓库总览](#1-skill-仓库总览)
2. [Skill Python 模块详细 API](#2-skill-python-模块详细-api)
3. [Skill MCP Server 工具一览](#3-skill-mcp-server-工具一览)
4. [SolidWorks COM 接口全景](#4-solidworks-com-接口全景)
5. [常用枚举速查](#5-常用枚举速查)
6. [关键概念与版本/语言兼容](#6-关键概念与版本语言兼容)
7. [Skill 高层封装 ↔ COM 底层调用映射](#7-skill-高层封装--com-底层调用映射)
8. [未封装 API 查证 → 实现 → 自审查 工作流](#8-未封装-api-查证--实现--自审查-工作流)
9. [常见排错清单](#9-常见排错清单)

---

## 1. Skill 仓库总览

```
solidworks-automation-skill/
├── SKILL.md                         # 元信息 + 入口、工作流约定
├── README.md                        # 中英文双语介绍、特性、快速上手、MCP 注册
├── install.js / package.json        # npx 一键安装脚本（多客户端注册）
├── setup.py / requirements.txt      # 标准 Python 安装入口、运行依赖
├── scripts/                         # ★ 核心 Python 模块（COM 封装）
│   ├── sw_session.py        # 友好 Session API（new/open/save/export/close）
│   ├── sw_preflight.py      # 入口自检：依赖检测、SolidWorks 注册检测
│   ├── sw_macro_guard.py    # 多模型 VBA 宏 Prompt + 校验 + 模板兜底
│   ├── sw_connect.py        # 连接、模板查找、新建/打开/保存、米/弧度
│   ├── sw_appearance.py     # 颜色/材质（文档/特征/组件三级容错）
│   ├── sw_part.py           # 草图、拉伸、旋转、倒圆/倒角、阵列、抽壳、镜像、筋
│   ├── sw_assembly.py       # 装配组件解析、Mate（重合/距离/同心/Gear）、Transform
│   ├── sw_motion.py         # Motion Study：tlb 加载、马达、Calculate/Play
│   ├── sw_drawing.py        # 三视图、剖视、局部放大、尺寸、BOM、PDF
│   ├── sw_export.py         # STEP/STL/IGES/Parasolid/PDF/DXF/DWG + 批量
│   └── sw_review.py         # 多视角 BMP 预览、JSON/MD 审查报告、规则评分
├── references/              # 参考文档（agent 按需阅读）
│   ├── openclaw.md / appearance.md / review.md / api-lookup.md
│   ├── part-modeling.md / assembly.md / motion-study.md / drawing.md / export.md
│   ├── advanced.md  / troubleshooting.md
├── mcp-server/              # 本地 stdio MCP Server，把 scripts/ 暴露给 LLM
│   ├── server.py / README.md
│   └── register_all_ai_mcp.{ps1,js}   # 多客户端自动注册
├── examples/                # 端到端示例（如风扇 Motion 装配）
└── agents/                  # 代理（Claude/Codex/OpenClaw）使用约定
```

Skill 的核心定位：**给 Claude / Codex / OpenClaw 等代理一套"先自检 → 用 Session 高层 API → 必要时下沉到 sw_* 模块 → 必做 sw_review 自审查"** 的稳定路径，并通过本地 MCP Server 把高频操作暴露成可调用工具。

---

## 2. Skill Python 模块详细 API

### 2.1 sw_preflight.py —— 入口自检
- `import_com_dependencies()` —— 返回 `(pythoncom, win32com.client, VARIANT)`，缺包时友好提示是否自动 `pip install`。
- `ensure_solidworks_installed()` —— 检测注册表/COM 注册；未安装则停止。
- `run_preflight()` —— 组合上述两步，所有脚本执行前调用。

### 2.2 sw_connect.py —— 连接与文档管理
- `connect_solidworks(version=None, wait_seconds=5, visible=True) -> (sw, model)`
  - 优先 `GetActiveObject("SldWorks.Application")`；失败则按 ProgID `SldWorks.Application[.{rev}]` `Dispatch`。
  - `rev = year - 2000 + 8`：2024→32、2025→33。
- `get_sw_version(sw) -> {revision, year, major}`
- `find_template(sw, doc_type)` —— 读 `GetUserPreferenceStringValue(24/25/26)` 找 `.prtdot/.asmdot/.drwdot`。
- `new_document(sw, doc_type, template_path=None)` —— `sw.NewDocument()`，再次 `ActiveDoc` 兜底拿到对象。
- `open_document(sw, file_path, read_only=False, silent=False, raise_on_error=False)` —— `sw.OpenDoc6` + `Silent=1 / ReadOnly=2`。
- `save_document(model, file_path=None)` —— `Save3(1, errors, warnings)` 或 `Extension.SaveAs(path, 0, 1, VT_DISPATCH(None), errors, warnings)`。
- 工具函数：
  - `get_com_member(obj, attr, *args)` / `safe_get_com_member` —— 兼容 pywin32 "属性 vs 方法" 双态（HRESULT `-2147352573`）。
  - `create_empty_dispatch_variant()` —— 给 `SelectByID2`、`SaveAs` 等接口提供合法的空 Dispatch。
  - `mm(value)`、`deg(value)`、`normalize_doc_type`、`_expand_path`、`_ensure_parent_dir`。

### 2.3 sw_part.py —— 零件建模
**草图：**
- `start_sketch(model, plane_name="Front Plane")` —— 自动在 `Front Plane ↔ 前视基准面`、`Top Plane ↔ 上视基准面`、`Right Plane ↔ 右视基准面` 之间兜底。
- `end_sketch(model)`、`@contextmanager sketch(model, plane)`、`current_sketch_name(model, fallback="Sketch1")`
- 几何：`sketch_line / sketch_rectangle(中心) / sketch_corner_rectangle(对角) / sketch_circle / sketch_arc / sketch_polygon / sketch_slot / sketch_spline`
- `add_dimension(model, x, y)`、`add_sketch_relation(model, "sgFIXED" | "sgHORIZONTAL" | "sgVERTICAL" | "sgPARALLEL" | "sgPERPENDICULAR" | "sgTANGENT" | "sgCONCENTRIC" | "sgCOLINEAR" | "sgEQUAL" | "sgSYMMETRIC" | "sgMIDPOINT" | "sgCOINCIDENT" | …)`

**特征：**
- `extrude_boss(model, sketch_name, depth, direction=True, merge=True)` → `IFeatureManager.FeatureExtrusion3(...)`
- `extrude_cut(model, sketch_name, depth, direction, flip)` → `FeatureCut4`，`depth==0` 时切完全贯穿（`swEndCondThroughAll=1`）
- `extrude_midplane(model, sketch_name, total_depth)` → 中面对称（`swEndCondMidPlane=6`）
- `revolve_boss(model, sketch_name, angle_rad, axis_sketch_name=None)` → `FeatureRevolve2`
- `fillet(model, radius)` → `FeatureFillet(195, ...)`（195 = 默认常半径选项位）
- `chamfer(model, distance, angle_deg=45)` → `InsertFeatureChamfer`
- `linear_pattern(...)`、`circular_pattern(...)`、`shell(model, thickness)`、`mirror_feature(...)`、`rib(...)`
- `hole_wizard(...)` —— 当前是占位接口；实际复杂参数仍需查 API Help。

**辅助：** `_select_by_id`、`_ensure_sketch_selected`（拉伸前若没有选择则按草图名 + 别名兜底再选）。

### 2.4 sw_assembly.py —— 装配体
**Mate 类型常量：** `SW_MATE_COINCIDENT=0 / CONCENTRIC=1 / PARALLEL=3 / DISTANCE=5 / GEAR=10`；`SW_COMPONENT_FULLY_RESOLVED=2 / RESOLVED=3 / LIGHTWEIGHT=1 / SUPPRESSED=0`；`SW_SOLID_BODY=0`。

**组件管理：**
- `add_component(asm, part_path, x=0, y=0, z=0, config_name="")` → `IAssemblyDoc.AddComponent4`
- `resolve_component(component, state=2)` → `IComponent2.SetSuppression2`
- `get_component_model(component, resolve=True, raise_on_error=True)` → `IComponent2.GetModelDoc2`
- `get_component_feature(component, ["前视基准面","Front Plane"])` —— 候选名兜底
- `get_assembly_entity(component, feature_or_face)` → `IComponent2.GetCorresponding`，把零件文档对象映射到装配体上下文（创建 Mate 必备）
- `get_component_feature_entity(component, aliases)` —— 上述两步组合
- `find_largest_cylinder_face(component, min_radius, max_radius)` —— 遍历 `IPartDoc.GetBodies2(0,False)` → 每个 `IBody2.GetFaces` → `IFace2.GetSurface` → `IsCylinder` + `CylinderParams[6]=半径` + `GetArea`，取最大圆柱面并映射回装配体上下文

**Mate：**
- `select_entities_for_mate(model, e1, e2, mark=1)` —— 校验当前选择数量必须 = 2，否则清空再抛错
- `add_mate5_checked(asm, mate_type, align=0, flip=False, distance=0, …, gear_num, gear_den, lock_rotation=False, name=None)` —— 15 参数 `IAssemblyDoc.AddMate5`，`errorStatus = VARIANT(VT_BYREF|VT_I4)` 全程检查（`swAddMateError_NoError=1` 或 `Unknown=0`）。
- `add_concentric_mate_by_cylinders(asm, ca, cb, radius_a, radius_b, name, lock_rotation=False)` —— 找两组件最大圆柱面 + 同心 Mate。
- `add_gear_mate_by_cylinders(asm, ca, cb, teeth_a, teeth_b, ...)` —— `gear_num/gear_den` 不得为 0。
- `add_revolute_joint_by_cylinders(asm, ca, cb, ...)` —— Hinge 等价：同心 + 不锁旋转。
- `add_mate_coincident(asm, e1_name, e1_type, e2_name, e2_type)` —— 基于名字的简化重合配合。

**位姿与遍历：**
- `build_transform_data_x(tx, ty, tz, angle_rad)` —— 16 元组 MathTransform.ArrayData（绕 X 旋转 + 平移）
- `apply_component_transform_x(component, ...)` → `Component2.SetTransformAndSolve2(transform)` 或回退 `Transform2 = transform`
- `iter_feature_tree(model, include_subfeatures=True)` —— 遍历 FirstFeature/GetNextFeature/GetFirstSubFeature/GetNextSubFeature
- `collect_mate_feature_summary(model)` —— 产出 `[{name, type, depth}]`，按 `GetTypeName2 == MateGroup` / 以 `Mate` 开头 / 名字含 `mate/配合` 筛选

### 2.5 sw_drawing.py —— 工程图
- `create_standard_views(drw, part_path)` → `IDrawingDoc.Create3rdAngleViews2`（第三角投影三视图）
- `add_view(drw, part_path, view_name, x, y, scale=None)` → `CreateDrawViewFromModelView3`
  - view_name：`*Front / *Back / *Top / *Bottom / *Left / *Right / *Isometric / *Trimetric / *Dimetric`
  - 比例：`view.ScaleRatio = (1.0, 1.0/scale)`（如 0.5 → 1:2）
- `add_section_view(drw, x, y)` → `CreateSectionViewAt5`
- `add_detail_view(drw, x, y, scale=2.0)` → `CreateDetailViewAt4`
- `insert_dimensions(drw, view=None)` → `Extension.InsertModelAnnotations3`，参数 `(0, 32, True, True, False, False)` = 整模型 + DimMarkedForDrawing
- `add_note(drw, x, y, text)` → `InsertNote`
- `insert_bom_table(drw, template_path, x, y, bom_type=1, config_name="")` → `InsertBomTable4`，`bom_type` ∈ 1=顶层/2=仅零件/3=缩进
- `set_sheet_format(drw, format_path)` → `Sheet.SetTemplateName`（图框 .slddrt）
- `add_sheet(drw, paper_size=7, template_path="")` → `NewSheet4`，纸张 `0..9` 对应 A..E/A4..A0
- `get_all_views(drw)` → 当前 Sheet 上 `GetViews()` 的 `name/type/scale`
- `export_sheet_to_pdf(model, output_path, sheet_names=None)` —— `sw.GetExportFileData(1=swExportPDFData)` + `Extension.SaveAs`

### 2.6 sw_export.py —— 文件导出
- 通用 `_export_generic(model, path)` = `model.Extension.SaveAs(path, 0, 1, VT_DISPATCH(None), errors, warnings)`，扩展名决定格式。
- `export_to_step / export_to_iges / export_to_parasolid` —— 直接走通用底座。
- `export_to_stl(model, path, quality="fine"|"coarse")` —— `model.SetUserPreferenceIntegerValue(78, 0|1=swSTLQuality)`。
- `export_to_pdf(model, path, sheet_names=None)` —— 工程图专用，`pdf_data.SetSheets(0, names)`。
- `export_to_dxf(model, path)` —— 工程图走通用；零件（钣金展开图）走 `model.ExportToDWG2(...)`。
- `export_flat_pattern_dxf(model, path)` —— 钣金展开 DXF。
- `batch_export(sw, file_paths, out_dir, format_ext)` —— 批量打开（`Silent=1`）→ 导出 → 关闭。

### 2.7 sw_session.py —— 友好 Session API
`SolidWorksSession(version, wait_seconds=5, visible=True)`：
- 属性：`.sw / .model / .active_doc`
- `.new(doc_type, template_path)` / `.new_part / .new_assembly / .new_drawing`
- `.open(file_path, read_only=False, silent=False, raise_on_error=True)`
- `.save(model=None, file_path=None)`
- `.export(model=None, output_path=str, format_ext=None, **kwargs)`
  - 内部分发 `EXPORTERS = {.step,.stp:export_to_step, .stl:export_to_stl, .iges,.igs:export_to_iges, .pdf:export_to_pdf, .dxf,.dwg:export_to_dxf}`
- `.close(model=None, title=None)` → `sw.CloseDoc(title)`

模块函数 `session(...)` 是便捷构造器。

### 2.8 sw_appearance.py —— 颜色/材质
- `rgb01(color)` —— 字符串预设/`#RRGGBB`/`(r,g,b)` 0..255 或 0..1 → `(r,g,b) ∈ [0,1]³`
- `material_values(color, ambient=0.35, diffuse=0.75, specular=0.45, shininess=0.35, transparency=0.0, emission=0.0)` —— 9 元素材质数组
- `set_document_appearance(model, color, configuration="")` —— 依次尝试 `MaterialPropertyValues=values` / `SetMaterialPropertyValues2` / `ISetMaterialPropertyValues2`
- `set_feature_appearance(feature, color, configuration)` / `set_component_appearance(component, color, configuration)`
- `apply_named_appearance(target, name)` —— 按文档/组件/特征顺序兜底
- 预设：`PRESET_COLORS = {iron_red, armor_gold, dark_gunmetal, arc_blue, black, white, silver}`

### 2.9 sw_motion.py —— Motion Study
- 常量：`SW_FM_AEM_ROTATIONAL_MOTOR=78`、`SW_MOTION_STUDY_BASIC_MOTION=1`
- `ensure_motion_type_library(raise_on_error=False)` —— 在常见路径搜索 `swmotionstudy.tlb`（含 `Program Files\SOLIDWORKS Corp\SOLIDWORKS\` 与 `Program Files\Dassault Systemes\SOLIDWORKS*\`），用 `pythoncom.LoadTypeLib + win32com.client.gencache.EnsureModule` 加载，解决 pywin32 把 `CreateMotionStudy/Activate/Calculate/Play` 看成属性的问题。
- `motion_member(obj, attr, *args)` —— 兼容属性/方法双态。
- `get_motion_study_manager(asm, load_type_library=True)` → `Extension.GetMotionStudyManager`
- `create_motion_study(asm, name, duration=4.0, study_type=None)` → `manager.CreateMotionStudy()` + `Activate()` + `SetDuration(seconds)`，可选写 `study.StudyType`
- `add_constant_speed_rotary_motor(study, direction_reference, load_reference, rpm, relative_component=None, name=None, reverse=False)`
  - 内部：`data = study.CreateDefinition(78)` →
    `data.DirectionReference = direction_reference` →
    `motion_member(data, "ConstantSpeedMotor", rpm)` →
    `data.ReverseDirection = reverse` → 可选 `data.RelativeComponent / data.Location` →
    `_set_load_references(data, [load_reference])`（tuple/list/`VARIANT(VT_ARRAY|VT_VARIANT)` / `VARIANT(VT_ARRAY|VT_DISPATCH)` 四层兜底）→
    `study.CreateFeature(data)`
- `add_constant_speed_rotary_motor_by_cylinders(study, shaft_comp, rotor_comp, shaft_radius, rotor_radius, rpm, name, reverse)` —— 借助 `find_largest_cylinder_face` 自动选轴/转子。
- `calculate_and_play(study, play=True)` → `Calculate` + `Play`

### 2.10 sw_review.py —— 自审查
- 视图常量 `STANDARD_VIEWS = {front:1, back:2, left:3, right:4, top:5, bottom:6, isometric:7, trimetric:8, dimetric:9}`
- `set_standard_view(model, view_name)` → `ShowNamedView2("", view_id)` 或 `ShowNamedView2(name, -1)`
- `zoom_to_fit(model)` → `ViewZoomtofit2 + GraphicsRedraw2`
- `save_preview(model, output_path, view_name="isometric", width=1600, height=1000)` → `model.SaveBMP(path, w, h)`
- `save_review_previews(model, output_dir, basename="review", views=("isometric","front","top","right"))`
- `inspect_bmp_preview(path)` —— 解析 BMP 头取宽高 + 取前 200000 字节计算独立字节数，<8 视为 `likely_blank`
- `collect_model_summary(model)` —— `GetTitle / GetPathName / GetType` + 走特征树
- `build_review_report(model, output_dir, basename, views, expected_outputs)` —— 生成 `previews / expected_outputs / checks / review_notes`
- `evaluate_review_report(report)` —— 规则评分：`status ∈ {pass, warn, fail}`、`score 0..100`、`issues[]`、`recommendations[]`
- `write_review_report / write_markdown_summary / run_review` —— 一站式，生成 `*_review_report.json` + `*_review_summary.md`
- 命令行：`python sw_review.py --file ... --output-dir ... --expected ... --views isometric,front,top,right [--fail-on-warn]`

### 2.11 sw_macro_guard.py —— 多模型 VBA 宏防护
- `build_prompt(user_request, model_name)` —— GPT 系列保留原始；Kimi/Claude/未知模型加强格式约束（"只允许输出 VBA 源码"）
- `validate_vba_macro(text) -> ValidationResult(ok, issues)` —— 必须包含 `SldWorks`、`ModelDoc2`、`Sub`、`End Sub`
- `fallback_macro_for_request(user_request)` —— 关键词触发本地 VBA 模板（立方体/圆柱/拉伸/草图）
- 推荐链路：`build_prompt → 调模型 → validate_vba_macro → 失败重试 1~2 次 → 仍失败 fallback_macro_for_request`

---

## 3. Skill MCP Server 工具一览

启动：`python mcp-server/server.py`（stdio）。所有工具串行执行，加全局锁。注册器 `register_all_ai_mcp.{ps1,js}` 一并写入 Codex / Claude Code / Claude Desktop / Cursor / Windsurf。

| 工具 | 主要参数 | 作用 | 对应 Python 封装 |
|---|---|---|---|
| `solidworks_health_check` | `connect?: bool` | 检查依赖 / SolidWorks / Motion tlb | `sw_preflight.run_preflight` + `sw_motion.ensure_motion_type_library` |
| `solidworks_connect` | — | 连接 SW，回传活动文档摘要 | `sw_connect.connect_solidworks` |
| `solidworks_new_document` | `doc_type` | 新建零件/装配/工程图 | `sw_session.new` |
| `solidworks_create_basic_part` | `shape=box\|cylinder, radius_mm/depth_mm/...., output_path, color` | 一键建立基础形状并保存 | `sw_session + sw_part + sw_appearance` |
| `solidworks_open_document` | `path, read_only, silent` | 打开文件 | `sw_session.open` |
| `solidworks_save_document` | `path?` | 保存或另存 | `sw_session.save` |
| `solidworks_close_documents` | `all_documents: bool` | 关闭活动 / 全部 | `sw_session.close` |
| `solidworks_add_component` | `path, x_mm, y_mm, z_mm, fix_component` | 加件并可固定 | `sw_assembly.add_component` |
| `solidworks_set_component_fixed` | `keyword, fixed: bool` | 按名字关键字固定/浮动 | `IAssemblyDoc.FixComponent / FloatComponent` |
| `solidworks_add_coincident_mate` | `component_a/b_keyword, feature_a/b_name` | 重合 Mate | `add_mate_coincident` |
| `solidworks_add_distance_mate` | …+ `distance_mm, flip, align` | 距离 Mate | `add_mate5_checked(MATE_DISTANCE)` |
| `solidworks_add_concentric_mate` | `radius_*_min/max_mm, lock_rotation` | 同心 Mate | `add_concentric_mate_by_cylinders` |
| `solidworks_set_appearance` | `color, scope=document\|component, keyword?` | 颜色 | `sw_appearance.*` |
| `solidworks_export_active` | `path, format?` | STEP/STL/IGES/Parasolid/PDF/DXF | `sw_session.export` |
| `solidworks_review_active` | `output_dir, basename, expected_outputs[]` | 多视角预览 + JSON/MD 报告 | `sw_review.run_review` |
| `solidworks_add_rotary_motor` | `shaft_keyword, rotor_keyword, *_radius_*_mm, rpm, study_name, motor_name, duration_seconds, calculate, play` | 装配体马达 + 计算/播放 | `sw_motion.create_motion_study + add_constant_speed_rotary_motor_by_cylinders` |

> 设计原则：**不暴露任意 Python/VBA 执行**；所有名字加 `solidworks_` 前缀避免冲突；返回值带建议性文字以利 LLM 自纠错。

---

## 4. SolidWorks COM 接口全景

### 4.1 顶层与文档对象树

```
SldWorks.Application  (ISldWorks)               ProgID: SldWorks.Application[.{rev}]
 ├─ ActiveDoc                       → IModelDoc2
 ├─ NewDocument(template, ...)      → IModelDoc2
 ├─ OpenDoc6(path, type, opt, ...)  → IModelDoc2
 ├─ CloseDoc(title)
 ├─ GetExportFileData(swExportPDFData=1) → IExportPdfData / IExportStlData / ...
 ├─ GetUserPreferenceStringValue(swFileLocationsParts=24, ...)
 ├─ Visible / RevisionNumber / FrameWidth / GetCommandManager …
 ├─ GetMassProperties / SetExportFileName / SetUserPreferenceIntegerValue …
 │
 └─ IModelDoc2  ─── 三种派生：IPartDoc / IAssemblyDoc / IDrawingDoc
      ├─ Extension : IModelDocExtension
      │   ├─ SelectByID2(name,type,x,y,z,append,mark,callout,selOption) → bool
      │   ├─ InsertModelAnnotations3(...)
      │   ├─ SaveAs(path, version=0, options=1, exportData, errors, warnings)
      │   ├─ GetMotionStudyManager() → IMotionStudyManager
      │   ├─ CustomPropertyManager(config) → ICustomPropertyManager
      │   └─ RunMacro2 / GetSelectionManager / Insert*
      ├─ FeatureManager : IFeatureManager   (创建特征)
      │   ├─ FeatureExtrusion3 / FeatureCut4 / FeatureRevolve2 / FeatureFillet
      │   ├─ FeatureLinearPattern3 / FeatureCircularPattern4
      │   ├─ InsertFeatureShell / InsertFeatureChamfer / InsertMirrorFeature2
      │   ├─ InsertProtrusionBlend2 / InsertProtrusionSwept4
      │   ├─ InsertRib / InsertSheetMetalBaseFlange / InsertWeldmentMember3 …
      │   └─ FirstFeature / Document
      ├─ SketchManager : ISketchManager     (草图)
      │   ├─ InsertSketch(单切换) / Insert3DSketch
      │   ├─ CreateLine / CreateCircleByRadius / CreateArc / CreateCenterRectangle
      │   ├─ CreateCornerRectangle / CreatePolygon / CreateSpline2 / CreateSketchSlot
      │   └─ ActiveSketch → ISketch
      ├─ SelectionManager : ISelectionMgr
      │   ├─ GetSelectedObjectCount2(mark) / GetSelectedObject6(i, mark)
      │   └─ DeSelect2 / ClearSelection2 / SetSelectionPoint2
      ├─ ConfigurationManager : IConfigurationManager
      │   ├─ ActiveConfiguration / AddConfiguration2 / DeleteConfiguration2
      ├─ EquationMgr → IEquationMgr
      ├─ ClearSelection2 / EditRebuild3 / ForceRebuild3 / ViewZoomtofit2
      ├─ Save3 / SaveBMP / GetTitle / GetPathName / GetType
      ├─ AddDimension2 / AddCustomInfo3 …
      └─ FirstFeature / FeatureByName(name) → IFeature
```

派生：

- **IPartDoc**：实体几何接口；`GetBodies2(swSolidBody=0)`、`InsertSheetMetal*`、`InsertGlobalVariable`。
- **IAssemblyDoc**：组件装配；`AddComponent4 / AddMate5 / AddMateReference / EditAssembly / FixComponent / FloatComponent / EditPart`。
  - 组件：`IComponent2`（`Name2 / Transform2 / SetSuppression2 / GetCorresponding / Select4 / GetModelDoc2 / IsRoot`）。
  - 配合：`IMate2`（`MateAlignment / MateType / Width / TransformControl`）。
- **IDrawingDoc**：`Create3rdAngleViews2 / CreateDrawViewFromModelView3 / CreateSectionViewAt5 / CreateDetailViewAt4 / NewSheet4 / GetCurrentSheet / InsertBomTable4`。
  - `IView`：`Name / Type / ScaleRatio / GetVisibleEntityCount2 / SetSize2`。
  - `ISheet`：`SetTemplateName / GetSize / GetProperties2 / GetViews`。

底层几何：

```
IBody2   → GetFaces() → IFace2  → GetSurface() → ISurface  (IsCylinder/IsPlane/IsSphere/IsCone)
         → GetEdges() → IEdge   → GetCurve()   → ICurve
         → GetVertices() → IVertex
ISketch  → GetSketchSegments() → ISketchSegment / ISketchPoint
IFeature → GetTypeName2() / GetDefinition() → IFeatureData (ExtrusionData / FilletData / …)
```

工程图特殊：`IDrawingDoc → IView → IDimension / IAnnotation / INote`；BOM = `IBomTableAnnotation`，`ITableAnnotation`。

外观：`IAppearanceSetting`（2010+）；低版本/容错路径走 `MaterialPropertyValues`。

Motion：

```
IModelDocExtension.GetMotionStudyManager() → IMotionStudyManager
   .CreateMotionStudy() / .GetMotionStudyCount / .GetMotionStudyByIndex
   IMotionStudy.Activate / SetDuration / Calculate / Play / StudyType
   IMotionStudy.CreateDefinition(swFmAEMRotationalMotor=78)
        → ISimulationMotorFeatureData
            .DirectionReference / .LoadReferences(VARIANT[]) /
            .ConstantSpeedMotor(rpm) / .ReverseDirection / .RelativeComponent
   IMotionStudy.CreateFeature(featureData) → IFeature
```

事件：可订阅 `SldWorks.SldWorksEvents`（pywin32 `WithEvents`）。代理脚本极少用到。

---

## 5. 常用枚举速查

### 5.1 文档与打开 — `swDocumentTypes_e` / `swOpenDocOptions_e`
| 名 | 值 | 含义 |
|---|---|---|
| swDocPART | 1 | 零件 |
| swDocASSEMBLY | 2 | 装配体 |
| swDocDRAWING | 3 | 工程图 |
| swOpenDocOptions_Silent | 1 | 静默打开 |
| swOpenDocOptions_ReadOnly | 2 | 只读 |
| swOpenDocOptions_ViewOnly | 4 | 仅查看 |
| swOpenDocOptions_LoadModel | 16 | 加载模型 |

### 5.2 选择类型 — `swSelectType_e`（数值 + `SelectByID2` 字符串）
- 常用数值：`swSelEDGES=1, swSelFACES=2, swSelVERTICES=3, swSelDATUMPLANES=4, swSelDATUMAXES=5, swSelSKETCHES=9, swSelEXTSKETCHSEGS=12, swSelCOMPONENTS=20, swSelMATES=83, swSelBODYFEATURES=83, swSelSOLIDBODIES=64`
- 常用字符串："PLANE / AXIS / FACE / EDGE / VERTEX / SKETCH / COMPONENT / BODYFEATURE / MATEPLANE"

### 5.3 拉伸/切除终止条件 — `swEndConditions_e`
| 名 | 值 |
|---|---|
| swEndCondBlind | 0 |
| swEndCondThroughAll | 1 |
| swEndCondUpToNext | 2 |
| swEndCondUpToVertex | 3 |
| swEndCondUpToSurface | 4 |
| swEndCondOffsetFromSurface | 5 |
| swEndCondMidPlane | 6 |
| swEndCondUpToBody | 7 |

### 5.4 配合 — `swMateType_e` / `swMateAlign_e`
| MateType | 值 | MateAlign | 值 |
|---|---|---|---|
| Coincident | 0 | Aligned | 0 |
| Concentric | 1 | AntiAligned | 1 |
| Perpendicular | 2 | Closest | 2 |
| Parallel | 3 |   |  |
| Tangent | 4 |   |  |
| Distance | 5 |   |  |
| Angle | 6 |   |  |
| Symmetric | 8 |   |  |
| CamFollower | 9 |   |  |
| Gear | 10 |   |  |
| RackPinion | 11 |   |  |
| Screw | 12 |   |  |
| Universal | 13 |   |  |
| Hinge | 14 |   |  |
| Slot | 15 |   |  |
| Width | 16 |   |  |

`swAddMateError_e`：`Unknown=0, NoError=1, IncorrectSelections=2, OverDefined=3, …`。

### 5.5 文件导出 — `swExportDataFileType_e` / `swSaveAsVersion_e`
- `swExportPDFData=1`、`swExportStlData=2`、`swExportEdrwData=…`（Skill 现版本主要用 1）。
- `Extension.SaveAs(path, version, options, exportData, errors, warnings)`
  - version = `swSaveAsVersion_e`：0 = Current。
  - options = `swSaveAsOptions_e`：1 = Silent，2 = Copy，4 = AvoidRebuildOnSave。

### 5.6 钣金 / 焊件 / 仿真 / Motion
- `swSheetMetalBendType_e`、`swSheetMetalReliefType_e`
- `swWeldmentSubFeatures_e`
- `swSimulationStudyType_e`：0=Static、1=Frequency、4=Thermal …
- 旋转马达：`swMotionFeatureManagerActiveExitMotor_e.swFmAEMRotationalMotor=78`
- Motion Study 类型：`swMotionStudyType_e.BasicMotion=1, MotionAnalysis=4, AnimationOnly=0`

### 5.7 组件状态 — `swComponentSuppressionState_e`
0 = Suppressed、1 = Lightweight、2 = FullyResolved、3 = Resolved。

---

## 6. 关键概念与版本/语言兼容

### 6.1 单位
- **长度**：API 一律 **米**；`mm(50)=0.05`。
- **角度**：弧度；`deg(90)=π/2`。
- **STL 质量**：`SetUserPreferenceIntegerValue(78, 0|1)` —— 0 fine, 1 coarse。
- **草图坐标**：相对草图局部坐标系，原点在草图基准面交点。

### 6.2 中英文版本基准面
| 英文 | 中文 |
|---|---|
| Front Plane | 前视基准面 |
| Top Plane | 上视基准面 |
| Right Plane | 右视基准面 |
| Sketch1 | 草图1 |

Skill 的 `start_sketch / current_sketch_name / get_component_feature` 都做了候选名兜底，避免代理在中文 SolidWorks 里失败。

### 6.3 SelectByID2 / 选择标记 (mark)
- 形参：`(name, type, x, y, z, append, mark, callout, selectOption)`。
- `name` 不指定时可以用坐标 `(x,y,z)` 选择空间中最接近的实体。
- `mark` 让 FeatureManager 区分多组选择：例如圆形阵列的轴线 mark=1，被阵列特征 mark=4。
- `callout` 必须是 IDispatch；pywin32 下用 `VARIANT(VT_DISPATCH, None)` 兜底（即 `create_empty_dispatch_variant`）。

### 6.4 VARIANT / by-ref 参数
- 任何 `OpenDoc6 / SaveAs / AddMate5 / Save3 / ExportToDWG2` 之类返回 `errors` / `warnings` / `status` 的方法，**必须** 用 `VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)` 包装。
- `LoadReferences = VARIANT(VT_ARRAY|VT_DISPATCH, [...])`：Skill 用了 `tuple → list → VARIANT(VT_ARRAY|VT_VARIANT) → VARIANT(VT_ARRAY|VT_DISPATCH)` 四层兜底，提升不同版本兼容性。

### 6.5 pywin32 "属性/方法双态" 坑
- 同一成员（如 `FirstFeature`、`CreateMotionStudy`、`GetTitle`）在不同 SolidWorks/pywin32 版本下可能是属性也可能是方法。
- 触发 HRESULT `-2147352573` ("Member not found") 时应回退到属性读取。
- Skill 通过 `get_com_member / safe_get_com_member / motion_member` 统一处理。

### 6.6 SilentMode / 阻塞对话框
- 打开模型：`OpenDoc6` 加 `swOpenDocOptions_Silent=1`。
- 全局静默：`sw.SetUserPreferenceToggle(swInputDimValOnCreate, False)`、`sw.CommandInProgress = True`。
- 抛出 SolidWorks 警告对话框时，可在脚本前加 `pythoncom.CoInitialize()` 并按需 `sw.Visible = False`。

### 6.7 SldWorks vs Apprentice
- 完整功能：`SldWorks.Application`（需要主程序进程，本 Skill 全程使用）。
- Apprentice：`SwDocumentMgr.Application` 等，无 GUI，能力子集（读取 / 批量转换 / 属性）。

### 6.8 版本号映射
- ProgID：`SldWorks.Application.{rev}`，`rev = year - 2000 + 8`：2024 → 32、2025 → 33。
- `RevisionNumber` 大版本号 = `rev`。

---

## 7. Skill 高层封装 ↔ COM 底层调用映射

| Skill 函数 | 等价底层 COM 调用 |
|---|---|
| `SolidWorksSession().new_part()` | `sw = win32com.client.Dispatch("SldWorks.Application")` → `sw.NewDocument(template_path, 0, 0, 0)` |
| `open_document(sw, path, silent=True)` | `errors=VARIANT(VT_BYREF\|VT_I4,0); warnings=...; sw.OpenDoc6(path, 1, swOpenDocOptions_Silent, "", errors, warnings)` |
| `save_document(model, path)` | `model.Extension.SaveAs(path, 0, 1, VARIANT(VT_DISPATCH,None), errors, warnings)` |
| `start_sketch(model, "Front Plane")` | `model.Extension.SelectByID2("Front Plane","PLANE",0,0,0,False,0,callout,0)` → `model.SketchManager.InsertSketch(True)` |
| `sketch_circle(model, 0, 0, mm(25))` | `model.SketchManager.CreateCircleByRadius(0, 0, 0, 0.025)` |
| `extrude_boss(model, "Sketch1", mm(50))` | 选中草图 → `model.FeatureManager.FeatureExtrusion3(True, False, True, 0, 0, 0.05, 0.0, …)` |
| `extrude_cut(model, name, 0)` | end_condition=`swEndCondThroughAll=1` → `model.FeatureManager.FeatureCut4(True, False, False, 1, 0, 0.01, …)` |
| `fillet(model, mm(2))` | `model.FeatureManager.FeatureFillet(195, 0.002, 0, 0, None, None, None)` |
| `chamfer(model, mm(1), 45)` | `model.FeatureManager.InsertFeatureChamfer(4, 1, 0.001, π/4, 0, 0, 0, 0)` |
| `add_component(asm, path, x, y, z)` | `asm.AddComponent4(path, "", x, y, z) → IComponent2` |
| `add_concentric_mate_by_cylinders(asm, ca, cb)` | 找两组件最大圆柱面 → `face.Select2(append, mark=1)` ×2 → `asm.AddMate5(swMateConcentric=1, …, errorStatus)` |
| `add_gear_mate_by_cylinders(asm, ca, cb, Tn=1, Td=2)` | 同上但 `swMateGear=10` 并填 `gear_num/gear_den` |
| `apply_component_transform_x(comp, tx,ty,tz, θ)` | 改 `Component2.Transform2.ArrayData` → `Component2.SetTransformAndSolve2(transform)` |
| `create_standard_views(drw, part_path)` | `drw.Create3rdAngleViews2(part_path)` |
| `add_view(drw, path, "*Isometric", x, y, scale)` | `drw.CreateDrawViewFromModelView3(path, "*Isometric", x, y, 0)`，再 `view.ScaleRatio=(1,1/scale)` |
| `export_to_pdf(drw, out)` | `pdf=sw.GetExportFileData(1); pdf.SetSheets(0, names); drw.Extension.SaveAs(out, 0, 1, pdf, errors, warnings)` |
| `export_to_step(model, out)` | `model.Extension.SaveAs(out.step, 0, 1, VARIANT(VT_DISPATCH,None), errors, warnings)`（依扩展名自识别格式） |
| `set_document_appearance(model, "iron_red")` | 9 元素材质数组 → 依次尝试 `model.SetMaterialPropertyValues2(values, 0, "")` / `model.MaterialPropertyValues = values` |
| `create_motion_study(asm, "spin", 4.0)` | `mgr=asm.Extension.GetMotionStudyManager(); study=mgr.CreateMotionStudy(); study.Activate(); study.SetDuration(4.0)` |
| `add_constant_speed_rotary_motor(study, dirRef, loadRef, rpm)` | `data=study.CreateDefinition(78); data.DirectionReference=dirRef; data.ConstantSpeedMotor(rpm); data.LoadReferences=[loadRef]; study.CreateFeature(data)` |
| `run_review(model, out_dir)` | `model.ForceRebuild3(False)` → `ShowNamedView2 + SaveBMP` ×N → 解析 BMP → 写 JSON/MD |

---

## 8. 未封装 API 查证 → 实现 → 自审查 工作流

1. **查文档**：先读 `references/api-lookup.md`，再去官方 [SolidWorks API Help](https://help.solidworks.com/) 搜接口名（如 `IFeatureManager.HoleWizard5`），确认：
   - 方法签名（参数顺序、类型）
   - by-ref / VARIANT / Dispatch 参数
   - 关联枚举（如 `swSelectType_e`、`swMateType_e`、`swEndConditions_e`）
   - 版本差异（HoleWizard 系列从 4 → 5 → …）
   - 返回值含义（IFeature 还是 bool）
2. **本地 SDK**：`C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\api\` 下有 `samples/`、`redist/`、`tlb`，可直接看 VBA/VB.NET/C# 示例。
3. **写最小验证脚本**：先连接、新建模型，按签名调用，每个返回值都做 `None / False / errors.value` 检查；by-ref 用 `VARIANT(VT_BYREF|VT_I4, 0)` 包装。
4. **试运行 + 保存 + 导出**：保证文件落盘，否则不能算成功。
5. **自审查**：调用 `sw_review.run_review(model, out_dir, expected_outputs=[...])`，必读 `evaluation.status`、`issues`。
6. **沉淀**：把稳定写法回写为 `scripts/sw_*.py` 中新函数，遇到的坑写进 `references/troubleshooting.md`。
7. **永远禁止猜接口名**——尤其 COM 方法的长参数表、枚举值、对齐方式。

---

## 9. 常见排错清单

### 9.1 连接 SolidWorks
| 现象 | 修复 |
|---|---|
| `pywintypes.com_error: 元素未找到` | SolidWorks 没启动过或 COM 未注册：先手动启动 SolidWorks 一次 |
| 32/64 位 mismatch | Python 与 SolidWorks 位数必须一致（通常都是 64 位） |
| `GetActiveObject` 拿不到实例 | 改用 `Dispatch("SldWorks.Application")` 启动新实例；`Visible=True` 便于调试 |
| pywin32 cache 损坏 | 删除 `%TEMP%\gen_py\` 后重新运行；`gencache.EnsureDispatch` 或 `EnsureModule` |

### 9.2 草图 / 特征
| 现象 | 修复 |
|---|---|
| `SelectByID2` 选基准面失败 | 中文版要传 "前视基准面"；用 Skill 的 `start_sketch` 自动兜底 |
| 拉伸返回 None | 草图未闭合 / 单位没转米 / 草图退出后名字不是 `Sketch1`；用 `current_sketch_name(model)` 取实际名 |
| 圆角失败 | 未先选择边线，且 `FeatureFillet` 参数 `195` 与边线选择 mark 不匹配；先 `Extension.SelectByID2(edge_name,"EDGE", append=True, mark=1)` |
| 切除整通失败 | `depth=0` 时 Skill 自动用 `swEndCondThroughAll=1`；若传非 0 又想贯穿需手动改 endCondition |

### 9.3 装配 / Mate
| 现象 | 修复 |
|---|---|
| `AddMate5 errorStatus=2 IncorrectSelections` | 选择数量 ≠ 2 或选择实体不属于装配体上下文：先 `get_assembly_entity` 做 `GetCorresponding` |
| 同心 Mate 导致旋转锁死 | `lock_rotation=True` 默认会锁；运动模型必须 `lock_rotation=False` |
| 齿轮 Mate 不联动 | 齿数比传 0 / 两轴未先建同心 Mate / 一边组件被固定/锁旋转 |
| `add_component` 加件后位置错位 | 直接传米单位 `(x,y,z)`；后续用 `apply_component_transform_x` 调整 |

### 9.4 工程图 / 导出
| 现象 | 修复 |
|---|---|
| `Create3rdAngleViews2` 失败 | 需先有空白 `.slddrw` 文档，并保证 `part_path` 已落盘 |
| PDF 导出文件大小为 0 | `GetExportFileData(1)` 必须先调用并 `SetSheets(0, names)`；检查 `errors.value` |
| STL 太粗糙 | 调 `SetUserPreferenceIntegerValue(78, 0=fine)`；或自己写 `IExportStlData.SetUnits/SetQuality` |
| 中文版工程图标注乱码 | 模板的字体 / 视图比例为 `(1,1/scale)`，且确认零件 SaveAs 生成的工程图引用相同 part_path |

### 9.5 Motion Study
| 现象 | 修复 |
|---|---|
| `CreateMotionStudy` 当成属性返回 None | 调用 `ensure_motion_type_library()`；用 `motion_member` 兼容属性/方法 |
| `Calculate` 不动 | 检查叶轮/转子是否被 `Fix`、同心 Mate 是否锁旋转、是否被冗余 Mate 过约束 |
| 马达 LoadReferences 设置失败 | 用 Skill 的四层 VARIANT 兜底（tuple/list/VT_VARIANT/VT_DISPATCH）；确认引用是装配体上下文 IFace2 |
| Motion 许可证缺失 | Basic Motion 自带；Motion Analysis 需 SolidWorks Premium / Simulation 加载项 |

### 9.6 自审查
| 现象 | 修复 |
|---|---|
| `previews_blank=true` | 模型为空 / 只在草图状态 / 视图未缩放：先 `ForceRebuild3 + ViewZoomtofit2 + ShowNamedView2` |
| `expected_outputs_missing` | 检查 SaveAs 路径权限、扩展名、是否被 SolidWorks 报错忽略；查看 `errors.value` |
| BMP 文件 < 10KB | SaveBMP 失败或图形窗口被遮挡：保证 SolidWorks 可见、最小尺寸；重试 |

---

> 该笔记尽量按 Skill 源码（v 2026-06）原貌整理；当 SolidWorks 升级或 Skill 仓库迭代后，建议重新拉取并对照 `references/troubleshooting.md` 与 `references/api-lookup.md` 做校验。
