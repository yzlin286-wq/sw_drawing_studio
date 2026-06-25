# run_log — fix-refdoc-via-qc-and-paths Task 4

闭环验证 Task 1+2+3 修复在真实 SolidWorks 环境下的实际效果。

---

## 节 A — 修改汇总

| Task | 文件 | 行号 | 改动 |
| ---- | ---- | ---- | ---- |
| 1 | `.trae/specs/build-v6-and-validate-exe-ui/drw_qc_loop_v6.py` | L313–L317 | 入口处 `part_path = str(Path(part_path).resolve())` 强制绝对路径 + `[qc_loop_v6] absolute part_path=...` 日志；subprocess 命令传给 v6 的 part_path 同步使用绝对路径 |
| 2 | `.trae/specs/enforce-drawing-quality/drw_quality_check.py` | L203–L222 / L225–L270 / L482–L486 / L547+ / L799+ | 新增 `_get_view_ref_model_path(view)`（ReferencedDocument 优先 + `GetReferencedModelName` 兜底）；`_check_refdoc_correct` 升级：基于文件名 lowercase 匹配 expected_part；输出新增 `name_match` / `name_match_count` / `ref_present` / `ref_present_count` / `bad_ref` 字段；pass 判定改为 `name_match_count ≥ 1` OR `ref_present_count ≥ 1` |
| 3 | `.trae/specs/build-v6-and-validate-exe-ui/drw_generate_v6.py` | L1224–L1273 | 在 [9.7/9] rebind 之后、SaveAs 之前新增 `[9.8/9] ReplaceViewModel`：枚举 created_views 名字 → 调 `drw.ReplaceViewModel(part_abs_path, view_names, instances)`，失败 try/except 不阻塞；ForceRebuild3 + GraphicsRedraw2 兜底刷盘 |

---

## 节 B — 真实闭环结果

### SW 在线状态
- SW pid = **13472**
- SW RevisionNumber = **33.5.0**

### v6 闭环执行
- 命令：`python .trae/specs/build-v6-and-validate-exe-ui/drw_qc_loop_v6.py "3D转2D测试图纸\LB26001-A-04-001.SLDPRT"`
- 退出码 = **0**
- final_pass = True
- round 1：pass=False (`__subprocess_timeout__`，第 1 轮 240s 超时)
- round 2：pass=False, **pass_count=11/12**, issues=`[has_tech_note, has_ra_note, has_datum_a, refdoc_correct, gb_titlebar_complete, gb_has_section_view_or_skipped]`

### 关键日志摘录
```
[qc_loop_v6] absolute part_path=C:\Users\Vision\Desktop\SW 相关\3D转2D测试图纸\LB26001-A-04-001.SLDPRT
[qc_loop_v6] (relative input was: 3D转2D测试图纸\LB26001-A-04-001.SLDPRT)
[main] part_path = C:\Users\Vision\Desktop\SW 相关\3D转2D测试图纸\LB26001-A-04-001.SLDPRT
[loop] subprocess: [..., 'C:\\Users\\Vision\\Desktop\\SW 相关\\3D转2D测试图纸\\LB26001-A-04-001.SLDPRT']
[v6 replace] enum views failed: (-2147352573, '找不到成员。', None, None)
[v6 replace] no views to replace
```

> Task 1（绝对路径转换）：✅ 日志含 `[qc_loop_v6] absolute part_path=...`，子进程命令亦使用绝对路径。  
> Task 3（ReplaceViewModel）：⚠ 调用进入了，但**枚举视图阶段失败**（HRESULT `-2147352573 / 找不到成员`，对应 `Sheet.GetViews` / `Sheet.Views` 方法不存在），导致 `view_names=[]`，没有真正触发 `ReplaceViewModel`。后续 SLDDRW/PDF/DXF 仍正常落盘。

### quality_check 详细字段（来自 `drw_output/v5/LB26001-A-04-001_v5_qc.json`）

```json
"refdoc_correct": {
  "pass": false,
  "total_views": 4,
  "checked_count": 4,
  "name_match": [],
  "name_match_count": 0,
  "ref_present": [],
  "ref_present_count": 0,
  "bad_ref": [
    { "view": "工程图视图1", "ref": "", "expected": "lb26001-a-04-001.sldprt" },
    { "view": "工程图视图2", "ref": "", "expected": "lb26001-a-04-001.sldprt" },
    { "view": "工程图视图3", "ref": "", "expected": "lb26001-a-04-001.sldprt" },
    { "view": "工程图视图4", "ref": "", "expected": "lb26001-a-04-001.sldprt" }
  ],
  "expected_part_path": "C:\\Users\\Vision\\Desktop\\SW 相关\\3D转2D测试图纸\\LB26001-A-04-001.SLDPRT"
}
```

| 指标 | 数值 |
| ---- | ---- |
| score_pass_count | **11/12** |
| refdoc_correct.pass | **False** |
| name_match_count | **0/4** |
| ref_present_count | **0/4** |
| bad_ref 长度 | **4/4** |
| dim_count_sufficient.dim_total | **44** (threshold 10.55) |
| view_overlap.pass | **True** |
| view_in_frame.pass | **True** |

### vision_score
- 退出码 = 0
- vision_score = **55**
- issues 关键字 = `[gb_titlebar_complete, gb_has_section_view_or_skipped, has_datum_a, refdoc_correct]`

---

## 节 C — 阶段对比

| 阶段 | vision_score | qc_pass | refdoc bad_ref | refdoc name_match |
| ---- | ------------ | ------- | -------------- | ----------------- |
| extend Task 11 | 35 | 11/12 | 4/4 | N/A |
| build-v6 Task 7 | 65 | 11/12 | 4/4 | N/A |
| build-v6 Task 8 | 65 | 11/12 | 4/4 | N/A |
| **fix-refdoc Task 4** | **55** | **11/12** | **4/4** | **0/4** |

---

## 节 D — 残余 / 下一步

### 未达成项

1. **ReplaceViewModel 没真正生效**  
   `[v6 replace] enum views failed: (-2147352573, '找不到成员。', None, None)` → `[v6 replace] no views to replace`。  
   根因：当前 v6 在 SaveAs 之前枚举 sheet 上的视图时使用的 COM 成员（`Sheet.GetViews` / `Sheet.Views` 之类）在 SW 2025 (rev 33.5.0) Python COM 后期绑定下不可用。  
   结果：`view_names` 为空，未把 4 个视图 rebind 到 part 文件，refdoc 仍全空，`name_match_count=0/4`。

2. **vision_score 退化（65 → 55）**  
   未通过 ≥60 不退化阈值。issues 仍指向：  
   - `gb_titlebar_complete`（标题栏字段缺失）  
   - `gb_has_section_view_or_skipped`（缺剖视图）  
   - `has_datum_a`（基准 A 标识不规范）  
   - `refdoc_correct`（与 QC 一致）  
   该 4 项中有 3 项是 LLM 视觉判定，与 refdoc 同源问题相关；refdoc 修复未生效，是导致退化的主因之一。

3. **第 1 轮 240s 超时**  
   `round 1: __subprocess_timeout__` — v5/v6 出图器首轮经常因冷启动 SW 超时；第 2 轮正常完成。可考虑首轮 timeout 加大或预热 SW。

### 建议下一个 spec 方向

- **A. 用 .NET / pywin32 EnsureDispatch 修复视图枚举**  
  改用 `IModelDocExtension.GetPersistReference3` / `Drawing.GetFirstView` + `IView.GetNextView` 链表式遍历（这是 SW 官方稳定 API），替代当前后期绑定的 `Sheet.GetViews`。或预先在 v6 的 [9.7/9] rebind 块里把 created_views 全局缓存（avoid re-enumerating in [9.8/9]）。  
- **B. 升级到 SW 2026 / 检查 Type Library**  
  `RevisionNumber=33.5.0` 是 SW 2025；查 SW 2026 是否对 `Sheet.GetViews` 提供新兼容。  
- **C. 直接走 macro/.swp**  
  `templates/macros/auto_section.bas` 已经有 macro 工具链，可在 .swp 中调用 `ReplaceViewModel` 并通过 `RunCommand` 触发，绕过 Python 后期绑定问题。  
- **D. refdoc 修复策略**：在 part 已成功 SaveAs 的工程图上，单独跑一个 `drw_relink_refdoc.py` 脚本，通过 `IDrawingDoc.Sheet().GetViews()` （EnsureDispatch + Type Library 早期绑定）逐个 view 调 `IView.ReferencedDocument = SwModel`，避开 v6 主流程的视图枚举瓶颈。

---

_生成时间：2026-06-18 / 工作目录：c:\\Users\\Vision\\Desktop\\SW 相关_

---

## 节 E 二次验证（Task 5 修复后）

修复点：[9.7/9] 缓存视图名为 _rebound_view_names；[9.8/9] 复用 + 链表+created_views 三级兜底

文件改动：`.trae/specs/build-v6-and-validate-exe-ui/drw_generate_v6.py`
- L1194–L1228：[9.7/9] 块开头新增 `_rebound_view_names: list = []`；rebind 循环内追加 `v_.Name` 收集（去重）；print 增加 `names=...`
- L1230–L1290：[9.8/9] 块整体改写——优先复用 `_rebound_view_names`，否则链表枚举，再退一步用 `created_views`；统一用 `_part_abs` / `_pyc_rv` / `_VARIANT_RV` 局部变量避免名字冲突

重跑结果：
- 退出码: **0**
- view_names 收集数: **4**（`['工程图视图1', '工程图视图2', '工程图视图3', '工程图视图4']`）
- ReplaceViewModel 调用结果: **False**（COM 调用进入但返回 False，未抛异常）
- refdoc_correct.pass: **false**
- name_match_count: **0**/4
- ref_present_count: **0**/4
- bad_ref 长度: **4**
- vision_score: **65**/100

关键日志摘录：
```
[9.7/9] rebound 4 views to part+cfg='默认', names=['工程图视图1', '工程图视图2', '工程图视图3', '工程图视图4']
[v6 replace] view_names=['工程图视图1', '工程图视图2', '工程图视图3', '工程图视图4'], part_abs=C:\Users\Vision\Desktop\SW 相关\3D转2D测试图纸\LB26001-A-04-001.SLDPRT
[v6 replace] ReplaceViewModel(4 views) -> False
```

阶段对比:
| 阶段 | vision_score | qc_pass | name_match | bad_ref |
| ---- | ------------ | ------- | ---------- | ------- |
| Task 4 | 55 | 11/12 | 0/4 | 4/4 |
| Task 5 | 65 | 11/12 | 0/4 | 4/4 |

### 结论

- ✅ **视图枚举问题已修复**：[9.7/9] 缓存机制让 [9.8/9] 拿到 4 个视图名，不再触发 `enum views failed` 报错；
- ⚠ **ReplaceViewModel 返回 False**：COM 调用本身没抛异常（VARIANT 数组传参成功），但 SW 拒绝执行，导致 ReferencedDocument 仍为空。即便 [9.7/9] 已成功 `SetReferencedDocument(part)`，最终保存到磁盘的 SLDDRW 中 view 的 ref 仍为空字符串。
- ✅ **vision_score 65 ≥ 60**：未退化，达到 checklist 第 9 项阈值。
- ❌ **name_match_count=0、bad_ref=4**：未达到第 8 项「name_match ≥ 1/4 或 bad_ref ≤ 3/4」阈值。

### 下一个 spec 方向（C/D 二选一）

- **方向 C — VBA 宏 ReplaceViewModel**  
  Python 后期绑定 + `VARIANT(VT_ARRAY|VT_DISPATCH, [None]*N)` 在某些 SW 版本下被默默忽略。改用 `templates/macros/auto_section.bas` 同款 .swp 宏：宏内部走 SW 早期绑定 (`Dim swDraw As DrawingDoc`)，调 `swDraw.ReplaceViewModel partAbs, viewNames(), instances()`。SaveAs 之前通过 `sw.RunMacro2(...)` 触发，绕过 Python COM 桥。
- **方向 D — .NET API + pywin32 EnsureDispatch**  
  在 v6 启动时执行 `from win32com.client import gencache; gencache.EnsureDispatch("SldWorks.Application")` 走早期绑定；这样 `drw.ReplaceViewModel` 的参数类型由 PyWin32 自动按 typelib 推断 SAFEARRAY，不再需要手工 VARIANT 包装。如果仍 False，进一步用 `IView.SetReferencedDocument` + `IModelDoc2.ForceRebuild3(False)` 在每个视图后立即调一次 `drw.GraphicsRedraw2` 让 SW 真正持久化。

> **不退化保障**：本轮所有改动均在 try/except 内，view_names 收集失败 / ReplaceViewModel 异常 都不会阻塞 SaveAs，因此即使 ReplaceViewModel 返回 False，SLDDRW/PDF/DXF 仍正常落盘，vision_score 反而从 55 → 65。

