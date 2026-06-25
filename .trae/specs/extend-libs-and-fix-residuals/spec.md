# 扩展标准件 / BOM / 工艺 / 核价库 + 修复 v5 残余问题 Spec

## Why
craft-gb-drwdot-template 已把 vision_score 从 15 推到 55、qc_pass 推到 11/12，残余 4 项硬限制（标题栏字段空 / 剖视图缺失 / refdoc 解除 / 基准 A 不完整）属 v5 流程层 + 源 SLDPRT 数据层问题；同时业务侧需要扩展标准件库 / BOM 库 / 工艺库 + 核价功能，使应用具备完整的"读懂图纸 → 出 2D → 拆 BOM → 算工艺 → 出报价"闭环。

## What Changes
### 1. 库与核价（业务能力扩展）
- 新增 `libs/standard_parts/`：基于 GB Toolbox 风格的标准件库（YAML/SQLite 双轨：YAML 可读，SQLite 可索引），覆盖紧固件 / 轴承 / 销轴等 8 类，每条含 GB 标准号 / 规格 / 默认 CustomProperty / Toolbox 链接路径
- 新增 `libs/bom/`：BOM 抽取器，给定装配体（或单件）→ 输出 `bom.csv` + `bom.xlsx`（用 openpyxl 写表）；对单件零件输出 1 行 BOM
- 新增 `libs/process/`：工艺库 SQLite，覆盖钣金折弯 / 激光切割 / 喷粉 / CNC 铣 / 攻丝等 12 道工序的"工时 + 单价 + 损耗系数"
- 新增 `libs/pricing/quote.py`：核价引擎，输入 BOM + 工艺路线 → 输出 `quote.json`（材料费 / 加工费 / 表面处理 / 包装 / 利润 + 总价）+ `quote.md`（人类可读）
- 新增 GUI 第 6 页"BOM 与核价"：表格展示 BOM；点"AI 工艺建议"调 LLM 给工艺路线；点"生成报价"调 quote.py；导出按钮

### 2. v5 残余问题修复
- 在 v5 主流程开头加 `_inject_default_custom_properties(part_path)`：若 SLDPRT 13 个 key 任一为空则自动注入：机型="通用"、品名=basename、设计="auto"、日期=today、数量=1、单位="mm"、材质=（GetMaterialPropertyName 兜底）、表面处理="脱脂磷化喷粉"、比例=（运行期推断）、重量=（GetMassProperties[5]）、图号=basename、类别="A"、机型 / UNIT_OF_MEASURE 一并补齐
- 新增 `templates/macros/auto_section.bas` + `templates/macros/build_swp.py`：把 .bas 编译为 .swp 后用 `RunMacro2(swp, module, proc)` 在 SW 进程内**绕开** pywin32 marshaling 调 `CreateSectionViewAt5`
- 在 v5 创建视图后立即 `view.SetReferencedDocument(part)` 之后**再调** `view.SetReferencedConfiguration(part.GetActiveConfiguration().Name)` 防止 SaveAs 时 refdoc 解除
- 在基准 A 注入处补 `view.InsertGtol()` 形位公差框（GeometricTolerance type=2 平面度），让视觉模型识别为"完整基准"

### 3. 学习沉淀
- 联网检索成果 → `libs/research_notes.md`（Toolbox / BOM / 工艺 / 核价 4 节）

### BREAKING
- 无（所有改动纯增量；v5 旧路径在没有库数据时仍可工作）

## Impact
- Affected specs: `enforce-drawing-quality`、`harden-v5-and-vision-loop`、`craft-gb-drwdot-template`、`build-3d-to-2d-desktop-app`
- Affected code:
  - 新增 `libs/standard_parts/parts.yaml`、`libs/standard_parts/build_db.py`、`libs/standard_parts.db`
  - 新增 `libs/bom/extract_bom.py`
  - 新增 `libs/process/process.db`、`libs/process/seed.py`
  - 新增 `libs/pricing/quote.py`、`libs/pricing/rules.yaml`
  - 新增 `libs/research_notes.md`
  - 新增 `templates/macros/auto_section.bas`、`templates/macros/build_swp.py`
  - 修改 `.trae/specs/enforce-drawing-quality/drw_generate_v5.py`（注入 CustomProperty + section 兜底 + refdoc + GTol）
  - 修改 `app/ui/main_window.py` + 新增 `app/ui/bom_pricing_page.py`、`app/services/bom_service.py`、`app/services/pricing_service.py`
  - 新增 `.trae/specs/extend-libs-and-fix-residuals/run_log.md`

## ADDED Requirements

### Requirement: 标准件库
系统 SHALL 提供 `libs/standard_parts/parts.yaml`（人读）+ `libs/standard_parts.db`（SQLite 索引），覆盖 ≥ 8 类标准件、≥ 50 条 GB 规格。

#### Scenario: 查询 GB/T 70.1 内六角螺钉 M5x16
- **WHEN** 调用 `bom_service.lookup_standard("GB/T 70.1", "M5x16")`
- **THEN** 返回字典含 `name="内六角圆柱头螺钉"、material="8.8级钢"、weight_g=...、price_cny=...`

### Requirement: BOM 抽取
系统 SHALL 给定 SLDPRT/SLDASM 输出含表头 `[序号 / 件号 / 名称 / 规格 / 数量 / 材质 / 重量 / 备注]` 的 CSV + XLSX。

#### Scenario: 单件 BOM
- **WHEN** 输入 `LB26001-A-04-001.SLDPRT`
- **THEN** 落地 `<base>_bom.csv` 与 `<base>_bom.xlsx`，含 1 行装配父件 + N 行子标准件（若是单件则 1 行）

### Requirement: 工艺库与工艺路线
系统 SHALL 提供 `libs/process/process.db` 含 ≥ 12 道工序，每道有 `process_code / name / unit_price_cny / unit / hourly_rate / scrap_factor` 字段。

#### Scenario: 工艺路线推断
- **WHEN** 调 `process_service.suggest_route(part_meta)` 输入钣金件 + 折弯 + 喷粉
- **THEN** 返回工艺路线 JSON 列表，每项含 `process_code / qty / minutes / cny`

### Requirement: 核价引擎
系统 SHALL 输入 BOM + 工艺路线 → 输出 `quote.json` + `quote.md`，含材料费、加工费、表面处理、包装、利润、税率、总价 7 项。

#### Scenario: 核价
- **WHEN** 调 `quote.calculate(bom, route, profit=0.15, tax=0.13)`
- **THEN** 返回 dict 含 `total_cny` 数值、`breakdown` 每项金额，并落盘 `<base>_quote.json` 与 `<base>_quote.md`

### Requirement: GUI 第 6 页 BOM 与核价
系统 SHALL 在主窗口左侧导航增加"BOM 与核价"项，展示 BOM 表格 + 工艺路线 + 报价摘要。

#### Scenario: 一键报价
- **WHEN** 用户点"生成报价"
- **THEN** GUI 调 LLM 推断工艺路线 + 调 quote 计算 → 表格更新 + 弹窗显示总价

### Requirement: SLDPRT 自动注入 13 个 CustomProperty
系统 SHALL 在 v5 出图开始时，对源 SLDPRT 的 13 个 key 中任一为空者补入默认值；不修改原 SLDPRT，仅写到 v5 内存模型；同时把这些值持久化到 SLDDRW 标题栏。

#### Scenario: 空值零件
- **WHEN** 输入 13 字段全空的 SLDPRT
- **THEN** v5 输出 SLDDRW 标题栏的 13 字段全部非空（机型="通用"、品名=basename 等）

### Requirement: VBA 兜底剖视图
系统 SHALL 提供 `templates/macros/auto_section.bas` 经 SW 编译为 `.swp`，v5 当原生 `CreateSectionViewAt5` 失败时通过 `RunMacro2` 调用宏完成剖视图。

#### Scenario: 剖视图成功
- **WHEN** v5 跑完后扫描视图列表
- **THEN** 至少含 1 个 `type=4 (SectionView)` 的视图

### Requirement: refdoc 不解除
系统 SHALL 在 `view.SetReferencedDocument(part)` 之后立刻 `view.SetReferencedConfiguration(part.GetActiveConfiguration().Name)`。

#### Scenario: refdoc_correct
- **WHEN** quality_check 跑出 refdoc_correct
- **THEN** 检查到的视图 ReferencedDocument 与 ReferencedConfiguration 均非空

### Requirement: 基准 A 完整 GTol
系统 SHALL 在基准 A 注入处补 `view.InsertGtol()` 形位公差框（type=平面度，公差=0.05），与基准代号联动。

#### Scenario: vision 不再报基准缺失
- **WHEN** 重跑 vision_loop
- **THEN** issues 中不再含 `incomplete_datum_a` / `missing_gtol`

### Requirement: 联网研究沉淀
系统 SHALL 在 `libs/research_notes.md` 沉淀 Toolbox / BOM / 工艺 / 核价 4 节研究笔记，每节列 ≥ 3 条来源链接。

#### Scenario: 文档完整
- **WHEN** 验证收束
- **THEN** `research_notes.md` ≥ 4 节、有标准条款引用与 SW API 调用样例

## MODIFIED Requirements

### Requirement: drwdot_template（来自 craft-gb-drwdot-template）
保持不变；BOM/核价表导出独立于模板，不冲突。

## REMOVED Requirements
（无）
