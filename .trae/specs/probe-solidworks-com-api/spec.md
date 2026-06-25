# 拉取 SolidWorks 官方 COM API 文档并对本地实例做接口冒烟 Spec

## Why
本仓库已有的 `sw_api_drawing_rules.md` / `gb_drawing_rules.md` / `capabilities.md` 只覆盖"工程图 + GB 规范"窄面，且大量条目标记为 🔧（未在线验证）。要为 EXE 出图工具提供可信赖的能力底盘，需要：(1) 拉取 SolidWorks 官方 COM API 文档作为权威来源；(2) 用本地 SolidWorks 2025 实例对**核心接口**做"能不能调通"的冒烟；(3) 把"可用 / 不可用 / 受限可用 / 已知 bug"逐条落到一份可检索的 Markdown，并对不可用项给出方案。这份产物会成为"3D→2D 出图 + 后续装配/钣金扩展"的唯一基线。

## What Changes
- 拉取 SolidWorks **官方 COM API 文档**（dev.solidworks.com / SolidWorks API Help），抽取与本仓库目标相关的接口集合，写到 `sw_com_api_index.md`。
- 用本地 SolidWorks 2025 实例驱动一份 `probe_runner.py` 探针脚本，按"接口分组（连接/文档/草图/特征/装配/工程图/导出/钣金/配置/属性/外观/QC）"逐组调用，捕获返回值/HRESULT/异常，落 `probe_result.json` + 控制台日志。
- 把探针结果与官方接口清单对比，输出最终交付物 `sw_com_api_probe.md`：每个接口至少含 (1) 官方签名 + Help 链接 (2) 本地 Python 调用示例 (3) 实测状态 ✅/⚠/❌ (4) 受限/失败原因 (5) 解决方案 / 兜底方案。
- 对不可用接口建立 `unresolved_apis.md`：含原因分类（许可证 / 版本不支持 / pywin32 marshaling / 参数不当 / 上游 bug）+ 优先级 + 工单状的下一步建议。
- 不删除现有 `sw_api_drawing_rules.md` / `capabilities.md`；本次产物在它们基础上做"权威 + 实测"双重升级。

## Impact
- 受影响 spec：`study-solidworks-skill`（capabilities 将引用本次产物）、`enforce-drawing-quality`（sw_api_drawing_rules 将给出回看链接）、`audit-skill-capabilities-and-prep-exe`（capability_matrix 标记的"上游 MCP / 仅 CLI"行可被实测填实）。
- 新增文件（仅在 `.trae/specs/probe-solidworks-com-api/` 下）：
  - `spec.md`、`tasks.md`、`checklist.md`
  - `sw_com_api_index.md`（官方文档抽取）
  - `probe_runner.py`（探针脚本，可重复执行）
  - `probe_result.json`（探针原始结果）
  - `probe_log.md`（探针运行人话日志 + 摘要）
  - `sw_com_api_probe.md`（最终 API 文档：清单 × 实测 × 解决方案）
  - `unresolved_apis.md`（不可用清单 + 解决方案）
- **不**修改：`app/`、`dist/sw_drawing_studio.exe`、其他 spec 的产物、上游 `solidworks-automation-skill` 包。

## ADDED Requirements

### Requirement: SolidWorks COM API Index from Official Source
系统 SHALL 提供 `sw_com_api_index.md`，按官方 SolidWorks API Help 的分组组织接口清单（至少覆盖 14 个分组：ISldWorks / IModelDoc2 / IPartDoc / IAssemblyDoc / IDrawingDoc / ISketchManager / IFeatureManager / IComponent2 / IConfiguration / ICustomPropertyManager / IModelDocExtension / ILayerMgr / IMassProperty / 文件导出 SaveAs 系列）。

#### Scenario: 任一分组都能查到官方签名
- **WHEN** 阅读 `sw_com_api_index.md` 任一分组
- **THEN** 至少包含该分组下 ≥10 个核心方法/属性，每个含官方签名（如 `OpenDoc6(FileName, Type, Options, Configuration, Errors, Warnings) -> ModelDoc2`）和官方 Help URL（dev.solidworks.com/anchor）。

### Requirement: Local Probe Script
系统 SHALL 提供 `probe_runner.py`，参数化运行：默认对本地"已运行的 SolidWorks 实例"按分组冒烟所有索引内接口；支持 `--group=drawings` 等过滤；每次运行落 `probe_result.json` 与 `probe_log.md`；脚本必须在没有 SolidWorks 时给出友好降级。

#### Scenario: 本地 SolidWorks 在线时
- **WHEN** 用户启动 SolidWorks 后执行 `python probe_runner.py`
- **THEN** 脚本能 `GetActiveObject` 接到实例，跑完全部分组，对每个接口记录 `{name, args, ok, error, result_summary}`；结束后打印 `pass/warn/fail` 统计且 returncode=0。

#### Scenario: 本地 SolidWorks 不在线
- **WHEN** SW 未启动
- **THEN** 脚本不抛栈追踪，输出"SolidWorks 未启动，已跳过 N 个分组"，returncode=2，且仍会写一份 stub 的 `probe_result.json`（含未运行原因）。

### Requirement: API Probe Markdown
系统 SHALL 输出 `sw_com_api_probe.md`，每行一条接口，列：分组 / 官方签名 / Help URL / Python 调用示例 / 实测状态 ✅/⚠/❌ / 失败原因 / 解决方案。⚠/❌ 项 SHALL 给出至少一条可执行的下一步（如"切换到 InsertSurfaceFinishSymbol3 兜底为 CreateText2"）。

#### Scenario: 行可被检索
- **WHEN** 在 IDE 中搜 `OpenDoc6`
- **THEN** 命中且能跳到该行查看完整状态。

### Requirement: Unresolved API Catalog
系统 SHALL 输出 `unresolved_apis.md`，把所有 ❌ 与高风险 ⚠ 集中归档，按"许可证受限 / SW 版本受限 / pywin32 marshaling 问题 / 参数错误 / 上游 bug / 暂不需要"6 类分桶；每条含优先级 P0/P1/P2 与具体 owner-action。

#### Scenario: 任意一条不可用接口都有路径
- **WHEN** 阅读 `unresolved_apis.md` 任一行
- **THEN** 都有"原因分类 + 解决方案 + 优先级"三字段全部非空。

## MODIFIED Requirements
（无）

## REMOVED Requirements
（无）
