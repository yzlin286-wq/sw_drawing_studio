# Tasks

- [x] Task 1: 联网研究 + 沉淀
  - [x] SubTask 1.1: 检索 Toolbox 标准件结构 / GB Toolbox 二次开发；写到 `libs/research_notes.md` § A 标准件
  - [x] SubTask 1.2: 检索 BOM 表头规范 / 链接 CustomProperty；§ B BOM
  - [x] SubTask 1.3: 检索机械加工工艺库 + 工时核价模型；§ C 工艺、§ D 核价
  - [x] SubTask 1.4: 列每节 ≥ 3 条来源链接 + SW API 样例

- [x] Task 2: 标准件库
  - [x] SubTask 2.1: 在仓库根新建 `libs/`，落地 `libs/standard_parts/parts.yaml`（≥ 8 类、≥ 50 条）
  - [x] SubTask 2.2: 写 `libs/standard_parts/build_db.py`：YAML → SQLite 索引（标号/规格/材质/单价）
  - [x] SubTask 2.3: 写 `libs/standard_parts/__init__.py` 导出 `lookup(std_no, spec)`

- [x] Task 3: BOM 抽取
  - [x] SubTask 3.1: 写 `libs/bom/extract_bom.py`：函数 `extract(sldprt|sldasm) -> list[dict]`，CSV/XLSX 双输出
  - [x] SubTask 3.2: 单件 SLDPRT 退化为 1 行 BOM（取 13 个 CustomProperty）
  - [x] SubTask 3.3: 装配体 SLDASM 通过 `Configuration.GetRootComponent3` 递归（mock 即可，不要求真跑装配）

- [x] Task 4: 工艺库
  - [x] SubTask 4.1: 写 `libs/process/seed.py` 注入 12 道工序到 `libs/process/process.db`（SQLite）
  - [x] SubTask 4.2: 写 `libs/process/__init__.py` 导出 `suggest_route(part_meta) -> list[dict]`
  - [x] SubTask 4.3: 提供"钣金件 / 机加件"两类默认路线模板

- [x] Task 5: 核价引擎
  - [x] SubTask 5.1: 写 `libs/pricing/quote.py`：`calculate(bom, route, profit=0.15, tax=0.13) -> dict`
  - [x] SubTask 5.2: 写 `libs/pricing/rules.yaml` 定义"利润率 / 税率 / 包装系数 / 起订量加价"
  - [x] SubTask 5.3: 输出 `<base>_quote.json` + `<base>_quote.md`

- [x] Task 6: GUI"BOM 与核价"页
  - [x] SubTask 6.1: 写 `app/ui/bom_pricing_page.py`：QTableView × 2（BOM / 工艺路线）+ 按钮"AI 工艺建议 / 生成报价 / 导出"
  - [x] SubTask 6.2: 写 `app/services/bom_service.py` + `pricing_service.py` 把 libs 包给 GUI
  - [x] SubTask 6.3: 在 `main_window.py` 增加左侧导航项"BOM 与核价"

- [x] Task 7: 修 v5 — CustomProperty 注入
  - [x] SubTask 7.1: 在 `drw_generate_v5.py` 加 `_inject_default_custom_properties(part)` 在打开 part 后立即调用
  - [x] SubTask 7.2: 13 个 key 任一为空则填默认值（机型/品名/...）；不写源文件，仅内存
  - [x] SubTask 7.3: 把这些值复制到 SLDDRW 的 CustomPropertyManager（对应 BlockInst）

- [x] Task 8: 修 v5 — VBA 剖视图兜底
  - [x] SubTask 8.1: 写 `templates/macros/auto_section.bas`（含 `Sub main` 选中前视图水平中线后调 `CreateSectionViewAt5`）
  - [x] SubTask 8.2: 写 `templates/macros/build_swp.py`：用 `sw.RunCommand` + `RunMacro2` 把 .bas 编译为 .swp（或直接复制 .bas 让 SW 兼容）
  - [x] SubTask 8.3: v5 在剖视图原生 API 失败后调 `sw.RunMacro2(swp, "auto_section", "main", ...)` 兜底

- [x] Task 9: 修 v5 — refdoc + GTol
  - [x] SubTask 9.1: 在每个视图 `view.SetReferencedDocument(part)` 后立即 `view.SetReferencedConfiguration(name)`
  - [x] SubTask 9.2: 在基准 A 注入处补 `view.InsertGtol()` 形位公差框（平面度 0.05）

- [x] Task 10: 真实闭环 + 归档
  - [x] SubTask 10.1: 检测/启动 SolidWorks 2025
  - [x] SubTask 10.2: 跑 `python libs/standard_parts/build_db.py` + `python libs/process/seed.py` 初始化数据库
  - [x] SubTask 10.3: 跑 `python libs/bom/extract_bom.py 3D转2D测试图纸\LB26001-A-04-001.SLDPRT`
  - [x] SubTask 10.4: 跑 `python libs/pricing/quote.py <bom_csv>`
  - [x] SubTask 10.5: 跑 vision_loop 1 轮验证 refdoc/section/GTol/CustomProperty 修复效果
  - [x] SubTask 10.6: 归档到 `.trae/specs/extend-libs-and-fix-residuals/run_log.md`

# Task Dependencies
- Task 1 与 Task 7/8/9 可并行
- Task 3 依赖 Task 2
- Task 4/5 与 Task 2/3 可并行
- Task 6 依赖 Task 3 + 4 + 5
- Task 10 依赖 Task 2~9
- Task 11 依赖 Task 10

- [x] Task 11: 修复 Task 10 暴露的 2 项 checklist 失败（依据 spec mode 第七步）
  - [x] SubTask 11.1: 修 v5 的 `view.SetReferencedConfiguration` 时序：在 SaveAs 之前对所有视图重新做一次 SetReferencedDocument + SetReferencedConfiguration + ForceRebuild3
  - [x] SubTask 11.2: 修 v5 的 `view.InsertGtol` 调用方式：先 `drw.ClearSelection2(True)` + 用 `model.InsertGtol()` 而非 `drw.InsertGtol()`；失败回退用 `drw.InsertNote("⏥ 0.05 A")` 模拟 GTol 文本
  - [x] SubTask 11.3: 重跑 vision_loop（≤ 1 轮），更新 run_log.md "## 节 E 二次验证"
  - [x] SubTask 11.4: 据二次验证结果勾选 checklist 中 2 项
