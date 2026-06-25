# 修复 refdoc 判定：绝对路径 + GetReferencedModelName 兜底 + ReplaceViewModel Spec

## Why
build-v6-and-validate-exe-ui Task 8 已确认：v6 4 级 cfg_name 回退（命中"默认"）+ 4 视图 `SetReferencedConfiguration=True` 都已就位，但 quality_check 重读 `view.ReferencedDocument` 仍为空（bad_ref=4/4）。问题不再是脚本侧 cfg_name 写入，而是：(1) `drw_qc_loop_v6.py` 把相对路径传给 SolidWorks 偶发触发 `OpenDoc6 errors=2`；(2) QC 判定单看 `ReferencedDocument` 不符合 SW API 实际持久化行为——SolidWorks API 提供 `IView.GetReferencedModelName()` 作为更稳定的获取方法。本 spec 落地两层修复 + 一项探索性增强。

## What Changes
### 1. `drw_qc_loop_v6.py` 强制绝对路径
- 入口 `part_path` 用 `Path(part_path).resolve()` 统一为绝对路径
- 子进程 `subprocess.run` 命令传给 v6 出图器的 part_path 也是绝对路径
- 加 `[qc_loop_v6] absolute part_path=<...>` 日志

### 2. `drw_quality_check.py` refdoc 判定升级
- 抽出 `_get_view_ref_model_path(view)`：先取 `view.ReferencedDocument.GetPathName()`，失败回退 `view.GetReferencedModelName()`
- `_check_refdoc_correct(model, expected_part_path)` 用 `Path(ref_path).name.lower() == Path(expected_part_path).name.lower()` 判定，避免 `ReferencedDocument` 为空导致误判
- 兼容旧字段 `bad_ref`：对 `ReferencedDocument` 仍空、但 `GetReferencedModelName` 返回正确路径的视图，记入新字段 `name_match` 而非 `bad_ref`

### 3. `drw_generate_v6.py` SaveAs 前 ReplaceViewModel（探索性）
- 在 SaveAs 之前收集 `created_views` 中 4 个视图名 → 调 `drw.ReplaceViewModel(part_abs_path, view_names, instances)` 重新绑定模型
- 失败不阻塞主流程（log + 继续 SaveAs）
- ForceRebuild3 + GraphicsRedraw2 兜底刷盘

### 4. 真实闭环验证
- 重跑 v6 闭环 1 轮，目标：
  - `refdoc_correct.pass=True` 或者 `name_match >= 1/4`（不再 0/4）
  - vision_score ≥ 60 不退化
  - qc_pass ≥ 11/12 不退化

### BREAKING
- 无（QC 字段为新增 + 兼容；v6/qc_loop_v6 路径解析向后兼容）

## Impact
- Affected specs: `enforce-drawing-quality`、`build-v6-and-validate-exe-ui`
- Affected code:
  - 修改 `.trae/specs/build-v6-and-validate-exe-ui/drw_qc_loop_v6.py`
  - 修改 `.trae/specs/enforce-drawing-quality/drw_quality_check.py`
  - 修改 `.trae/specs/build-v6-and-validate-exe-ui/drw_generate_v6.py`
  - 新增 `.trae/specs/fix-refdoc-via-qc-and-paths/run_log.md`

## ADDED Requirements

### Requirement: 绝对路径强制
系统 SHALL 在 `drw_qc_loop_v6.py` 入口将 `part_path` 用 `Path(part_path).resolve()` 转为绝对路径，传递给 v6 出图器的命令也使用该绝对路径。

#### Scenario: 相对路径输入
- **WHEN** 用 `python drw_qc_loop_v6.py "3D转2D测试图纸\\LB26001-A-04-001.SLDPRT"` 启动
- **THEN** 控制台打印 `[qc_loop_v6] absolute part_path=C:\\...` 且 OpenDoc6 不再报 errors=2

### Requirement: GetReferencedModelName 兜底
系统 SHALL 在 `drw_quality_check.py` 中提供 `_get_view_ref_model_path(view)`：优先 `view.ReferencedDocument.GetPathName()`，失败回退 `view.GetReferencedModelName()`。

#### Scenario: ReferencedDocument 为空但 GetReferencedModelName 有值
- **WHEN** 视图 `ReferencedDocument=None` 但 `GetReferencedModelName="...\\LB26001-A-04-001.SLDPRT"`
- **THEN** `_get_view_ref_model_path` 返回该路径字符串，QC 视为 name_match

### Requirement: refdoc_correct 名称匹配
系统 SHALL 在 `_check_refdoc_correct` 中用文件名 lowercase 比较，并新增 `name_match` 字段记录文件名匹配数。

#### Scenario: 4 视图全部名称匹配
- **WHEN** 4 个视图 GetReferencedModelName 文件名都等于 expected_part 文件名
- **THEN** check 返回 `{"pass": True, "name_match": 4, "bad_ref": 0}`（pass 用 name_match 判定）

### Requirement: ReplaceViewModel 重绑定（探索性）
系统 SHALL 在 v6 SaveAs 之前对 4 视图调用 `drw.ReplaceViewModel(part_abs_path, view_names, instances)`；失败不阻塞主流程。

#### Scenario: 重绑定成功
- **WHEN** 调用返回 True
- **THEN** 日志 `[v6 replace] ReplaceViewModel ok` + 后续 ForceRebuild3 触发

### Requirement: 真实闭环验证
系统 SHALL 重跑 v6 闭环 1 轮，记录 refdoc 表现到 `run_log.md`。

#### Scenario: refdoc 改善
- **WHEN** 闭环结束
- **THEN** name_match ≥ 1/4 或 bad_ref ≤ 3/4，vision_score ≥ 60、qc_pass ≥ 11/12 不退化

## MODIFIED Requirements

### Requirement: refdoc_correct 检查（来自 enforce-drawing-quality）
原仅判 `ReferencedDocument` 非空。改为：优先用 `_get_view_ref_model_path`；以文件名 lowercase 匹配 expected_part；只有当 ≥ 1/4 视图匹配且 ReferencedDocument 至少 1 个非空 OR name_match ≥ 1，pass=True。

## REMOVED Requirements
（无）
