# 审计 solidworks-automation-skill 全功能并为 EXE 上线做准备 Spec

## Why
仓库内已沉淀多份 SolidWorks 自动化能力（`app/services` 桌面服务、`drw_generate_v5.py` 生成、`drw_quality_check.py` 12 项 QC、`drw_qc_loop.py` 三轮闭环、Vision QC、批量出图、MCP 16 工具等），但缺乏一次"端到端的能力审计"：哪些可调用？哪些只能在特定文件上跑？UI 是否完整接入？GB 制图规范是否已落到生成器？只有完成这次审计并修补缺口，后续把功能写进 EXE 才不会带病上线。

本次目标 = **审计 + 测试 + 修补 + 文档化**，**不**做完整 EXE 重打包，但要让 `dist/sw_drawing_studio.exe` 内每个功能都"按下按钮可用、人机交互顺手、出图符合国标"。

## What Changes
- 全量盘点 `solidworks-automation-skill` 在本仓库的"可用能力面"，输出 `capability_matrix.md`（功能 × 入口 × 是否已接 UI × 实测状态 × 已知问题）。
- 对每条已声明 ✅ 的能力做一次**冒烟测试**（pick 1 个代表性文件），输出 `smoke_test_report.md`（含 `pass/warn/fail` + 复现命令 + 失败修复建议）。
- 对**人机交互**（HCI）做一次**显式的 UX Review**（基于现代桌面应用最佳实践：清晰的状态反馈、可中断的长任务、错误可恢复、零状态/空状态/失败态、键盘可达、避免模态阻塞），输出 `ux_review.md` + 一份**可直接落地的微调 patch 清单**。
- 对**制图规范**做一次显式比对（GB/T 17450、GB/T 14689 图框、GB/T 14690 字体、GB/T 4458.1 视图、GB/T 4458.4 尺寸、GB/T 131 表面粗糙度、GB/T 1182 形位公差），输出 `gb_compliance_matrix.md`，并把缺口补到 `drw_generate_v5.py` / 模板 / `drw_quality_check.py` 的检查规则。
- **不**新建 EXE 打包流程（`dist/sw_drawing_studio.exe` 已存在，本次只确认"装上正确的文件后再打包能跑"），但在 `pre_exe_checklist.md` 里给出**打包前 must-have 清单**（依赖、配置默认值、模板路径、错误兜底）。
- 修补冒烟测试中发现的 P0/P1 缺陷（仅修补，不重构）。

## Impact
- 受影响 spec：`study-solidworks-skill`（capabilities 文档已是一次盘点，本次在其上做最新化）、`enforce-drawing-quality`（QC 规则将被扩展）、`build-3d-to-2d-desktop-app`（UI 微调）、`harden-v5-and-vision-loop`（生成器修补）。
- 受影响代码（仅在确认有缺陷时编辑，遵循"最小改动"）：
  - `app/ui/main_window.py`、`app/ui/home_page.py`、`app/ui/batch_page.py`、`app/ui/qc_page.py`、`app/ui/log_panel.py`、`app/ui/settings_dialog.py`
  - `app/services/sw_runner.py`、`app/services/llm_client.py`、`app/services/vision_qc.py`
  - `app/config/defaults.py`、`config/app.yaml.example`、`config/llm.yaml.example`
  - `.trae/specs/enforce-drawing-quality/drw_generate_v5.py`、`drw_quality_check.py`、`drw_qc_loop.py`
- 受影响测试样本：`3D转2D测试图纸/` 下 5 个代表零件 + 1 个装配 + 1 个已存在 SLDDRW（用于回归比对）。
- **不**影响：`dist/sw_drawing_studio.exe` 的发布版本号、`build_exe.spec` 打包流程、上游 `solidworks-automation-skill` MCP server。

## ADDED Requirements

### Requirement: Capability Matrix
系统 SHALL 提供一份覆盖全部已实现能力的能力矩阵，每条能力包含：分类、入口（CLI/服务/UI 按钮/MCP 工具）、是否已接入 UI、实测状态、已知问题。

#### Scenario: 任意一条 ✅ 能力都能在矩阵中追溯到入口
- **WHEN** 阅读 `capability_matrix.md` 中任意一行
- **THEN** 都能找到 (1) 调用文件路径与函数 (2) 是否在 `app/ui` 中暴露按钮 (3) 最近一次实测的 pass/warn/fail。

### Requirement: Smoke Test Report
系统 SHALL 对每条 ✅ 能力执行一次最小冒烟测试并记录结果，失败项 SHALL 给出可执行的修复建议。

#### Scenario: 出图链路冒烟通过
- **WHEN** 在 `LB26001-A-04-001.SLDPRT` 上跑 `drw_qc_loop.py`
- **THEN** 在 `drw_output/` 内生成 SLDDRW + PDF + DXF + `_qc.json`，且 `_qc.json.status` ∈ {pass, warn}（fail 必须修复后重跑直至 pass/warn）。

### Requirement: UX Review & Patch
系统 SHALL 对桌面 UI 做一次基于现代桌面应用 UX 原则的评审，并对发现的高优先级问题做最小修补。评审 SHALL 覆盖：
1. 状态可见性（状态栏、进度条、忙碌提示）
2. 用户控制（取消、暂停、清空日志、重试）
3. 错误处理（人话错误信息、可点击的修复路径、定位到出错文件）
4. 一致性（按钮命名、图标、颜色语义 pass=绿/warn=黄/fail=红）
5. 防错（无文件时禁用"开始"按钮、覆盖输出前确认）
6. 空状态 / 加载态 / 失败态三件套
7. 键盘可达（Enter 提交、Esc 取消、Ctrl+L 清空日志）
8. 文档可达（"帮助"入口指向本仓库 README/规范文档）

#### Scenario: 长任务可被取消且不会冻结 UI
- **WHEN** 用户在批量页面启动 5+ 个文件的处理后点击"停止"
- **THEN** 当前文件能被优雅终止，剩余排队任务被跳过，UI 在 2 秒内回到 idle 状态，日志中明确写出"用户取消"。

#### Scenario: 失败可恢复
- **WHEN** 单文件 QC 三轮后仍 fail
- **THEN** UI 在 QC 页用红色徽章 + 简明错误摘要 + 一键"打开输出目录"按钮告知用户，并在日志中给出 `_qc.json` 中前 3 条规则失败原因。

### Requirement: GB Compliance Matrix
系统 SHALL 输出一份 GB 制图规范符合性矩阵，列出每条相关 GB 条款 → 当前生成器/模板的实现状态 → 缺口补丁。

#### Scenario: 国标关键条款全部命中
- **WHEN** 阅读 `gb_compliance_matrix.md`
- **THEN** 至少包含：图幅图框 (GB/T 14689)、字体 (GB/T 14690 长仿宋)、比例 (GB/T 14690)、视图配置 (GB/T 4458.1 第一角投影)、尺寸标注 (GB/T 4458.4)、剖视 (GB/T 17452)、表面粗糙度 (GB/T 131)、形位公差 (GB/T 1182)、线型线宽 (GB/T 17450)、标题栏 (GB/T 10609.1) 共 10 项，每项标注 ✅/⚠/❌ 与处理方式。

### Requirement: Pre-EXE Checklist
系统 SHALL 在不重新打包 EXE 的前提下，输出"打包前 must-have 检查清单"，覆盖依赖、配置默认值、资源路径、错误兜底、签名（可选）。

#### Scenario: 清单可独立执行
- **WHEN** 用户/CI 按 `pre_exe_checklist.md` 顺序执行
- **THEN** 能在 30 分钟内确认当前 `app/` 是否具备打包条件，并给出"YES/NO + 阻塞项"结论。

## MODIFIED Requirements

### Requirement: Drawing Quality Check (扩展自 enforce-drawing-quality)
现有 12 项 QC SHALL 在本次中至少新增以下检查项（以 `drw_quality_check.py` 为唯一执行入口）：
- 标题栏字段非空（图号/名称/材料/比例/数量/制图/审核/日期）
- 字体族包含"仿宋"或"长仿宋"
- 图纸幅面 ∈ {A0,A1,A2,A3,A4} 且与图纸尺寸一致
- 至少含 1 个剖视图 OR 在 `_qc.json.warnings` 中显式写明"无剖视，已确认"
- 表面粗糙度符号至少 1 处 OR 在自定义属性中标注"全部 Ra3.2"

(若任意一项过严，允许由 `gb_drawing_rules.md` 通过开关位关闭，但默认必须开启)

## REMOVED Requirements
（无）
