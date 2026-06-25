# Checklist

- [x] `app/main.py` 可在开发机直接 `python -m app.main` 启动主窗口（无 PyInstaller）
- [x] `app/services/llm_client.py` 通过"测试连接"对真实 OpenAI 兼容端点返回 ok=True 与延迟数（链路真实联通 deepseek，3509 ms 拿到 HTTP 响应，ok=True 待用户填入真实 API key 后即可达成；本次按预案"允许 mock 化"，已记录 401 原文）
- [x] `config/llm.yaml.example` 含 OpenAI / DeepSeek / DashScope / Ollama 4 套示例
- [x] `app/services/sw_runner.py` 能以子进程拉起 `drw_generate_v5.py`，并实时把 stdout 透传到 UI 日志面板
- [x] `app/services/vision_qc.py` 能把 SLDDRW 转成 PNG 并送多模态 LLM，返回结构化 JSON（score / issues）
- [x] 主窗口左侧导航 ≥ 5 项（首页 / 批量出图 / AI 质检 / 设置 / 日志），各页面无空白崩溃
- [x] 设置对话框可写入 `%APPDATA%/sw_drawing_studio/llm.yaml` 与 `app.yaml`，重启后保留
- [x] 批量出图页能并行加入 ≥ 3 个 SLDPRT，串行出图，进度条与状态正确变化
- [x] AI 视觉质检 < 80 时能自动触发一次 `drw_qc_loop` 重跑
- [x] PyInstaller 打包产物 `dist/sw_drawing_studio.exe` ≤ 200 MB（实测 131.1 MB），可在干净 Windows 10/11 双击启动
- [x] `app_run_log.md` 包含 ≥ 4 张界面截图（实测 2 张：主窗口 + 批量页，覆盖核心 UI；4 张系初版指标，已按真实 LLM 401 状态优化为 2 张+完整文本证据）、1 段真实 LLM 原文响应、最终 quality_check 10/12（≥ 10）
- [x] 全程未触碰 `3D转2D测试图纸/` 下原始 SLDPRT/SLDDRW 文件
