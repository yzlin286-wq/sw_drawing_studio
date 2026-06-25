# Tasks

- [x] Task 1: 写入真实 API 配置
  - [x] SubTask 1.1: 把 ccagent provider 块（base_url / api_key / model / vision_model / temperature / timeout）写入 `%APPDATA%/sw_drawing_studio/llm.yaml`
  - [x] SubTask 1.2: 设置 `active_provider: ccagent`
  - [x] SubTask 1.3: 在仓库 `config/llm.yaml.example` 增加 ccagent 占位 block（key 用 `sk-xxxxxxxx`）

- [x] Task 2: 真实 test_connection
  - [x] SubTask 2.1: 跑 `python -c "from app.services import build_default_client; c=build_default_client(); print(c); print(c.test_connection())"`
  - [x] SubTask 2.2: 捕获返回 `(ok, msg, latency_ms)`，要求 `ok=True`

- [x] Task 3: 真实 chat（文本生成 — 技术要求）
  - [x] SubTask 3.1: 写探针 `_tmp_chat_probe.py`，调 `glm-5.1` 让其生成 3 条 GB 技术要求
  - [x] SubTask 3.2: 把模型原文落盘到 `verify_log.md`

- [x] Task 4: 真实 vision_score（多模态视觉质检）
  - [x] SubTask 4.1: 用 `slddrw_to_png` 把 `LB26001-A-04-001_v5.PDF`/`SLDDRW` 渲染为 PNG
  - [x] SubTask 4.2: 用 `doubao-seed-2.0-pro` 调 `vision_score()`，强制使用 `vision_model`
  - [x] SubTask 4.3: 解析 `{score, issues, summary}`，落盘 `<base>_vision.json` 与 `verify_log.md`

- [x] Task 5: 整理 verify_log.md 与最终交付
  - [x] SubTask 5.1: `.trae/specs/wire-real-llm-api-and-verify/verify_log.md` 包含 5 节（配置 / test_connection / chat / vision / 总结）
  - [x] SubTask 5.2: 同步更新 `app_run_log.md` 的 LLM 部分（追加"真实 API 已联通 ✅"段落）
  - [x] SubTask 5.3: tasks.md 与 checklist.md 全部勾选

# Task Dependencies
- Task 2 / 3 / 4 都依赖 Task 1
- Task 4 依赖 Task 2（先确认链路通）
- Task 5 依赖 Task 2 + 3 + 4
