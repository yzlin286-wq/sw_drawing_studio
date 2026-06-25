# 学习 SolidWorks Automation Skill 与 COM 接口 Spec

## Why
用户希望系统学习 `npx github:wzyn20051216/solidworks-automation-skill` 这个 Skill 的具体功能，并掌握 SolidWorks COM 接口的全部能力与用法，以便后续基于此 Skill 在本地工作目录中（含大量 SLDPRT/SLDASM/SLDDRW 文件）进行自动化建模、装配、出图与导出。

## What Changes
- 拉取并分析 `wzyn20051216/solidworks-automation-skill` 仓库结构、SKILL.md、scripts/ 各模块、references/ 文档与 mcp-server。
- 整理 Skill 提供的所有可调用函数（Python 封装 + MCP 工具）的功能、参数、返回值与典型用法。
- 系统梳理 SolidWorks COM 接口（SldWorks、ModelDoc2、PartDoc、AssemblyDoc、DrawingDoc、Feature、SelectionMgr、FeatureManager、SketchManager、Configuration、Component2、Mate2、ModelDocExtension 等）核心对象、常用方法、常用枚举与典型调用模式。
- 输出一份学习笔记（Markdown），归纳 Skill ↔ COM 接口的对应关系，并附带常见易错点与排错建议。
- **不修改任何 SLDPRT/SLDASM/SLDDRW 工程文件**，不安装任何依赖，不执行 SolidWorks 操作；仅做研究与文档输出。

## Impact
- 影响范围：在 `c:\Users\Vision\Desktop\SW 相关\.trae\specs\study-solidworks-skill\` 下生成研究笔记。
- 影响代码：无（纯学习/文档任务）。
- 影响外部系统：无（不调用 SolidWorks，不执行 npx 安装）。

## ADDED Requirements

### Requirement: Skill 功能盘点
系统 SHALL 输出一份覆盖该 Skill 全部脚本模块（sw_session、sw_preflight、sw_macro_guard、sw_connect、sw_appearance、sw_part、sw_assembly、sw_motion、sw_drawing、sw_export、sw_review）和 MCP 工具（solidworks_connect、solidworks_open_document、solidworks_save_document、solidworks_export_active、solidworks_review_active、solidworks_add_rotary_motor、solidworks_health_check、solidworks_create_basic_part、solidworks_add_component、solidworks_add_*_mate、solidworks_set_component_fixed、solidworks_set_appearance 等）的功能清单。

#### Scenario: 用户查阅 Skill 能力
- **WHEN** 用户打开生成的笔记
- **THEN** 能按"建模 / 装配 / 工程图 / 导出 / 外观 / 运动算例 / 自审查 / MCP"分类找到每个函数的用途与调用示例

### Requirement: SolidWorks COM 接口全景梳理
系统 SHALL 提供 SolidWorks COM 接口的核心对象树、常用方法、常用枚举、典型工作流（连接 → 创建/打开文档 → 选择 → 建模/装配/出图 → 保存/导出）以及单位/坐标/语言版本基准面差异等关键概念说明。

#### Scenario: 用户查询某个 COM 调用
- **WHEN** 用户想知道"如何用 COM 添加同心 Mate"或"如何选择面后倒角"
- **THEN** 笔记中能给出对应 COM 对象/方法路径与最小可运行代码骨架

### Requirement: Skill 与 COM 的对应关系
系统 SHALL 将 Skill 中的高层 Python 封装函数映射回底层 SolidWorks COM 调用，标明该封装内部使用了哪些 ISldWorks / IModelDoc2 / IFeatureManager 等接口方法，便于用户在需要扩展或排错时直接落到 COM 层面。

#### Scenario: 用户需要扩展 Skill 未覆盖的功能
- **WHEN** 用户在 Skill 中找不到所需封装
- **THEN** 笔记的"未封装 API 查证流程"章节能指导用户从 references/api-lookup.md 与官方 API Help 入手实现新封装

## MODIFIED Requirements
（无）

## REMOVED Requirements
（无）
