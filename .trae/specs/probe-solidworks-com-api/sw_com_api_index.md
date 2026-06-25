# SolidWorks COM API Index — 官方文档抽取

> 来源：SolidWorks API Help (2024/English)
> 命名空间：[SolidWorks.Interop.sldworks](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks_namespace.html)
> 抽取范围：与本仓库"3D→2D 出图 + GB QC + 装配/配置/钣金"目标直接相关的 14 个核心接口
> 说明：每个分组列出 ≥10 个核心方法/属性的官方签名与 Help URL 锚点。Help URL 模板为
> `https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.<Interface>~<Member>.html`

---

## 1. ISldWorks（应用级根接口）
URL：[ISldWorks](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks.html)

| # | 签名 | 说明 |
|---|---|---|
| 1 | `OpenDoc6(FileName: BSTR, Type: Long, Options: Long, Configuration: BSTR, Errors: Long*, Warnings: Long*) -> ModelDoc2` | 打开零件/装配/工程图（推荐 OpenDoc7 IDocumentSpecification 链） |
| 2 | `OpenDoc7(IDocumentSpecification) -> ModelDoc2` | 推荐方式 |
| 3 | `ActiveDoc -> ModelDoc2` | 当前活动文档 |
| 4 | `ActivateDoc3(Name, UseUserPreferences, Option, Errors) -> ModelDoc2` | 切换活动文档 |
| 5 | `CloseDoc(Name)` | 关闭文档（不保存） |
| 6 | `CloseAllDocuments(IncludeUnsaved) -> Boolean` | 关闭全部 |
| 7 | `NewDocument(TemplateName, PaperSize, Width, Height) -> ModelDoc2` | 按模板新建 |
| 8 | `GetUserPreferenceDoubleValue(Id) -> Double` / `SetUserPreferenceDoubleValue(Id, Value)` | 用户首选项浮点 |
| 9 | `GetUserPreferenceIntegerValue / SetUserPreferenceIntegerValue` | 整型 |
| 10 | `GetUserPreferenceToggle / SetUserPreferenceToggle` | 布尔 |
| 11 | `RevisionNumber() -> BSTR` | SW 版本（如 33.5.0） |
| 12 | `Visible -> Boolean` | 显示/隐藏 SW |
| 13 | `FrameLeft / FrameTop / FrameWidth / FrameHeight` | 主窗口几何 |
| 14 | `EnumDocuments2() -> IEnumDocuments2` | 枚举所有打开的文档 |
| 15 | `ExitApp()` | 退出 SW |
| 16 | `LoadFile4(FileName, Args, ImportData, Errors)` | 导入 STEP/IGES 等 |

---

## 2. IModelDoc2（文档基类）
URL：[IModelDoc2](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDoc2.html)

| # | 签名 | 说明 |
|---|---|---|
| 1 | `GetType() -> Long`（1=Part, 2=Assembly, 3=Drawing） | 文档类型 |
| 2 | `GetTitle() -> BSTR` / `GetPathName() -> BSTR` | 标题与磁盘路径 |
| 3 | `Save() / Save3(Options, Errors, Warnings) -> Boolean` | 原地保存 |
| 4 | `SaveAs / SaveAs2 / SaveAs3 / SaveAs4` | 另存（PDF/DXF/STEP 等通过扩展名识别） |
| 5 | `Extension -> IModelDocExtension` | 扩展接口（建议优先使用） |
| 6 | `ClearSelection2(IncludeAllSubSelections)` | 清选择 |
| 7 | `SelectByID2(Name, Type, X, Y, Z, Append, Mark, Callout, SelectOption) -> Boolean` | 按名称/坐标选择 |
| 8 | `EditRebuild3() -> Boolean` | 重建模型 |
| 9 | `ForceRebuild3(IncludeTopOnly) -> Boolean` | 强制重建 |
| 10 | `GetActiveConfiguration() -> Configuration` | 当前配置 |
| 11 | `GetEquationMgr() -> IEquationMgr` | 方程式管理器 |
| 12 | `FeatureManager -> IFeatureManager` | 特征管理器 |
| 13 | `SketchManager -> ISketchManager` | 草图管理器 |
| 14 | `ConfigurationManager -> IConfigurationManager` | 配置管理器 |
| 15 | `CustomInfo / CustomInfo2 / CustomInfo3` | 自定义属性（弱方式） |
| 16 | `Summary / Title / Subject / Author / Keywords / Comments` | 文档摘要 |

---

## 3. IPartDoc（零件文档）
URL：[IPartDoc](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IPartDoc.html)

| # | 签名 | 说明 |
|---|---|---|
| 1 | `GetBodies2(BodyType, Visible) -> Variant(IBody2[])` | 获取实体 |
| 2 | `EnumBodies3(BodyType, Visible) -> IEnumBodies2` | 枚举实体 |
| 3 | `MaterialIdName -> BSTR` / `SetMaterialPropertyName2` | 材料 |
| 4 | `CreateNewBodyFolder(Type, Name, RetainAttachedBody) -> IFeature` | 新建实体文件夹 |
| 5 | `ExportToDWG2(FileName, ...) -> Boolean` | 导出 DWG/DXF |
| 6 | `MirrorPart3(MirrorPlane, BodyOptions) -> Boolean` | 镜像零件 |
| 7 | `GetPartBox(UseSystem) -> Variant(double[6])` | 包围盒 |
| 8 | `FeatureByName(Name) -> IFeature` | 按名取特征 |
| 9 | `FirstFeature() -> IFeature` | 第一个特征 |
| 10 | `IsWeldment() -> Boolean` | 是否焊件 |
| 11 | `GetSelectedFeatureType() -> Long` | 选中特征类型 |
| 12 | `IsSheetMetal() -> Boolean` | 是否钣金（注意：SW2025 改为 `Extension.IsSheetMetal`） |

---

## 4. IAssemblyDoc（装配文档）
URL：[IAssemblyDoc](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IAssemblyDoc.html)

| # | 签名 | 说明 |
|---|---|---|
| 1 | `AddComponent5(CompName, ConfigOption, ConfigName, UseCenterOfMass, NewName, X, Y, Z) -> IComponent2` | 加入组件 |
| 2 | `AddMate5(...) -> IFeature` / `AddMate3` | 配合（多个签名） |
| 3 | `GetComponents(TopLevelOnly) -> Variant(IComponent2[])` | 全组件 |
| 4 | `GetComponentByName(Name) -> IComponent2` | 按名取 |
| 5 | `MoveComponent / DragOperator2` | 移动 |
| 6 | `EditAssembly() / EditPart()` | 装配/零件编辑 |
| 7 | `ExpandAllConnectors / CollapseAllConnectors` | 展开收起 |
| 8 | `ResolveAllLightWeightComponents(Prompt)` | 解压所有 |
| 9 | `IsLightWeight() -> Boolean` | 是否轻量化 |
| 10 | `ExplodeView() / Explode()` | 爆炸图 |
| 11 | `ToolsCheckInterference2(Components) -> Variant` | 干涉检查 |
| 12 | `GetClearanceVerificationMgr() -> IClearanceVerificationMgr` | 间隙检查 |

---

## 5. IDrawingDoc（工程图文档）
URL：[IDrawingDoc](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDrawingDoc.html)

| # | 签名 | 说明 |
|---|---|---|
| 1 | `Create3rdAngleViews2(ModelName) / Create1stAngleViews2(ModelName) -> Boolean` | 三视图（投影法决定第一/三角） |
| 2 | `CreateDrawViewFromModelView3(ModelName, ViewName, X, Y, Z) -> IView` | 单视图 |
| 3 | `CreateSectionViewAt5(X, Y, Z, ViewName, Options, ExcludedComps, ExcludedSubAssyComps) -> IView` | 剖视图 |
| 4 | `InsertModelInPredefinedView(ModelName) -> IView` | 预定义视图填充 |
| 5 | `ActivateView(ViewName) -> Boolean` / `GetCurrentSheet() -> ISheet` | 激活视图 / 当前图纸 |
| 6 | `GetSheetNames() -> Variant(string[])` / `ActivateSheet(Name)` | 图纸枚举/切换 |
| 7 | `NewSheet4(...) -> Boolean` | 新建图纸 |
| 8 | `SetupSheet5(Name, PaperSize, TemplateIn, ScaleNum, ScaleDen, FirstAngle, TemplateName, Width, Height, PropertyViewName, ZonesShow) -> Boolean` | 图纸属性 |
| 9 | `EditTemplate() / EditSheet()` | 编辑模板/图纸 |
| 10 | `GetFirstView() -> IView` | 第一个视图（图纸格式视图） |
| 11 | `FeatureByName(Name) -> IFeature` | 按名取 |
| 12 | `InsertModelAnnotations3(Type, Options, AllViews, Process, IncludeChildren, IncludeFeatures, FeatTolType) -> Variant` | 模型尺寸自动标注 |
| 13 | `InsertCenterMark2(SelOption) -> ICenterMark` | 中心标记 |
| 14 | `InsertCenterLine2(SelOption) -> ICenterLine` | 中心线 |

---

## 6. ISketchManager
URL：[ISketchManager](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISketchManager.html)

| # | 签名 | 说明 |
|---|---|---|
| 1 | `InsertSketch(UpdateEditRebuild) -> Boolean` | 进入/退出草图 |
| 2 | `Insert3DSketch(ToggleEnd) -> Boolean` | 3D 草图 |
| 3 | `CreateLine(X1, Y1, Z1, X2, Y2, Z2) -> ISketchSegment` | 直线 |
| 4 | `CreateCornerRectangle(X1, Y1, Z1, X2, Y2, Z2) -> Variant(ISketchSegment[])` | 矩形 |
| 5 | `CreateCircle(Xc, Yc, Zc, Xp, Yp, Zp) -> ISketchSegment` | 圆 |
| 6 | `CreateArc(...)` | 圆弧 |
| 7 | `CreateSpline(Points) -> ISketchSegment` | 样条 |
| 8 | `CreateCenterLine(...)` | 中心线 |
| 9 | `CreatePoint(X, Y, Z) -> ISketchPoint` | 点 |
| 10 | `MakeSketchBlockFromFile(...) / InsertSketchBlockInstance(...)` | 块 |
| 11 | `AddToDB -> Boolean` / `DisplayWhenAdded -> Boolean` | 高速添加 |
| 12 | `ActiveSketch -> ISketch` | 当前草图 |

---

## 7. IFeatureManager
URL：[IFeatureManager](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeatureManager.html)

| # | 签名 | 说明 |
|---|---|---|
| 1 | `FeatureExtrusion3(...) / FeatureExtrusion2(...)` | 拉伸 |
| 2 | `FeatureCut4(...) / FeatureCut3(...)` | 拉伸切除 |
| 3 | `FeatureRevolve2(...)` | 旋转 |
| 4 | `FeatureFillet3(...)` | 倒圆角 |
| 5 | `FeatureChamfer(...)` | 倒角 |
| 6 | `InsertFeatureShell2(...) / Shell(...)` | 抽壳 |
| 7 | `FeatureRib(...)` | 加强筋 |
| 8 | `FeatureLinearPattern5(...) / FeatureCircularPattern5(...)` | 线性/圆周阵列 |
| 9 | `FeatureMirror2(...)` | 镜像 |
| 10 | `InsertSheetMetalBaseFlange2(...)` | 钣金基体法兰 |
| 11 | `EditFeature() / EditDefinition()` | 编辑特征 |
| 12 | `InsertReferencePlane2(...)` | 参考基准面 |

---

## 8. IComponent2
URL：[IComponent2](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IComponent2.html)

| # | 签名 | 说明 |
|---|---|---|
| 1 | `Name2 -> BSTR` / `Name -> BSTR` | 组件名 |
| 2 | `GetPathName() -> BSTR` | 文档路径 |
| 3 | `GetModelDoc2() -> ModelDoc2` | 取底层模型（卸载时返回 None） |
| 4 | `Visible -> Long` / `SetSuppression2(Action) -> Long` | 显示/抑制 |
| 5 | `Transform2 -> IMathTransform` | 变换矩阵 |
| 6 | `GetChildren() -> Variant(IComponent2[])` | 子组件 |
| 7 | `IsSuppressed() -> Boolean` | 是否抑制 |
| 8 | `IsRoot() -> Boolean` | 是否顶层 |
| 9 | `ReferencedConfiguration -> BSTR` | 引用配置 |
| 10 | `Solving -> Long`（0=Rigid, 1=Flexible） | 子装配求解模式 |
| 11 | `GetID() -> Long` | 组件 ID |
| 12 | `MakeVirtual()` | 虚拟化 |

---

## 9. IConfiguration / IConfigurationManager
URL：[IConfiguration](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IConfiguration.html)

| # | 签名 | 说明 |
|---|---|---|
| 1 | `IConfiguration.Name -> BSTR` | 配置名 |
| 2 | `IConfiguration.Description -> BSTR` | 描述 |
| 3 | `IConfiguration.Comment -> BSTR` | 备注 |
| 4 | `IConfiguration.AlternateName -> BSTR` | 显示名 |
| 5 | `IConfiguration.GetParameters() -> Variant` | 参数列表 |
| 6 | `IConfiguration.CustomPropertyManager -> ICustomPropertyManager` | 该配置的属性 |
| 7 | `IConfigurationManager.AddConfiguration2(...)` | 新建配置 |
| 8 | `IConfigurationManager.ActiveConfiguration -> IConfiguration` | 当前配置 |
| 9 | `IConfigurationManager.GetConfigurationNames() -> Variant` | 名称列表 |
| 10 | `IConfigurationManager.LinkDisplayStateToConfiguration -> Boolean` | 显示状态绑定 |
| 11 | `IModelDoc2.ShowConfiguration2(Name) -> Boolean` | 切换 |
| 12 | `IModelDoc2.AddConfiguration3(...)` | 历史 API |

---

## 10. ICustomPropertyManager
URL：[ICustomPropertyManager](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ICustomPropertyManager.html)

| # | 签名 | 说明 |
|---|---|---|
| 1 | `Add3(FieldName, FieldType, FieldValue, OverwriteExisting) -> Long` | 新增 |
| 2 | `Set2(FieldName, FieldValue) -> Long` | 设置 |
| 3 | `Get4(FieldName, UseCached, ValueOut, ResolvedValueOut, WasResolved, LinkToProperty) -> Long` | 读取（推荐） |
| 4 | `Get5 / Get6` | 更新签名（2021+） |
| 5 | `Delete2(FieldName) -> Long` | 删除 |
| 6 | `GetNames() -> Variant(string[])` | 名称列表 |
| 7 | `GetType2(FieldName) -> Long`（0=String, 30=Number...） | 类型 |
| 8 | `Count -> Long` | 数量 |
| 9 | `Owner -> Object` | 宿主 |
| 10 | `LinkAll -> Boolean` | 是否全部链接 |

---

## 11. IModelDocExtension
URL：[IModelDocExtension](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDocExtension.html)

| # | 签名 | 说明 |
|---|---|---|
| 1 | `SaveAs / SaveAs3(Name, Version, Options, ExportData, AdvancedSaveAsOptions, Errors, Warnings) -> Boolean` | 推荐 SaveAs |
| 2 | `RunCommand(Command, Title) -> Boolean` | 触发菜单命令 |
| 3 | `CustomPropertyManager(ConfigName) -> ICustomPropertyManager` | 取属性管理器 |
| 4 | `MassProperty -> IMassProperty` / `GetMassProperties2(Accuracy, Status) -> Variant` | 质量属性 |
| 5 | `GeneralPostponeFeatureManagerNotifications(Postpone) -> Boolean` | 推迟通知 |
| 6 | `SelectByID2(...)` / `MultiSelect2(...)` | 选择 |
| 7 | `SelectionManager -> ISelectionMgr` | 选择管理器 |
| 8 | `GetLinesFontStyle / SetLinesFontStyle` | 线型 |
| 9 | `LayerMgr -> ILayerMgr` | 图层 |
| 10 | `Document -> IModelDoc2` | 反向取根 |
| 11 | `IsSheetMetal() -> Boolean` | 是否钣金 |
| 12 | `Rebuild(Options) -> Boolean` | 重建 |

---

## 12. ILayerMgr / ILayer
URL：[ILayerMgr](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ILayerMgr.html)

| # | 签名 | 说明 |
|---|---|---|
| 1 | `AddLayer(Name, Description, Color, Style, Width) -> Long`（Width: 0~12） | 新增图层 |
| 2 | `DeleteLayer(Name) -> Long` | 删除 |
| 3 | `GetLayer(Name) -> ILayer` | 取图层 |
| 4 | `GetLayerCount() -> Long` | 数量 |
| 5 | `GetLayerList() -> Variant(string[])` | 名称列表 |
| 6 | `IsLayerPresent(Name) -> Boolean` | 是否存在 |
| 7 | `ILayer.Color -> Long` / `Visible -> Boolean` / `Printable -> Boolean` | 颜色/可见/打印 |
| 8 | `ILayer.Style -> Long` | 线型 |
| 9 | `ILayer.Width -> Long` | 线宽 |
| 10 | `ILayer.OnOff -> Boolean` | 启用 |

---

## 13. IMassProperty
URL：[IMassProperty](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IMassProperty.html)

| # | 签名 | 说明 |
|---|---|---|
| 1 | `Mass -> Double` | 质量 (kg) |
| 2 | `Volume -> Double` | 体积 (m³) |
| 3 | `SurfaceArea -> Double` | 表面积 |
| 4 | `Density -> Double` | 密度 |
| 5 | `CenterOfMass -> Variant(double[3])` | 质心 |
| 6 | `PrincipalAxesOfInertia -> Variant` | 惯性主轴 |
| 7 | `PrincipalMomentsOfInertia -> Variant` | 惯性矩 |
| 8 | `Accuracy -> Double` | 精度 |
| 9 | `OverrideMass / OverrideCenterOfMass / OverrideMomentsOfInertia` | 覆盖项 |
| 10 | `IncludeHiddenBodiesOrComponents -> Boolean` | 是否含隐藏体 |

---

## 14. 文件导出 SaveAs / IExportPdfData / SaveAsType
统一入口：[IModelDocExtension.SaveAs3](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDocExtension~SaveAs3.html)

| # | 目标格式 | 推荐方法 / 关键参数 |
|---|---|---|
| 1 | SLDPRT/SLDASM/SLDDRW（原生） | `IModelDoc2.Save3(Options, Errors, Warnings)` |
| 2 | PDF（工程图多页） | `IExportPdfData.SetSheets(swExportData_ExportSpecifiedSheets, sheetNames)` + `IModelDocExtension.SaveAs3(filename, version=0, options=0, ExportData=pdfData, ...)` |
| 3 | DXF / DWG（工程图或钣金展开） | `IPartDoc.ExportToDWG2(...)` 或 `SaveAs3` 后缀 .dxf/.dwg |
| 4 | STEP203 / STEP214 / STEP242 | `SaveAs3` + 用户首选项 `swStepAP=...` |
| 5 | IGES | `SaveAs3` + `.igs` |
| 6 | Parasolid | `.x_t / .x_b` |
| 7 | STL | `SaveAs3` + `.stl`；分辨率经 user pref `swSTLQuality_Coarse/Fine` |
| 8 | eDrawings | `.eprt / .easm / .edrw` |
| 9 | PNG / JPG / BMP | `IModelDoc2.SaveBMP(filename, w, h)` 或 `IModelView.GetVisibleBox` + GDI；推荐 `IExportData_BMP` |
| 10 | 3D PDF | `IExportPdfData` 中 `Set3DPDFData(...)` |

---

## 跨分组通用枚举

| 名称 | 取值 | 出处 |
|---|---|---|
| `swDocumentTypes_e` | 1=Part, 2=Assembly, 3=Drawing | OpenDoc6 第二参数 |
| `swSaveAsVersion_e` | 0=Current, 1=SW_PreviousRelease | SaveAs |
| `swSaveAsOptions_e` | 1=SilentlyOverwriteExisting, 2=Copy, 4=AvoidRebuildOnSave, ... | SaveAs |
| `swSelectType_e` | "EXTSKETCHPOINT", "DRAWINGVIEW", "DIMENSION" 等字符串 | SelectByID2 |
| `swViewOrientation_e` | 1=Front, 2=Back, 3=Left, 4=Right, 5=Top, 6=Bottom, 7=Iso, 8=Trimetric, 9=Dimetric | 标准视图 |
| `swPaperSizes_e` | 0=A0, 6=A4, ...（数字编码与 SetupSheet5 配合） | 图纸幅面 |
| `swDrawingViewTypes_e` | 1=Model, 2=Section, 3=Detail, 4=Auxiliary, 5=Projection... | IView.Type |

---

## 注释

- **接口版本**：本仓库目标 SW 2025（Rev 33.5.0），上述签名对 SW2018+ 兼容；带数字后缀（OpenDoc6/Save3 等）的为现行推荐版本。
- **过时接口**：本索引刻意不收录已 Obsolete 项（如 `IComponent`、`IBody`、`IBlockDefinition`、`OpenDoc / OpenDoc2` 等）。
- **Help URL 模板**：`https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.<Interface>~<Member>.html`，可直接拼接锚点。
- **离线文档**：本地安装 SW 时通常包含 `C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\api\sldworks.tlb`，可用 OLE/COM Object Viewer 浏览全部签名作为兜底。
