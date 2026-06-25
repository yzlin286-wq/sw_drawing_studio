# SolidWorks COM API 探针运行日志

- 时间：2026-06-18 16:42:49
- SW 连接：GetActiveObject fallback (gencache failed: This COM object can not automate the makepy process - please run makepy manually for this object)
- 文档：ActiveDoc reused
- 写入模式：off (只读)

## 统计
- total: 83; pass: 48; fail: 9; skip: 26

## 按分组
- **01_ISldWorks** — total 12 / pass 10 / fail 2 / skip 0
- **02_IModelDoc2** — total 11 / pass 9 / fail 2 / skip 0
- **03_IPartDoc** — total 10 / pass 5 / fail 3 / skip 2
- **04_IAssemblyDoc** — total 1 / pass 0 / fail 0 / skip 1
- **05_IDrawingDoc** — total 1 / pass 0 / fail 0 / skip 1
- **06_ISketchManager** — total 10 / pass 3 / fail 0 / skip 7
- **07_IFeatureManager** — total 2 / pass 1 / fail 1 / skip 0
- **08_IComponent2** — total 1 / pass 0 / fail 0 / skip 1
- **09_IConfiguration** — total 10 / pass 7 / fail 0 / skip 3
- **10_ICustomPropertyManager** — total 9 / pass 6 / fail 0 / skip 3
- **11_IModelDocExtension** — total 9 / pass 5 / fail 1 / skip 3
- **12_ILayerMgr** — total 1 / pass 0 / fail 0 / skip 1
- **13_IMassProperty** — total 1 / pass 0 / fail 0 / skip 1
- **14_Export_SaveAs** — total 5 / pass 2 / fail 0 / skip 3

## 全部条目（截断 summary）

| group | name | status | summary | error |
|---|---|---|---|---|
| 01_ISldWorks | RevisionNumber | pass | '33.5.0' |  |
| 01_ISldWorks | Visible | pass | True |  |
| 01_ISldWorks | FrameLeft | pass | 0 |  |
| 01_ISldWorks | FrameWidth | pass | 2048 |  |
| 01_ISldWorks | ActiveDoc(ref) | pass | 'CDispatch' |  |
| 01_ISldWorks | EnumDocuments2 | fail |  | com_error: (-2147352567, '发生意外。', (61836, 'SOLIDWORKS', '无法读只写属性。', 'C:\\PROGRA~ |
| 01_ISldWorks | GetUserPreferenceDoubleValue(89) | pass | 0.0 |  |
| 01_ISldWorks | GetUserPreferenceIntegerValue(0) | pass | 3 |  |
| 01_ISldWorks | GetUserPreferenceToggle(0) | pass | True |  |
| 01_ISldWorks | GetCurrentLanguage | pass | 'chinese-simplified' |  |
| 01_ISldWorks | GetExecutablePath | pass | 'C:\\PROGRA~1\\SOLIDW~1\\SOLIDW~1' |  |
| 01_ISldWorks | GetMathUtility | fail |  | com_error: (-2147352573, '找不到成员。', None, None) |
| 02_IModelDoc2 | GetType | pass | 1 |  |
| 02_IModelDoc2 | GetTitle | pass | 'LB26001-A-04-001.SLDPRT' |  |
| 02_IModelDoc2 | GetPathName | pass | 'C:\\Users\\Vision\\Desktop\\SW 相关\\3D转2D测试图纸\\LB26001-A-04-001.SLDPRT' |  |
| 02_IModelDoc2 | Extension | pass | 'CDispatch' |  |
| 02_IModelDoc2 | GetActiveConfiguration | fail |  | com_error: (-2147352573, '找不到成员。', None, None) |
| 02_IModelDoc2 | FeatureManager | pass | 'CDispatch' |  |
| 02_IModelDoc2 | SketchManager | pass | 'CDispatch' |  |
| 02_IModelDoc2 | ConfigurationManager | pass | 'CDispatch' |  |
| 02_IModelDoc2 | GetEquationMgr | fail |  | com_error: (-2147352573, '找不到成员。', None, None) |
| 02_IModelDoc2 | ClearSelection2(True) | pass | True |  |
| 02_IModelDoc2 | EditRebuild3 | pass | True |  |
| 03_IPartDoc | GetBodies2(any, visible_only) | pass | 1 |  |
| 03_IPartDoc | EnumBodies3 | fail |  | com_error: (-2147352567, '发生意外。', (61836, 'SOLIDWORKS', '无法读只写属性。', 'C:\\PROGRA~ |
| 03_IPartDoc | MaterialIdName | pass | '材料库/防静电研磨黑纤/502' |  |
| 03_IPartDoc | GetPartBox | pass | '(-0.25000000000000006, -0.000593576801498424, -0.15499999999999997, 0.250000000 |  |
| 03_IPartDoc | FirstFeature | fail |  | com_error: (-2147352573, '找不到成员。', None, None) |
| 03_IPartDoc | FeatureByName('Sketch1') | pass | None |  |
| 03_IPartDoc | IsWeldment | pass | False |  |
| 03_IPartDoc | Extension.IsSheetMetal | fail |  | AttributeError: <unknown>.IsSheetMetal |
| 03_IPartDoc | ExportToDWG2(skip_unless_write) | skip |  |  |
| 03_IPartDoc | MirrorPart3(skip_unless_write) | skip |  |  |
| 04_IAssemblyDoc | (not_assembly) | skip |  |  |
| 05_IDrawingDoc | (not_drawing) | skip |  |  |
| 06_ISketchManager | ActiveSketch(read) | pass | True |  |
| 06_ISketchManager | AddToDB(read) | pass | False |  |
| 06_ISketchManager | DisplayWhenAdded(read) | pass | True |  |
| 06_ISketchManager | InsertSketch(skip) | skip |  |  |
| 06_ISketchManager | Insert3DSketch(skip) | skip |  |  |
| 06_ISketchManager | CreateLine(skip) | skip |  |  |
| 06_ISketchManager | CreateCircle(skip) | skip |  |  |
| 06_ISketchManager | CreateCornerRectangle(skip) | skip |  |  |
| 06_ISketchManager | CreateSpline(skip) | skip |  |  |
| 06_ISketchManager | CreateCenterLine(skip) | skip |  |  |
| 07_IFeatureManager | FeatureManager(ref) | pass | 'CDispatch' |  |
| 07_IFeatureManager | (group_crash:07_IFeatureManager) | fail |  | com_error: (-2147352573, '找不到成员。', None, None) |
| 08_IComponent2 | (not_assembly) | skip |  |  |
| 09_IConfiguration | ConfigurationManager.ActiveConfiguration | pass | True |  |
| 09_IConfiguration | IModelDoc2.GetConfigurationNames | pass | ['默认'] |  |
| 09_IConfiguration | Configuration.Name | pass | '默认' |  |
| 09_IConfiguration | Configuration.Description | pass | '默认' |  |
| 09_IConfiguration | Configuration.Comment | pass | '' |  |
| 09_IConfiguration | Configuration.AlternateName | pass | '' |  |
| 09_IConfiguration | Configuration.GetParameters(skip) | skip |  |  |
| 09_IConfiguration | Configuration.CustomPropertyManager | pass | 'CDispatch' |  |
| 09_IConfiguration | AddConfiguration2(skip) | skip |  |  |
| 09_IConfiguration | ShowConfiguration2(skip) | skip |  |  |
| 10_ICustomPropertyManager | CustomPropertyManager('').Count | pass | 43 |  |
| 10_ICustomPropertyManager | CustomPropertyManager('').GetNames | pass | ['Description', 'Weight', 'Material', '质量', '材料', '单重', '零件号', '设计', '审核', '标准审查 |  |
| 10_ICustomPropertyManager | CustomPropertyManager('').LinkAll(read) | pass | True |  |
| 10_ICustomPropertyManager | CustomProp.Get(Description) | pass | 'all_methods_failed' |  |
| 10_ICustomPropertyManager | CustomProp.Get(Material) | pass | 'all_methods_failed' |  |
| 10_ICustomPropertyManager | GetType2('Description') | pass | 30 |  |
| 10_ICustomPropertyManager | Add3(skip) | skip |  |  |
| 10_ICustomPropertyManager | Set2(skip) | skip |  |  |
| 10_ICustomPropertyManager | Delete2(skip) | skip |  |  |
| 11_IModelDocExtension | Extension.MassProperty(read) | pass | 'str' |  |
| 11_IModelDocExtension | Extension.SelectionManager(read) | pass | 'str' |  |
| 11_IModelDocExtension | Extension.LayerMgr(read) | pass | 'str' |  |
| 11_IModelDocExtension | Extension.Document(==model) | pass | True |  |
| 11_IModelDocExtension | Extension.IsSheetMetal | fail |  | AttributeError: <unknown>.IsSheetMetal |
| 11_IModelDocExtension | Extension.RunCommand(skip) | skip |  |  |
| 11_IModelDocExtension | Extension.SaveAs3(skip) | skip |  |  |
| 11_IModelDocExtension | Extension.MultiSelect2(skip) | skip |  |  |
| 11_IModelDocExtension | Extension.Rebuild(0) | pass | True |  |
| 12_ILayerMgr | (not_drawing) | skip |  |  |
| 13_IMassProperty | Extension.MassProperty is None | skip |  |  |
| 14_Export_SaveAs | IExportPdfData = sw.GetExportFileData(1) | pass | 'CDispatch' |  |
| 14_Export_SaveAs | ExtraSaveAs3(skip_unless_write) | skip |  |  |
| 14_Export_SaveAs | Save3(skip_unless_write) | skip |  |  |
| 14_Export_SaveAs | ExportToDWG2(skip_unless_write) | skip |  |  |
| 14_Export_SaveAs | BuildAdvancedSaveAsOptions(read-only) | pass | 'NoneType' |  |
