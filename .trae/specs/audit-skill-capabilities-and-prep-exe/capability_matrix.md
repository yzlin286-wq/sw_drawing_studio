# Capability Matrix — solidworks-automation-skill 在本仓库的能力面

> 时间：2026-06-18
> 范围：`app/`（桌面服务/UI）+ `.trae/specs/enforce-drawing-quality/`（QC 闭环）+ 相关辅助脚本
> 标记：✅ 已接入 UI / 🔧 仅 CLI / 🧪 仅本地脚本探针 / 🔌 仅 MCP / 🚧 受许可证或上游限制

---

## 1. 连接与应用层（SolidWorks 实例）

| 能力 | 入口 | 是否暴露 UI | 实测状态 |
|---|---|---|---|
| 自动连接已运行 SW 实例（GetActiveObject） | [home_page.py:99](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/app/ui/home_page.py#L93-L113) `_refresh_sw_status` | ✅（首页"SolidWorks 连接状态"卡） | warn — 卡片只在打开时检测一次，无手动刷新；未连接时卡片仅显文案，无重试按钮 |
| 静默/可见切换、用户偏好读写 | 由 `drw_generate_v5.py` / `drw_quality_check.py` 内部调用（如 `GetUserPreferenceDoubleValue(89)`） | 🔧 | pass — `drw_quality_check.py` 第 250 行已用于读取字高 |

## 2. 文档管理

| 能力 | 入口 | UI | 备注 |
|---|---|---|---|
| 打开 SLDPRT/SLDASM/SLDDRW（OpenDoc6） | `drw_quality_check._open_drw` 第 138 行；`drw_generate_v5.py` 内部 | 🔧（由 SwRunner 触发） | warn — 历史日志显示存在 `OpenDoc6 returned None`（见 `drw_output/v5/LB26001-A-04-001_v5_qc.json`），需关注 |
| 自定义属性读写（13 项 PROP_KEYS） | `drw_quality_check.py` 第 55-59 行 `PROP_KEYS` + 第 331-348 行采集 | 🔧 | pass |
| 关闭文档 / 切活动文档 | `drw_quality_check.py` 第 384-388、636-639 行 | 🔧 | pass |

## 3. 草图（2D & 3D）

| 能力 | 入口 | UI | 备注 |
|---|---|---|---|
| 直线/矩形/圆/圆弧/槽口/样条 | 仅在上游 `solidworks-automation-skill`（npm 包）中实现，本仓库未直接调用 | 🔌（仅 MCP） | n/a — 本次桌面应用未使用 |
| 草图几何关系 / 尺寸标注 | 同上 | 🔌 | n/a |

## 4. 零件特征

| 能力 | 入口 | UI | 备注 |
|---|---|---|---|
| 拉伸/旋转/倒圆角/抽壳/筋/阵列 | 上游 MCP `solidworks-automation-skill` | 🔌 | 桌面应用本次目标是"3D→2D 出图"，不创建特征 |

## 5. 装配体

| 能力 | 入口 | UI | 备注 |
|---|---|---|---|
| 添加组件 / 配合 / 干涉检查 | 上游 MCP `solidworks-automation-skill` | 🔌 | 桌面应用本次未涉及 |

## 6. Motion Study & 仿真

| 能力 | 入口 | UI | 备注 |
|---|---|---|---|
| 旋转马达 / Calculate / Play | 上游 MCP `solidworks_add_rotary_motor` 等 | 🔌 | 桌面应用本次未涉及 |

## 7. 工程图（核心能力）

| 能力 | 入口 | UI | 备注 |
|---|---|---|---|
| 三视图 + 等轴测自动布局 | [drw_generate_v5.py](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/.trae/specs/enforce-drawing-quality/drw_generate_v5.py) | ✅ 通过 [SwRunner.run_single](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/app/services/sw_runner.py#L37-L42) | pass — 在 `LB26001-A-04-001` 上有历史成功产物 |
| 模型尺寸自动标注 | `drw_generate_v5.py` 内 `InsertModelAnnotations3` | ✅ | pass |
| 中心标记 / 中心线 | `drw_generate_v5.py` | ✅ | pass — 由 QC 第 8 项检查 |
| 标题栏 13 项自定义属性 | `drw_generate_v5.py` 写入；`drw_quality_check.py` 第 6 项校验 | ✅ | pass |
| 视图比例选取（GB 标准比例集） | `drw_generate_v5.py` + QC 第 4 项 `GOOD_SCALES` | ✅ | warn — 当前 `GOOD_SCALES` 含 `(1,3)(1,4)`（GB 14690 不允许 3 与 4），需收紧 |
| PDF / DXF 导出 | `drw_generate_v5.py` SaveAs 链路 | ✅ | pass |
| 第一角投影标志 | `drw_generate_v5.py` `SetupSheet5(..., firstAngle=True)` | ✅ | pass |
| 剖视图 | 仅 `repair-section-and-recompare/section_helper.py`（CLI） | 🔧 仅 CLI | warn — 未在 v5 默认链路启用，UI 无开关 |

## 8. 文件导出

| 能力 | 入口 | UI | 备注 |
|---|---|---|---|
| PDF（每张工程图一次性出） | v5 SaveAs | ✅ | pass |
| DXF（含钣金展开） | v5 SaveAs | ✅ | pass |
| STEP / IGES / Parasolid / STL | 上游 MCP（`solidworks_export_active`） | 🔌 | UI 无入口 |
| PNG（用于视觉 QC 预览） | [vision_qc.slddrw_to_png](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/app/services/vision_qc.py#L82-L105) → fitz / pdf2image / 复制已有 PNG 三层兜底 | ✅（QC 页自动渲染） | pass |

## 9. 钣金 / 焊件

| 能力 | 入口 | UI | 备注 |
|---|---|---|---|
| 钣金展开图 DXF | v5 / 上游 MCP | 🔌 | UI 无独立入口 |

## 10. 配置 / 设计表 / 方程式

| 能力 | 入口 | UI | 备注 |
|---|---|---|---|
| 配置切换 / 创建 / 删除 | 上游 MCP | 🔌 | UI 无 |

## 11. 自定义属性 / 元数据

| 能力 | 入口 | UI | 备注 |
|---|---|---|---|
| 13 项 PROP_KEYS 写入 + 校验 | `drw_generate_v5.py` + `drw_quality_check.PROP_KEYS` | ✅ | pass |
| 标题栏属性映射 `$PRP:"..."` | 模板 .drwdot（用户提供） | ✅（依赖配置 `drwdot_template`） | warn — `app.yaml.example` 默认指向 `gb_a3.drwdot`，A4 横向需另选 |

## 12. 外观 / 材质 / 渲染

| 能力 | 入口 | UI | 备注 |
|---|---|---|---|
| 文档/特征级颜色 | 上游 MCP `solidworks_set_appearance` | 🔌 | UI 无 |

## 13. 自动化质检 / 复检（本仓库重点）

| 能力 | 入口 | UI | 备注 |
|---|---|---|---|
| 12 项渲染级 QC（视图重叠 / 在框 / 比例 / 字高 / 尺寸/中心标记数量 / 自定义属性 / Note 关键词 / 引用文档） | [drw_quality_check.quality_check](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/.trae/specs/enforce-drawing-quality/drw_quality_check.py#L354-L641) | ✅ 经 SwRunner→loop→生成 `_qc.json` | pass |
| 三轮 QC 闭环（生成→QC→修复 issues→重生成） | [drw_qc_loop.run_qc_loop](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/.trae/specs/enforce-drawing-quality/drw_qc_loop.py) | ✅（SwRunner 子进程调用） | warn — `LB26001-A-04-001_v5_qc.json` 记为 `OpenDoc6 returned None`，三轮闭环未真正生效在该样本上 |
| LLM 视觉评分 (vision_qc) | [vision_qc.vision_score](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/app/services/vision_qc.py#L137-L241) | ✅（QC 页"AI 视觉质检"按钮） | warn — 依赖配置 `llm.yaml` 含 vision_model；`deepseek` 默认无 vision，需切换到 `dashscope`/`openai` |
| 视觉评分低于阈值自动重出图 | [qc_page.set_vision_result](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/app/ui/qc_page.py#L146-L205) | ✅ | pass |
| 多视角 BMP 导出 + 自审查报告 | 上游 MCP / capabilities.md 第 13 节 | 🔌 | UI 无独立按钮 |

## 14. MCP / 代理集成

| 能力 | 入口 | UI | 备注 |
|---|---|---|---|
| 16 个 `solidworks_*` MCP 工具 | 上游 npm 包 `github:wzyn20051216/solidworks-automation-skill` | 🔌 | 不在桌面应用范畴；本次审计**不**展开测试 |
| 全局锁串行执行 | 上游 | 🔌 | n/a |

## 15. 桌面应用的 UI 能力

| 能力 | 入口 | 备注 |
|---|---|---|
| 首页（SW/LLM 状态卡片 + 快速开始） | [home_page.py](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/app/ui/home_page.py) | warn — SW 状态无手动刷新按钮 |
| 批量出图（添加文件/目录、AI 预分析、开始出图、进度条、结果表） | [batch_page.py](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/app/ui/batch_page.py) | warn — 缺"停止"按钮、缺"打开输出目录"行内动作、缺空状态文案 |
| AI 质检（选择 SLDDRW、PNG 预览、视觉打分、生成技术要求、自动重出图） | [qc_page.py](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/app/ui/qc_page.py) | pass |
| 设置（模型 provider/路径/并发） | [settings_dialog.py](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/app/ui/settings_dialog.py) | pass |
| 日志面板（清空/导出/暂停滚动 + 等级着色） | [log_panel.py](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/app/ui/log_panel.py) | warn — 缺 Ctrl+L 快捷键 |
| 工具栏（AI 预分析 / 开始出图 / AI 质检） | [main_window._build_toolbar](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/app/ui/main_window.py#L173-L189) | warn — 操作时缺"运行中"忙碌指示 |

---

## 汇总

| 维度 | 数量 |
|---|---|
| 桌面 UI 直接暴露的能力 | ≈ 14 项（覆盖工程图主链路 + AI 视觉 QC） |
| 仅 CLI / 仅探针 | ≈ 6 项（剖视、deep_probe、compare_v3、section_helper、drw_full_stats、drw_inspect_props） |
| 仅 MCP / 上游 | ≈ 30+ 项（16 工具 + 草图/特征/装配/Motion 全集） |
| 已知缺陷（本次需修补） | 4 项：标准比例集放宽、SW 状态无刷新、批量页缺停止、缺剖视/粗糙度 QC |

> 全部 ✅ 项的入口 + 实测状态在上表中可逐行追溯。已知缺陷在 `smoke_test_report.md` / `ux_review.md` / `gb_compliance_matrix.md` 中分别细化。
