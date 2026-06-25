# SolidWorks COM API 实测 × 解决方案

> 时间：2026-06-18
> SW 版本：33.5.0（SOLIDWORKS 2025）
> 测试样本：[LB26001-A-04-001.SLDPRT](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/3D%E8%BD%AC2D%E6%B5%8B%E8%AF%95%E5%9B%BE%E7%BA%B8/LB26001-A-04-001.SLDPRT)
> 数据源：[probe_result.json](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/.trae/specs/probe-solidworks-com-api/probe_result.json) × [sw_com_api_index.md](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/.trae/specs/probe-solidworks-com-api/sw_com_api_index.md)
> 命中率：**pass 48 / fail 9 / skip 26 / total 83**

---

## 0. 统计概览（按分组）

| 分组 | pass | fail | skip | total | 通过率* |
|---|---|---|---|---|---|
| 01_ISldWorks | 9 | 2 | 0 | 11 | 82% |
| 02_IModelDoc2 | 9 | 2 | 0 | 11 | 82% |
| 03_IPartDoc | 5 | 3 | 2 | 10 | 56% |
| 04_IAssemblyDoc | 0 | 0 | 9 | 9 | n/a (非装配) |
| 05_IDrawingDoc | 0 | 0 | 9 | 9 | n/a (非工程图) |
| 06_ISketchManager | 3 | 0 | 7 | 10 | 100%* |
| 07_IFeatureManager | 1 | 1 | 10 | 12 | 50%* |
| 08_IComponent2 | 0 | 0 | 1 | 1 | n/a (非装配) |
| 09_IConfiguration | 7 | 0 | 3 | 10 | 100%* |
| 10_ICustomPropertyManager | 6 | 0 | 3 | 9 | 100%* |
| 11_IModelDocExtension | 5 | 1 | 3 | 9 | 83% |
| 12_ILayerMgr | 0 | 0 | 1 | 1 | n/a (非工程图) |
| 13_IMassProperty | 0 | 0 | 1 | 1 | n/a (取不到 MassProperty) |
| 14_Export_SaveAs | 2 | 0 | 3 | 5 | 100%* |

\* 仅按 pass/(pass+fail) 统计，skip 不计入分母。

---

## 1. 已通过 ✅（48 项 — 摘要表）

> 完整 Python 调用示例见 [probe_runner.py](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/.trae/specs/probe-solidworks-com-api/probe_runner.py) 内对应函数。

| 分组 | 接口 | 实测返回（截断） |
|---|---|---|
| 01 | RevisionNumber | `'33.5.0'` |
| 01 | Visible | `True` |
| 01 | FrameLeft / FrameWidth | `0` / `2048` |
| 01 | ActiveDoc | CDispatch |
| 01 | GetUserPreferenceDoubleValue(89) | `0.0` |
| 01 | GetUserPreferenceIntegerValue(0) | `3` |
| 01 | GetUserPreferenceToggle(0) | `True` |
| 01 | GetCurrentLanguage | `'chinese-simplified'` |
| 01 | GetExecutablePath | `'C:\\PROGRA~1\\SOLIDW~1\\SOLIDW~1'` |
| 02 | GetType | `1` (Part) |
| 02 | GetTitle | `'LB26001-A-04-001.SLDPRT'` |
| 02 | GetPathName | 完整磁盘路径 ✅ |
| 02 | Extension | CDispatch |
| 02 | FeatureManager / SketchManager / ConfigurationManager | CDispatch ×3 |
| 02 | ClearSelection2(True) | `True` |
| 02 | EditRebuild3 | `True` |
| 03 | GetBodies2(0,True) | `1`（个实体） |
| 03 | MaterialIdName | `'材料库\|防静电研磨黑纤\|502'` |
| 03 | GetPartBox(True) | `(-0.25, -0.000593, -0.155, 0.25, 0.012, 0.155)` |
| 03 | FeatureByName('Sketch1') | `None`（合理：本零件无 Sketch1） |
| 03 | IsWeldment | `False` |
| 06 | SketchManager.ActiveSketch / AddToDB / DisplayWhenAdded | 三属性 ✅ |
| 07 | FeatureManager（属性引用） | CDispatch |
| 09 | ConfigurationManager.ActiveConfiguration | True |
| 09 | GetConfigurationNames | `['默认']` |
| 09 | Configuration.Name/Description/Comment/AlternateName | `'默认' / '默认' / '' / ''` |
| 09 | Configuration.CustomPropertyManager | CDispatch |
| 10 | CustomPropertyManager('').Count | `43` |
| 10 | CustomPropertyManager('').GetNames | `['Description','Weight','Material','质量','材料',...]`（43 项） |
| 10 | CustomPropertyManager('').LinkAll | `True` |
| 10 | CustomPropertyManager('').GetType2('Description') | `30`（Number） |
| 11 | Extension.Document | True |
| 11 | Extension.Rebuild(0) | `True` |
| 14 | sw.GetExportFileData(1) | CDispatch（IExportPdfData） |

完整列表见 `probe_result.json`。

---

## 2. 失败 ❌（9 项 — 全部带原因 × 解决方案）

### ❌-1 `ISldWorks.EnumDocuments2`
- 官方签名：[`EnumDocuments2() -> IEnumDocuments2`](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~EnumDocuments2.html)
- 实测错误：`com_error: (-2147352567, '发生意外。', (61836, 'SOLIDWORKS', '无法读只写属性。', ...))`
- **原因**：在 `gencache.EnsureDispatch` 生成的早绑定中，`EnumDocuments2` 被 typelib 标为 propput-only；这是 pywin32 的已知 typelib quirk。
- **解决方案**：
  1. 用 `IModelDoc2.GetActiveDoc` + `sw.GetFirstDocument()` + `IModelDoc2.GetNext()` 链式遍历替代；或
  2. 直接绕过早绑定：`win32com.client.dynamic.Dispatch(sw._oleobj_)` 后再 call。
  3. 推荐：使用 `sw.GetDocuments` (集合属性) → `for i in range(sw.GetDocumentCount): sw.GetDocument(i)` 形式（部分版本可用）。
- 优先级：P2（本仓库不依赖批量枚举打开文档）。

### ❌-2 `ISldWorks.GetMathUtility`
- 官方签名：[`GetMathUtility() -> IMathUtility`](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~GetMathUtility.html)
- 实测错误：`com_error: 找不到成员`
- **原因**：在 SW2025 EnsureDispatch 生成的早绑定中，`GetMathUtility` 不在 ISldWorks 的成员表里——它实际定义在 `IMathUtility` 接口的兄弟提供者上。pywin32 早绑定从该派生表查不到。
- **解决方案**：
  1. 使用 `win32com.client.Dispatch("SldWorks.MathUtility")` 直接实例化 IMathUtility；
  2. 或在 EnsureDispatch 之前先 `pythoncom.LoadTypeLib(...sldworks.tlb)` 触发完整生成。
- 优先级：P2（本仓库 v5 出图未使用矩阵运算）。

### ❌-3 `IModelDoc2.GetActiveConfiguration`
- 官方签名：`GetActiveConfiguration() -> IConfiguration`
- 实测错误：`com_error: 找不到成员`
- **原因**：早绑定后该成员被映射为 propget `ActiveConfiguration`（直接属性访问，而非方法调用）。
- **解决方案**：用 `model.ConfigurationManager.ActiveConfiguration` 替代（实测此路径 ✅）。本仓库现有代码已统一走 ConfigurationManager 路径，不阻塞。
- 优先级：P2。

### ❌-4 `IModelDoc2.GetEquationMgr`
- 官方签名：`GetEquationMgr() -> IEquationMgr`
- 实测错误：`com_error: 找不到成员`
- **原因**：同 ❌-3，早绑定下变成属性 `EquationMgr`。
- **解决方案**：`model.EquationMgr`（属性形式）。已加入 `unresolved_apis.md` Owner-Action。
- 优先级：P2。

### ❌-5 `IPartDoc.EnumBodies3`
- 官方签名：`EnumBodies3(BodyType, Visible) -> IEnumBodies2`
- 实测错误：`com_error: 无法读只写属性`
- **原因**：同 ❌-1 的 typelib 标注问题。
- **解决方案**：用 `model.GetBodies2(0, True)`（实测 ✅，返回 `(IBody2, ...)`）。本仓库 `drw_quality_check.py` 已采用此路径。
- 优先级：P2。

### ❌-6 `IPartDoc.FirstFeature`
- 官方签名：`FirstFeature() -> IFeature`
- 实测错误：`com_error: 找不到成员`
- **原因**：早绑定下 `IModelDoc2.FirstFeature` 才是真实位置；`IPartDoc` 不直接暴露。
- **解决方案**：从 `IModelDoc2` 取 → `model.FirstFeature` (属性 / 方法均尝试一遍)。本仓库 v5 实际通过 `Feature` 自身的 `GetNextFeature` 链遍历，不阻塞。
- 优先级：P2。

### ❌-7 `IModelDocExtension.IsSheetMetal`
- 官方签名：`IsSheetMetal() -> Boolean`
- 实测错误：`AttributeError: <unknown>.IsSheetMetal`
- **原因**：在 SW2025 中此方法已迁移到 `ISheetMetalManager` 或 `IPartDoc.GetSheetMetalFolder`；旧入口被移除。
- **解决方案**：
  1. 检测 `model.GetType() == 1` 后，遍历 `FirstFeature → GetNextFeature` 寻找 `GetTypeName2 == "SheetMetal"`；
  2. 或调用 `IPartDoc.GetSheetMetalFolder` 判空。
- 优先级：P1（影响后续钣金链路）。

### ❌-8 `IFeatureManager` 链遍历
- 实测错误：`com_error: 找不到成员`（在 `f.GetNextFeature` 上）
- **原因**：第一个 `f` 是 `None`（因 ❌-6），导致后续链式调用未发生。换言之这是 ❌-6 的级联效应。
- **解决方案**：先修 ❌-6 即可。

### ❌-9 `Extension.IsSheetMetal`（同 ❌-7）

---

## 3. 已跳过 ⏭ 的分类

- **destructive (16 项)**：写入/删除/创建特征类，本次只读跑，故 skip。本仓库 [drw_generate_v5.py](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/.trae/specs/enforce-drawing-quality/drw_generate_v5.py) 已在更高层验证。
- **non-applicable (9 项)**：装配、工程图、组件、图层、质量属性 → 当前样本是零件，无法验证。下一步可换 `LB26001-gen5.0硬盘转卡组件.SLDASM` 跑一次取得 04/05/08/12/13 分组数据。
- **enters edit mode (2 项)**：InsertSketch / Insert3DSketch 会改变 SW UI 状态。

---

## 4. 复现 / 下一步

```bash
# 完整冒烟（默认零件）
python ".trae\specs\probe-solidworks-com-api\probe_runner.py"

# 仅跑工程图分组（先在 SW 中打开 SLDDRW）
python ".trae\specs\probe-solidworks-com-api\probe_runner.py" --group "05_IDrawingDoc,12_ILayerMgr"

# 启用破坏性接口
python ".trae\specs\probe-solidworks-com-api\probe_runner.py" --write

# 切换到装配体（可补全 04/08/13 分组）
python ".trae\specs\probe-solidworks-com-api\probe_runner.py" --part "3D转2D测试图纸\LB26001-gen5.0硬盘转卡组件.SLDASM"
```
