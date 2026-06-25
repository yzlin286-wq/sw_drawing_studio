# Tasks

- [x] Task 1: 抓取并解析 Skill 仓库结构
  - [x] SubTask 1.1: 通过 WebFetch 拉取 `SKILL.md`、`README.md`、`mcp-server/README.md`
  - [x] SubTask 1.2: 拉取 `scripts/` 下各模块（sw_session.py、sw_preflight.py、sw_macro_guard.py、sw_connect.py、sw_appearance.py、sw_part.py、sw_assembly.py、sw_motion.py、sw_drawing.py、sw_export.py、sw_review.py）的源码
  - [x] SubTask 1.3: 拉取 `references/` 下 openclaw.md、appearance.md、review.md、api-lookup.md、part-modeling.md、assembly.md、motion-study.md、drawing.md、export.md、advanced.md、troubleshooting.md
  - [x] SubTask 1.4: 拉取 `mcp-server/server.py` 主体，列出已暴露的 MCP 工具签名（mcp-server README.md 已给出工具表，`server.py` 因 raw 端点偶发 5xx 改用 README 表格作为权威清单）

- [x] Task 2: 整理 Skill 功能与 API 清单
  - [x] SubTask 2.1: 按模块归纳每个 Python 函数：用途、入参、返回、典型用法
  - [x] SubTask 2.2: 按 MCP 工具归纳：用途、参数 schema、对应 Python 封装
  - [x] SubTask 2.3: 标注当前 Skill 未覆盖但 references/api-lookup.md 推荐自行扩展的方向

- [x] Task 3: 梳理 SolidWorks COM 接口全景
  - [x] SubTask 3.1: 总结核心对象树（SldWorks → ModelDoc2 → PartDoc/AssemblyDoc/DrawingDoc 等）与扩展接口
  - [x] SubTask 3.2: 整理常用方法分类清单（连接/文档/选择/草图/特征/装配/Mate/工程图/导出/属性/外观/Motion）
  - [x] SubTask 3.3: 整理常用枚举（swDocumentTypes_e、swSelectType_e、swMateType_e、swMateAlign_e、swEndConditions_e、swExportDataFileType_e、swSheetMetal、swMotor 等）
  - [x] SubTask 3.4: 总结关键概念：单位（米/弧度）、基准面中英文差异、SelectByID2 用法、Apprentice vs SldWorks、阻塞对话框 / SilentMode、版本兼容

- [x] Task 4: 建立 Skill ↔ COM 对应关系并产出学习笔记
  - [x] SubTask 4.1: 将 Task 2、Task 3 的内容合并为单一笔记 `notes.md`
  - [x] SubTask 4.2: 给出"如何扩展 Skill 未覆盖功能"的查证 → 实现 → 自审查工作流
  - [x] SubTask 4.3: 列出常见排错场景（连不上、特征失败、Mate 失败、导出失败、Motion 失败）

- [x] Task 5: 自审查
  - [x] SubTask 5.1: 对照 checklist.md 逐项核查 notes.md 是否覆盖
  - [x] SubTask 5.2: 修补遗漏

# Task Dependencies
- Task 2 依赖 Task 1
- Task 3 可与 Task 1/2 并行（来源主要是公开 API 文档与已有知识 + Skill 源码交叉印证）
- Task 4 依赖 Task 2 与 Task 3
- Task 5 依赖 Task 4
