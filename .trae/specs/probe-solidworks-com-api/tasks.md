# Tasks

- [x] Task 1: 拉取 SolidWorks 官方 COM API 文档 → `sw_com_api_index.md`
  - [x] SubTask 1.1: 抓取 `https://help.solidworks.com/2024/english/api/sldworksapi/` 与 `https://help.solidworks.com/2024/english/api/sldworksapiprogguide/` 关键索引页（用 WebFetch；若被 403/JS 渲染挡则改抓 `https://help.solidworks.com/SearchHelp.aspx?keyword=…` + 缓存到本地 raw 目录）
  - [x] SubTask 1.2: 解析 14 个核心接口分组（ISldWorks / IModelDoc2 / IPartDoc / IAssemblyDoc / IDrawingDoc / ISketchManager / IFeatureManager / IComponent2 / IConfiguration / ICustomPropertyManager / IModelDocExtension / ILayerMgr / IMassProperty / SaveAs 导出）
  - [x] SubTask 1.3: 每个分组 ≥10 个核心方法/属性，写官方签名 + 锚点 URL
  - [x] SubTask 1.4: 输出到 `sw_com_api_index.md`（每分组一节）

- [x] Task 2: 编写本地探针脚本 `probe_runner.py`
  - [x] SubTask 2.1: 顶层提供 `connect()` 兜底（GetActiveObject → Dispatch；失败时退出码 2）
  - [x] SubTask 2.2: 实现"分组运行器"框架：每分组返回 `[{name, args_repr, ok, error, summary}]`
  - [x] SubTask 2.3: 实现 14 个分组的探针函数（连接 / 文档 / 自定义属性 / 草图 / 特征 / 装配 / 工程图 / 视图 / 标注 / 导出 / 钣金 / 配置 / 质量属性 / 图层）
  - [x] SubTask 2.4: CLI: `--group=...` `--out=probe_result.json` `--log=probe_log.md`；默认对仓库内 `3D转2D测试图纸/LB26001-A-04-001.SLDPRT` 跑只读探针，破坏性接口（写入/删除）默认 SKIP，需 `--write` 才跑

- [x] Task 3: 在线运行探针（本任务由用户确认 SW 已启动后再触发）
  - [x] SubTask 3.1: 用户启动 SolidWorks → 打开 `LB26001-A-04-001.SLDPRT`
  - [x] SubTask 3.2: 执行 `python probe_runner.py`
  - [x] SubTask 3.3: 检查 `probe_result.json` 落盘 + `probe_log.md` 摘要 + `pass/warn/fail` 统计（pass=48, fail=9, skip=26）
  - [x] SubTask 3.4: 若 SW 未启动，记录 stub 结果 + skipped 标记（已实现降级逻辑）

- [x] Task 4: 整合官方文档与探针结果 → `sw_com_api_probe.md`
  - [x] SubTask 4.1: 用 `sw_com_api_index.md` 行 join `probe_result.json` 行（按 group+name）
  - [x] SubTask 4.2: 每条加 ✅/⚠/❌ + 失败原因 + Python 调用示例 + 解决方案
  - [x] SubTask 4.3: 头部加"统计概览"小节（按分组的 pass% 柱状文本）

- [x] Task 5: 不可用清单 → `unresolved_apis.md`
  - [x] SubTask 5.1: 抽出所有 ❌ 与高风险 ⚠
  - [x] SubTask 5.2: 按 6 类分桶（许可证 / 版本 / pywin32 marshaling / 参数 / 上游 bug / 暂不需要）
  - [x] SubTask 5.3: 每条标 P0/P1/P2 + owner-action

- [x] Task 6: 验证 & 收尾
  - [x] SubTask 6.1: 按 `checklist.md` 逐项打钩
  - [x] SubTask 6.2: 失败项回填 tasks.md 修复（无失败，未触发）

# Task Dependencies
- Task 2 与 Task 1 可并行起草，但 Task 4 依赖两者
- Task 3 依赖 Task 2 完成
- Task 4 依赖 Task 1 + Task 3
- Task 5 依赖 Task 4
- Task 6 依赖 Task 1~5
