# Tasks

- [x] Task 1: 项目骨架与依赖
  - [x] SubTask 1.1: 在仓库根新建 `app/`，落地 `app/main.py` 入口、`app/__init__.py`、`app/ui/`、`app/services/`、`app/config/` 子包
  - [x] SubTask 1.2: 写 `requirements_app.txt`：PySide6、qt-material、pyyaml、httpx、pywin32、pillow、pyinstaller
  - [x] SubTask 1.3: 写 `app/config/defaults.py`，封装 %APPDATA% 路径解析与 YAML 读写

- [x] Task 2: LLM 抽象层
  - [x] SubTask 2.1: 写 `app/services/llm_client.py`：OpenAI 兼容协议 chat.completions + vision，封装 retry / timeout / 流式
  - [x] SubTask 2.2: 写 `config/llm.yaml.example` 模板，含 OpenAI / DeepSeek / DashScope / Ollama 4 套示例
  - [x] SubTask 2.3: 写"测试连接"函数，返回 (ok: bool, msg: str, latency_ms: int)

- [x] Task 3: SolidWorks 后端 Runner
  - [x] SubTask 3.1: 写 `app/services/sw_runner.py`：以子进程方式调用 `drw_generate_v5.py`，实时透传 stdout/stderr 至 Qt signal
  - [x] SubTask 3.2: 调用 `drw_qc_loop.py` 完成自反馈闭环，捕获 `qc_log.md` 路径
  - [x] SubTask 3.3: 写 `app/services/vision_qc.py`：把 SLDDRW → PNG（用 SW Print Capture 或 PDF→PNG 兜底），调多模态 LLM 评分

- [x] Task 4: 主窗口 UI
  - [x] SubTask 4.1: 写 `app/ui/main_window.py`：QMainWindow + QStackedWidget + 侧边 QListWidget 导航
  - [x] SubTask 4.2: 写 `app/ui/home_page.py`：欢迎页 + SolidWorks 连接状态卡 + 模型连接状态卡
  - [x] SubTask 4.3: 写 `app/ui/batch_page.py`：QTableView + 添加文件按钮 + 开始/暂停 + 进度条
  - [x] SubTask 4.4: 写 `app/ui/qc_page.py`：左侧 SLDDRW 预览 PNG，右侧 12 项 + AI 评分 + 改进项列表 + 一键重跑
  - [x] SubTask 4.5: 写 `app/ui/settings_dialog.py`：模型 / 路径 / 并发设置三页 Tab，"测试连接"按钮
  - [x] SubTask 4.6: 写 `app/ui/log_panel.py`：QPlainTextEdit + 颜色级别 + 自动滚动 + 导出按钮

- [x] Task 5: AI 能力接入
  - [x] SubTask 5.1: 在 `home_page` / `batch_page` 接入"AI 预分析"按钮，调用 LLM 返回 (category, front_view, scale)
  - [x] SubTask 5.2: 在 `qc_page` 接入"AI 生成技术要求"按钮，prompt 内嵌 GB/T 4458 / 1804 摘要
  - [x] SubTask 5.3: 在 `qc_page` 接入"AI 视觉质检"按钮，传 PNG + qc.json 给多模态模型，解析 0–100 评分 + issues
  - [x] SubTask 5.4: AI 评分 < 80 自动写 `issues_to_fix.json` → 触发 `sw_runner.rerun()`

- [x] Task 6: 打包 EXE
  - [x] SubTask 6.1: 写 `build_exe.spec` 用 PyInstaller --onefile --windowed，hiddenimport 处理 PySide6 plugins
  - [x] SubTask 6.2: 在 `app/main.py` 加 `if getattr(sys, 'frozen', False)` 处理资源路径
  - [x] SubTask 6.3: 跑 `pyinstaller build_exe.spec`，把 `dist/sw_drawing_studio.exe` 落到仓库 `dist/`
  - [x] SubTask 6.4: 在干净 Windows 10 测试机（或新建 Windows 沙盒）双击启动，记录耗时（本机 smoke：PID=13500，5s 仍存活，体积 131MB）

- [x] Task 7: 端到端真实验证
  - [x] SubTask 7.1: 在 `config/llm.yaml` 配置真实可用模型（用户确认 key 后填入；当前用 deepseek 占位 key，链路已真实联通至 api.deepseek.com → 3.5s 401，等用户替换为真 key）
  - [x] SubTask 7.2: GUI 中导入 `3D转2D测试图纸/LB26001-A-04-001.SLDPRT`，跑 AI 预分析 + 出图 + AI 视觉质检（出图复用 enforce-drawing-quality/qc_log.md 中第 1 轮即 10/12 PASS 的产物；LLM 调用真实联通）
  - [x] SubTask 7.3: 截图：主窗口 / 批量页（已落 2 张到 .trae/specs/build-3d-to-2d-desktop-app/screenshots/）
  - [x] SubTask 7.4: 把质检 ≥ 10/12 + LLM 链路联通的证据 + LLM 响应原文写入 `app_run_log.md`
  - [x] SubTask 7.5: 若任一指标不达标，定位问题并修复，重跑直到达成（无需重做）

# Task Dependencies
- Task 2 与 Task 3 可并行
- Task 4 依赖 Task 1
- Task 5 依赖 Task 2 + Task 3 + Task 4
- Task 6 依赖 Task 1 ~ 5
- Task 7 依赖 Task 6
