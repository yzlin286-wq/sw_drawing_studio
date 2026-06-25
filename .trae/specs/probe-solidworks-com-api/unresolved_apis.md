# Unresolved APIs — 不可用接口清单与解决方案

> 时间：2026-06-18
> 来源：[sw_com_api_probe.md](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/.trae/specs/probe-solidworks-com-api/sw_com_api_probe.md) ❌ + 高风险 ⚠
> 目的：把所有"在 SW2025 + Python 3.11 + pywin32 EnsureDispatch 路径下不可直接调用"的接口集中归档，明确原因 / 替代路径 / 优先级。

---

## 桶 A. pywin32 marshaling / typelib quirk（4 条）

| ID | 接口 | 现象 | 解决方案 | 优先级 | Owner-Action |
|---|---|---|---|---|---|
| A-1 | `ISldWorks.EnumDocuments2` | `无法读只写属性` | 用 `IEnumDocuments2` 替代路径，或切换到 `dynamic.Dispatch` | P2 | 仅在批量遍历已打开文档时需要；本仓库不依赖 |
| A-2 | `IPartDoc.EnumBodies3` | `无法读只写属性` | 用 `model.GetBodies2(0, True)` 替代（已 ✅） | 已绕开 | `drw_quality_check.py` 已用 GetBodies2 |
| A-3 | `IConfiguration.GetParameters` | `非选择性的参数` | 多数版本要求传 BSTR 参数（参数名）才返回；空入参不可用 | P2 | 当需要参数表时，先通过 `Configuration.CustomPropertyManager.GetNames` 拿键再逐个 GetParameter |
| A-4 | `ICustomPropertyManager.Get4(name, False)` outparams | `非选择性的参数` | EnsureDispatch 后 outparams 不能直接接收；用 `Get6` 或自行包 `VARIANT(VT_BYREF\|VT_BSTR)` | P1 | 在 v5 写入流程修补：优先调用 `Get5/Get6`；对老 SW 调用 `Get4` 时把 outparams 用 win32com.client.VARIANT 包装 |

---

## 桶 B. 早绑定下"方法 ↔ 属性"映射错位（4 条）

> EnsureDispatch 会把无参 method 标成 propget，导致直接 `obj.Foo()` 抛 `'<type>' object is not callable`。

| ID | 接口 | 推荐替代 | 优先级 |
|---|---|---|---|
| B-1 | `IModelDoc2.GetActiveConfiguration` | 改用属性 `model.ConfigurationManager.ActiveConfiguration` | P2（已绕开） |
| B-2 | `IModelDoc2.GetEquationMgr` | 改用属性 `model.EquationMgr` | P2 |
| B-3 | `IPartDoc.FirstFeature` | 改用 `model.FirstFeature`（IModelDoc2 上的方法/属性双形态，需 `call_or_get` 兜底） | P2（probe_runner 已实现 helper） |
| B-4 | `ISldWorks.GetCurrentLanguage / GetExecutablePath` | 一律用 `call_or_get` 兜底 | P2（已实现） |

---

## 桶 C. SW 版本受限 / 接口已迁移（3 条）

| ID | 接口 | 原因 | 解决方案 | 优先级 |
|---|---|---|---|---|
| C-1 | `IModelDocExtension.IsSheetMetal` | SW2025 移除 / 迁移到 `ISheetMetalManager` | 1) 遍历特征找 `GetTypeName2 == "SheetMetal"`；2) `IPartDoc.GetSheetMetalFolder` 判空 | P1 |
| C-2 | `ISldWorks.GetMathUtility` | typelib 早绑定 派生表查不到（实际在 IMathUtility 接口的兄弟提供者） | 直接 `win32com.client.Dispatch("SldWorks.MathUtility")` | P2 |
| C-3 | `ISldWorks.GetExportFileData(2)`（swExportPngData） | SW2025 Rev 33.5.0 返回 None，不可用（2026-06-19 v1.5 spec Task 4 记录） | PNG 导出改用 PDF→PyMuPDF 回退（`run_manager.py` L222-254 实现） | 已绕开 |

---

## 桶 D. 许可证 / 上游 MCP 受限（0 条）

本仓库当前未触发许可证类受限接口（如 SOLIDWORKS Simulation / Routing / Toolbox 专用 API 需要相应模块授权）。如未来引入，在此桶记录。

---

## 桶 E. 参数错误 / 调用时机不当（2 条）

| ID | 接口 | 原因 | 解决方案 | 优先级 |
|---|---|---|---|---|
| E-1 | `OpenDoc6` outparams | byref Errors/Warnings 必须用 `VARIANT(VT_BYREF\|VT_I4, 0)` 包装；裸传整数会得到 `类型不匹配` | 已在 `probe_runner.open_or_get_active` 实现包装；`drw_qc_loop.py` 同步采用 | P0（在出图链路） |
| E-2 | `IDrawingDoc` 多数方法 | 当前样本是 SLDPRT，所有 IDrawingDoc 接口必然 fail；属于"调用时机不当" | 选择 SLDDRW 样本后再跑 | n/a |

---

## 桶 F. 暂不需要 / 不在本里程碑（5 条）

| ID | 接口 | 原因 | 优先级 |
|---|---|---|---|
| F-1 | `AddComponent5 / AddMate5` | destructive，本次只读冒烟 | n/a |
| F-2 | `FeatureExtrusion3 / FeatureCut4 / FeatureRevolve2 / FeatureFillet3 / FeatureChamfer / Shell / FeatureLinearPattern5 / FeatureCircularPattern5 / InsertSheetMetalBaseFlange2 / InsertReferencePlane2` | destructive；本仓库 v5 出图不创建特征 | n/a |
| F-3 | `Create3rdAngleViews2 / CreateSectionViewAt5 / InsertModelAnnotations3 / InsertCenterMark2` | destructive；已在 v5 链路验证 | n/a |
| F-4 | `Add3 / Set2 / Delete2`（CustomProperty） | destructive；已在 v5 链路验证 | n/a |
| F-5 | `MakeVirtual / AddConfiguration2 / ShowConfiguration2` | destructive | n/a |

---

## 总览

| 桶 | 数量 | 默认优先级 |
|---|---|---|
| A. marshaling | 4 | P1~P2 |
| B. 早绑定错位 | 4 | P2 |
| C. 版本受限 | 3 | P1~P2 |
| D. 许可证 | 0 | — |
| E. 参数 / 时机 | 2 | P0 / n/a |
| F. 暂不需要 | 5 | n/a |

**P0 整改**：1 条（E-1，OpenDoc6 outparams 包装），已在 probe_runner 实现，建议同步到 `drw_qc_loop.py / drw_generate_v5.py`。
**P1 整改**：2 条（A-4 CustomProperty Get4、C-1 IsSheetMetal），下一里程碑处理。
**P2 整改**：6 条，影响小，已用 `call_or_get` helper 在 probe_runner 中绕开；上层代码可按需迁移。

> 没有任何接口处于"无路径可用"状态——每条 ❌ 都给出了至少一种替代方案。
