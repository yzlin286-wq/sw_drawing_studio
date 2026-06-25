# 构建 3D 转 2D 桌面应用 Spec

## Why
当前 3D→2D 出图能力（`drw_generate_v5` / `drw_quality_check` / `drw_qc_loop`）以脚本形式存在，工程师只能命令行触发，无法批量、无法可视化、无法调用大模型理解图纸语义。需要打包成可分发的 Windows EXE，提供操作界面 + 大模型接入，让真实使用者无需 Python 环境即可完成"导入 SLDPRT → 自动出图 → AI 视觉质检 → 一键交付"全流程。

## What Changes
- 新增 GUI 桌面应用 `sw_drawing_studio`（PySide6 + qt-material 主题），打包为单文件 EXE（PyInstaller）。
- 新增大模型抽象层 `llm_client`，支持 OpenAI 兼容协议（OpenAI / DeepSeek / DashScope / 智谱 / 本地 Ollama），通过 `config/llm.yaml` 可视化配置（界面 → 设置 → 模型）。
- 新增三类真实 LLM 能力：
  1. **图纸理解**：解析 SLDPRT 元数据 + 视图截图 → LLM 推断零件类别、关键工艺、推荐主视图朝向。
  2. **文本理解**：自动生成"技术要求/表面处理/材质说明"草稿，写入 SLDDRW 标题栏。
  3. **视觉质检**：把生成的 SLDDRW 转 PNG → 多模态 LLM → 给出 0~100 分 + 具体改进项 JSON，馈入 `drw_qc_loop` 的 `issues_to_fix.json`。
- 新增项目级配置 `config/app.yaml`（SolidWorks 路径、模板路径、输出路径、并发数）。
- 新增运行日志面板（QPlainTextEdit）实时显示子进程输出 + LLM 响应。
- 新增"批量任务表"（QTableView）：多 SLDPRT 排队 → 单文件进度条 + 总体进度条。
- **复用** `drw_generate_v5.py` / `drw_quality_check.py` / `drw_qc_loop.py` 作为子进程后端，不改动其接口。
- 提供端到端真实验证：用 `3D转2D测试图纸/LB26001-A-04-001.SLDPRT` 跑 GUI → 出 SLDDRW → 视觉质检 → 通过截图证明可用性。
- **BREAKING**：无（纯新增）。

## Impact
- Affected specs: `enforce-drawing-quality`（被 GUI 复用，但行为不变）。
- Affected code:
  - 新增 `app/` 目录（main.py / windows / widgets / services / config）
  - 新增 `app/services/llm_client.py`、`app/services/sw_runner.py`、`app/services/vision_qc.py`
  - 新增 `app/ui/main_window.py`、`app/ui/settings_dialog.py`、`app/ui/batch_table.py`、`app/ui/log_panel.py`
  - 新增 `requirements_app.txt`、`build_exe.spec`（PyInstaller 配置）
  - 新增 `config/llm.yaml.example`、`config/app.yaml.example`
  - 新增 `dist/sw_drawing_studio.exe`（打包产物）
  - 复用 `.trae/specs/enforce-drawing-quality/drw_generate_v5.py` 等不变

## ADDED Requirements

### Requirement: 桌面应用主窗口
系统 SHALL 提供一个 PySide6 主窗口，包含侧边导航（首页 / 批量出图 / AI 质检 / 设置 / 日志），主区域根据导航切换 QStackedWidget。

#### Scenario: 启动 EXE 后显示主窗口
- **WHEN** 用户双击 `sw_drawing_studio.exe`
- **THEN** 应用在 ≤ 5 秒内显示窗口，初始页为"首页"，状态栏显示"SolidWorks: 已连接"或"未连接"

### Requirement: 大模型可配置接入
系统 SHALL 允许在"设置 → 模型"页面配置 LLM 提供商、API Base、API Key、Model Name、温度、超时；保存后写入 `%APPDATA%/sw_drawing_studio/llm.yaml`，并通过"测试连接"按钮发起一次真实 chat completion 验证。

#### Scenario: 配置并测试 DeepSeek
- **WHEN** 用户填写 base_url=`https://api.deepseek.com/v1`、key=`sk-xxx`、model=`deepseek-chat`，点击"测试连接"
- **THEN** 应用真实调用 chat.completions，UI 显示模型返回的"OK"或错误提示与状态码

### Requirement: AI 图纸理解
系统 SHALL 在导入 SLDPRT 后调用 LLM，根据零件名 + 体积 + 包围盒 + 等轴测截图（多模态），返回零件类别 / 推荐主视图朝向 / 推荐比例。

#### Scenario: 导入 LB26001-A-04-001.SLDPRT
- **WHEN** 用户在"批量出图"中加入该零件并点击"AI 预分析"
- **THEN** UI 显示 LLM 返回的 JSON（类别="钣金件"、front_view="*前视"、scale="1:2"），用户确认后注入 v5 生成参数

### Requirement: AI 文本生成
系统 SHALL 调用 LLM 自动生成技术要求 / 表面处理 / 通用公差三段标题栏文本；用户可在"AI 质检"页面单击修改并写回 SLDDRW。

#### Scenario: 生成技术要求
- **WHEN** 用户点击"AI 生成技术要求"
- **THEN** LLM 返回 ≥ 3 条符合 GB/T 4458 的中文技术要求，UI 渲染并允许编辑

### Requirement: AI 视觉质检
系统 SHALL 把生成的 SLDDRW 渲染为 PNG，连同 12 项 quality_check JSON 一起送入多模态 LLM，请其给出综合评分（0–100）与具体改进项；评分 < 80 时自动重跑 `drw_qc_loop`。

#### Scenario: 视觉质检触发重生成
- **WHEN** v5 输出后视觉质检评分 = 65、列出"前视图偏左"等 3 条改进项
- **THEN** 应用把改进项写入 `issues_to_fix.json`，触发一次 v5 重生成，再做一次质检直至 ≥ 80 或达上限 3 轮

### Requirement: 批量出图
系统 SHALL 支持选择文件夹批量加入 SLDPRT，串行调用 v5 后端（避免 SolidWorks 多实例冲突），表格显示文件名 / 状态 / 评分 / 输出路径 / 错误。

#### Scenario: 批量 5 个零件
- **WHEN** 用户加入 5 个 SLDPRT 并点击"开始"
- **THEN** 进度条逐个推进，每完成一个写一行日志，结束后导出 `batch_report.csv`

### Requirement: 打包为 Windows EXE
系统 SHALL 提供 PyInstaller 打包脚本 `build_exe.spec`，最终产物 `dist/sw_drawing_studio.exe` 在干净的 Windows 10/11（无 Python）上可双击运行；体积 ≤ 200 MB。

#### Scenario: 在测试机运行 EXE
- **WHEN** 把 exe 拷到无 Python 的 Windows 10 测试机
- **THEN** 双击启动，主窗口显示，可完成"导入 SLDPRT → 出图"全流程（前提：测试机已装 SolidWorks 2025）

### Requirement: 真实文件验证
系统 SHALL 在交付前用 `3D转2D测试图纸/LB26001-A-04-001.SLDPRT` 完成一次端到端真实运行：导入 → AI 预分析 → v5 出图 → AI 视觉质检 → 评分 + 截图证据写入 `app_run_log.md`。

#### Scenario: 端到端真实跑通
- **WHEN** 验证流程结束
- **THEN** `app_run_log.md` 包含至少 1 张主窗口截图、1 张 AI 质检面板截图、1 个 SLDDRW 路径、1 段真实 LLM 响应原文，且最终 quality_check ≥ 10/12 且 vision_score ≥ 80

## MODIFIED Requirements
（无）

## REMOVED Requirements
（无）
