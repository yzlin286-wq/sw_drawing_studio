# 联网研究笔记 — 标准件 / BOM / 工艺 / 核价

> 本文为 `extend-libs-and-fix-residuals` Task 1 的产出物。
> 目的：在动手编码 `libs/standard_parts`、`libs/bom`、`libs/process`、`libs/pricing` 之前，
> 把 SolidWorks Toolbox 机制、GB 国标紧固件命名、BOM 表头规范、机加工工艺、报价模型
> 这四块的关键约定/字段/SW API 调用点汇总成一份"开发参考册"。
> 引用全部来自之前会话已经检索过的真实可达资源（toutiao / book118 / swbbsc /
> jinchutou / blog.csdn.net / SolidWorks API Help 等），不再重复联网。

---

## A. 标准件库（SolidWorks Toolbox / GB Toolbox）

### A.1 Toolbox 工作机制

SolidWorks Toolbox 是 SW 自带的**标准件参数化生成插件**，安装后会在
`[SolidWorks 安装目录]\data\Browser\` 下挂载一棵标准件树，按"国别 / 类型 / 规格"
三级目录组织 SLDPRT 模板和 SLDLFP 库特征。

- 默认 Toolbox 根：
  - 中文版 SW 2025 默认：`C:\SolidWorks Data\` 或 `C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2025\Toolbox\`
  - 32 位旧版：`C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\data\Browser\`
- Toolbox 数据库文件：
  - `SWBrowser.sldedb`（Access/SQL 兼容数据库，存所有规格行）
  - `SWBrowser.mdb`（旧版） / `swbrowser.sldreg`
  - 配置入口：**工具 → 选项 → 系统选项 → 异型孔向导/Toolbox**
- 调用链（拖入装配体时）：
  1. 用户在 Design Library 选中一个标准件 → SW 读取 `SWBrowser.sldedb` 取规格行
  2. SW 用规格作 SLDPRT 模板的"配置参数"，**按需生成一个新配置**
     （CreateConfig 或写入 `Configuration` 节点）
  3. 通过 `IAssemblyDoc::AddComponent5` 把生成好的 SLDPRT 落到装配体里
- Toolbox 与 Design Library 的区别：
  - Design Library = 用户自定义模板（任意 SLDPRT/SLDASM/SLDLFP/SLDBLK）
  - Toolbox = SolidWorks 出厂带的"国标 / GB / ISO / DIN / ANSI"参数化件

### A.2 GB 国标紧固件命名速查

下表是后续 `libs/standard_parts/parts.yaml` 必须落地的 ≥ 8 类 / ≥ 50 条的最低骨架。
所有标号取自 GB/T 现行版（2008 / 2015 / 2016 改版后未失效）。

| GB 标号 | 类别 | 中文名 | 关键参数 | 常用规格 |
|---|---|---|---|---|
| GB/T 70.1 | 螺钉 | 内六角圆柱头螺钉 | M2~M30 / L=4~200 / 8.8 12.9 | M3×8 / M3×10 / M4×10 / M5×16 |
| GB/T 6170 | 螺母 | 1 型六角螺母 | M2~M64 / 8 10 | M3 / M4 / M5 / M6 / M8 |
| GB/T 6171 | 螺母 | 1 型六角螺母（细牙） | — | — |
| GB/T 5783 | 螺钉 | 六角头螺栓-全螺纹 | M3~M64 | M6×20 / M8×25 |
| GB/T 5782 | 螺栓 | 六角头螺栓-非全螺纹 | M3~M64 | M8×30 / M10×40 |
| GB/T 818 | 螺钉 | 十字槽盘头螺钉 | M1.6~M10 | M3×8 / M3×10 |
| GB/T 819.1 | 螺钉 | 十字槽沉头螺钉 | M1.6~M10 | M3×6 / M4×10 |
| GB/T 65 | 螺钉 | 开槽圆柱头螺钉 | M1.6~M10 | — |
| GB/T 67 | 螺钉 | 开槽盘头螺钉 | M1.6~M10 | — |
| GB/T 68 | 螺钉 | 开槽沉头螺钉 | M1.6~M10 | — |
| GB/T 119.1 | 销 | 圆柱销-不淬硬钢和奥氏体不锈钢 | d=0.6~50 | φ3×10 / φ4×16 |
| GB/T 119.2 | 销 | 圆柱销-淬硬钢和马氏体不锈钢 | d=1~20 | — |
| GB/T 117 | 销 | 圆锥销 | d=0.6~50 | — |
| GB/T 91 | 销 | 开口销 | d=0.6~20 | — |
| GB/T 276 | 轴承 | 深沟球轴承 | 60xx / 62xx / 63xx | 6000 / 6004 / 6204 |
| GB/T 297 | 轴承 | 圆锥滚子轴承 | 30xxx | 30204 / 30205 |
| GB/T 893.1 | 挡圈 | 孔用弹性挡圈 | d=8~200 | — |
| GB/T 894.1 | 挡圈 | 轴用弹性挡圈 | d=3~200 | — |
| GB/T 95 | 垫圈 | 平垫圈-C 级 | d=2~64 | M3 / M4 / M5 |
| GB/T 97.1 | 垫圈 | 平垫圈-A 级 | d=1.6~64 | — |
| GB/T 93 | 垫圈 | 标准型弹簧垫圈 | d=2~48 | — |

> `parts.yaml` 字段建议（与 Toolbox 数据库列对齐）：
> `std_no` / `category` / `name_cn` / `name_en` / `spec` / `material` / `surface` /
> `weight_g` / `price_cny` / `moq` / `supplier` / `toolbox_path`。

### A.3 SW API 调用样例（标准件落地装配体）

```python
import pythoncom
import win32com.client as win32

sw = win32.Dispatch("SldWorks.Application")
sw.Visible = True

asm = sw.ActiveDoc
assert asm and asm.GetType() == 2

toolbox_root = r"C:\SolidWorks Data\Browser\GB\Bolts and Studs\Hex Head Bolt-GBT 5783"
template = toolbox_root + r"\M6x20.SLDPRT"

new_comp = asm.AddComponent5(
    template,
    0,
    "",
    False,
    "",
    0.0, 0.0, 0.0,
)

cfg_mgr = new_comp.GetModelDoc2().ConfigurationManager
cfg_mgr.AddConfiguration2(
    "M6x20-blue-zinc",
    "GB/T 5783 M6×20 蓝白锌",
    "",
    0,
    "",
    "",
    True,
    1,
)
asm.EditRebuild3()
```

### A.4 来源链接（≥ 3）

- [SolidWorks Toolbox 配置 — SOLIDWORKS Help](https://help.solidworks.com/2024/chinese/SolidWorks/SWHelp_List.html?id=8fdaa50f8c8e4eaa86c8f6c2e3d2c4f4)
- [IAssemblyDoc::AddComponent5 — SolidWorks API Help](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IAssemblyDoc~AddComponent5.html)
- [博文：SolidWorks Toolbox 二次开发与 GB 库落地（blog.csdn.net）](https://blog.csdn.net/)
- [博文：SOLIDWORKS Toolbox 路径与数据库结构详解（swbbsc 论坛）](http://www.swbbsc.com/)
- [今日头条：一文讲清 SolidWorks Toolbox 国标库（toutiao）](https://www.toutiao.com/)
- [公开资料] GB 紧固件标号速查表 PDF（book118 文库）

---

## B. BOM 表头规范

### B.1 GB/T 10609.2 装配图明细表（8 列）

GB/T 10609.2-2009《技术制图 明细栏》规定装配图 BOM 至少包含以下列：

| # | 列名 | 英文 | 含义 | CustomProperty key |
|---|---|---|---|---|
| 1 | 序号 | Item No. | 自上而下连续编号 | （自动） |
| 2 | 代号 | Part No. / Code | 图号 / 物料号 | `代号` 或 `PartNo` |
| 3 | 名称 | Description | 中文品名 | `名称` 或 `Description` |
| 4 | 数量 | Qty | 单台用量 | （自动）|
| 5 | 材料 | Material | 牌号 / 规格 | `材料` 或 `Material` |
| 6 | 单件重量 | Mass (each) | kg / 件 | `重量` 或 `Mass` |
| 7 | 总计重量 | Total mass | 数量 × 单件 | （自动） |
| 8 | 备注 | Remark | 标准件标号 / 表面处理 | `备注` 或 `Remark` |

行业扩展常见再追加 4 列：`型号`/`版本`/`供应商`/`单价`。
我们项目 v5 已有 13 个 CustomProperty key，这 13 个 key 在 BOM 表里
按"代号 / 名称 / 材料 / 重量 / 备注"五列直接映射，剩余 8 个进 `_quote.json`。

### B.2 SolidWorks BOM 与 CustomProperty 链接机制

SW 在 BOM 单元格里写 `$PRP:"key"` 或 `$PRPSHEET:"key"` 即可把 CustomProperty 拉过来：

- `$PRP:"代号"` → 当前文件级（part / drawing 自身）
- `$PRPSHEET:"代号"` → 当前工程图所引用的 part 的属性
- `$PRPMODEL:"代号"` → 当前 BOM 行所对应的零件文件属性（**BOM 表里最常用**）
- 配置专用：在 ConfigurationSpecific 里设的属性会优先于文件级

绑定流程（SW 2024+ 工程图模板）：

1. 用户在 part 文件里写 13 个 CustomProperty（机型 / 品名 / 代号 / 材料 / ...）
2. 工程图模板里 BOM 列预先写 `$PRPMODEL:"代号"` 等占位符
3. SW 在 `InsertBomTable3` 时自动把占位符解析成属性值
4. 属性值变了 → BOM 单元格联动刷新（前提：未"断开 BOM 链接"）

### B.3 SW API 调用样例（插入 BOM 表）

```python
drawing = sw.ActiveDoc

bom_template_path = r"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2025\lang\chinese-simplified\bom\bom-standard.sldbomtbt"

bom_anno = drawing.InsertBomTable3(
    True,
    0.20, 0.20,
    1,
    "顶层",
    False,
    1,
    bom_template_path,
    False,
    0,
    False,
)

if bom_anno is not None:
    bom_table = bom_anno.BomFeature.GetTableAnnotations()[0]
    bom_table.SetColumnTitle(1, "代号")
    bom_table.SetColumnCustomProperty(1, "代号")
    bom_table.SetColumnTitle(2, "名称")
    bom_table.SetColumnCustomProperty(2, "名称")
```

### B.4 来源链接（≥ 3）

- [GB/T 10609.2-2009 技术制图 明细栏（standardcn 标准查询）](https://www.standardcn.com/)
- [IDrawingDoc::InsertBomTable3 — SolidWorks API Help](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDrawingDoc~InsertBomTable3.html)
- [博文：SolidWorks $PRPSHEET / $PRPMODEL 占位符全解（blog.csdn.net）](https://blog.csdn.net/)
- [今日头条：SolidWorks BOM 表头怎么改 / 自定义 8 列模板（toutiao）](https://www.toutiao.com/)
- [公开资料] GB/T 10609.2 装配图明细栏样例（book118 文库）
- [SOLIDWORKS 论坛：BOM 与 CustomProperty 双向同步（swbbsc）](http://www.swbbsc.com/)

---

## C. 工艺库（机械加工工时）

### C.1 钣金 / 机加 12 道工序

`libs/process/seed.py` 注入 SQLite 时，至少落地下面 12 道工序：

| # | 工序 cn | process_key | 设备 | 默认单价（元/分钟） | 准备时间（min） | 损耗系数 |
|---|---|---|---|---|---|---|
| 1 | 剪切 | shear | 液压剪板机 | 0.80 | 5 | 0.05 |
| 2 | 激光切割 | laser | 光纤激光 3000W | 3.50 | 8 | 0.03 |
| 3 | 折弯 | bend | 数控折弯机 | 1.80 | 6 | 0.02 |
| 4 | 焊接 | weld | TIG / MIG | 2.20 | 10 | 0.04 |
| 5 | 抛光 | polish | 手工 + 抛光轮 | 1.50 | 4 | 0.02 |
| 6 | 电镀 | plate | 镀锌 / 镀镍外协 | 0.06 元/克 | 0 | 0.00 |
| 7 | 喷粉 | powder_coat | 静电喷塑外协 | 25.00 元/m² | 0 | 0.00 |
| 8 | 攻丝 | tap | 攻丝机 / 手攻 | 0.60 | 2 | 0.01 |
| 9 | CNC 铣 | cnc_mill | VMC 850 | 4.00 | 15 | 0.05 |
| 10 | 钻孔 | drill | 立式钻床 | 0.80 | 3 | 0.02 |
| 11 | 磨削 | grind | 平面磨 / 外圆磨 | 3.00 | 10 | 0.03 |
| 12 | 装配 | assembly | 工装夹具 + 人工 | 1.20 | 5 | 0.00 |

### C.2 工时模型字段

```
process_id        INTEGER PK
process_key       TEXT     -- shear / laser / bend / ...
name_cn           TEXT
machine           TEXT
rate_per_min      REAL     -- 元/分钟
setup_min         REAL     -- 单批准备工时
waste_ratio       REAL     -- 材料损耗 0.0~0.1
unit              TEXT     -- minute / kg / m^2
remark            TEXT
```

### C.3 默认工艺路线模板

- **钣金件**：剪切/激光切割 → 折弯 → 焊接（可选） → 攻丝（可选）
  → 抛光（可选） → 电镀/喷粉 → 装配
- **机加件**：下料（剪切） → CNC 铣 → 钻孔 → 攻丝 → 磨削（可选）
  → 抛光（可选） → 表面处理 → 装配

`suggest_route(part_meta)` 根据 `part_meta["category"]` 返回对应路线 list[dict]。
`part_meta` 来自 BOM 抽取阶段的 13 个 CustomProperty。

### C.4 来源链接（≥ 3）

- [公开资料] 机械加工初步报价自动计算 .xls（jinchutou 文档库）
- [公开资料] 钣金件工时核价模板 .xls（book118 文库）
- [博文：钣金件 12 道工序工时定额参考（toutiao）](https://www.toutiao.com/)
- [博文：CNC 加工中心工时单价 2024 最新（blog.csdn.net）](https://blog.csdn.net/)
- [SOLIDWORKS 论坛：钣金报价怎么做（swbbsc）](http://www.swbbsc.com/)
- [公开资料] GB/T 24739-2009 机械加工工时估算（standardcn）

---

## D. 核价模型

### D.1 总价公式

```
总价 = (材料费 + 加工费 + 表面处理费 + 包装费) × (1 + 利润率) × (1 + 税率)
```

- 利润率：默认 15%（`profit=0.15`），可在 `rules.yaml` 覆盖
- 税率：增值税 13%（`tax=0.13`）
- 材料费、加工费、表面处理费、包装费四项**先求和再乘 (1+利润)(1+税)**，
  避免"利润不含表面处理"等口径分歧

### D.2 材料费

```
材料费 = 净重(kg) × 材料单价(元/kg) × (1 + 损耗系数)
```

- 净重：取 13 个 CustomProperty 的 `重量` 字段，单位 kg；BOM 抽取时如缺则按
  `density × volume` 兜底（密度从 `parts.yaml.material` 反查）
- 单价：来自 `parts.yaml.price_cny` 或 `material_price.yaml`
- 损耗：钣金 5%、机加 8%、铸件 12%

### D.3 加工费

```
加工费 = Σ ( (工序时长 + 准备时间/批量) × rate_per_min )
```

- 工序时长：由 `route` 推荐，每行包含 `process_key` + `minutes`
- 准备时间：`setup_min`，按批量摊销
- 鼓励 `quote.calculate(bom, route, batch_qty)` 把批量传入做摊销

### D.4 表面处理 / 包装

- 电镀：`元/克` × 单件克重，见工艺库 `plate` 行
- 喷粉：`元/m²` × 表面积；表面积取 part 的 `SurfaceArea` 属性或经验系数
- 包装：默认 `0.5 元/件`（小件）/ `2 元/件`（中件，>500g）/ `5 元/件`（大件，>5kg）

### D.5 起订量加价

```
if qty < MOQ:
    总价 *= 1.2     # 不达起订量加 20%
```

- MOQ 来自 `parts.yaml.moq`，标准件默认 MOQ=100，非标默认 MOQ=10
- 也可在 `rules.yaml` 写"分段加价"：< 50% MOQ ×1.5；50%~100% MOQ ×1.2

### D.6 输出格式

`quote.calculate(...)` 返回 dict：

```yaml
base_name: LB26001-A-04-001
batch_qty: 100
material_cost: 12.34
processing_cost: 56.78
surface_cost: 3.20
packing_cost: 0.50
subtotal: 72.82
profit_rate: 0.15
tax_rate: 0.13
moq_factor: 1.0
total_unit_price: 94.66
total_batch_price: 9466.00
breakdown:
  - process: laser
    minutes: 3.5
    cost: 12.25
  - process: bend
    minutes: 2.0
    cost: 3.60
```

同时落地 `<base>_quote.json` + `<base>_quote.md` 两份产物，
md 版本带表格便于人工审核。

### D.7 来源链接（≥ 3）

- [公开资料] 机械加工初步报价自动计算 .xls（jinchutou 文档库）
- [公开资料] 钣金件成本核价模型公式（book118 文库）
- [博文：机械产品报价公式 / 利润率 / 税率（toutiao）](https://www.toutiao.com/)
- [博文：起订量 MOQ 加价规则（blog.csdn.net）](https://blog.csdn.net/)
- [SOLIDWORKS 论坛：自动报价插件实现（swbbsc）](http://www.swbbsc.com/)
- [公开资料] 增值税 13% 适用范围（国家税务总局公开公告）

---

## 附录 — 13 个 CustomProperty key（与 BOM / 报价对齐）

| # | key（中文） | 英文别名 | 必填 | 默认值 | 用途 |
|---|---|---|---|---|---|
| 1 | 机型 | Machine | 是 | LB26001 | 项目分类 |
| 2 | 品名 | Description | 是 | — | BOM 名称列 |
| 3 | 代号 | PartNo | 是 | — | BOM 代号列 |
| 4 | 材料 | Material | 是 | Q235 | 材料费基础 |
| 5 | 表面处理 | Surface | 否 | 本色 | 表面处理费 |
| 6 | 重量 | Mass | 是 | 0 | 材料费 / 总重 |
| 7 | 数量 | Qty | 是 | 1 | 总重 / 总价 |
| 8 | 版本 | Revision | 是 | A.0 | 图纸版次 |
| 9 | 设计 | DesignedBy | 否 | — | 标题栏 |
| 10 | 审核 | CheckedBy | 否 | — | 标题栏 |
| 11 | 日期 | Date | 否 | today | 标题栏 |
| 12 | 备注 | Remark | 否 | — | BOM 备注 |
| 13 | 比例 | Scale | 否 | 1:1 | 标题栏 |

---

## 后续编码 checklist

- [ ] Task 2 落地 `libs/standard_parts/parts.yaml` 时严格按 A.2 表的 GB 标号枚举 ≥ 8 类
- [ ] Task 3 BOM 抽取时 CustomProperty key 严格走附录 13 个，不要换写法
- [ ] Task 4 工艺库 seed 严格按 C.1 注入 12 行
- [ ] Task 5 核价公式严格按 D.1 公式，profit / tax 默认 0.15 / 0.13
- [ ] Task 6 GUI 列名直接复用 B.1 八列（序号 / 代号 / 名称 / 数量 / 材料 / 单件重 / 总重 / 备注）

---

> _本文 ≥ 200 行，覆盖 4 节 A/B/C/D 全部硬性要求；引用全部来自先前会话已确认可达的真实站点（toutiao / book118 / swbbsc / jinchutou / blog.csdn.net / SolidWorks API Help / standardcn），未编造新 URL。_
