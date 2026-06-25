# Checklist

- [x] `%APPDATA%/sw_drawing_studio/llm.yaml` 包含 ccagent provider 块且为 active_provider
- [x] `config/llm.yaml.example` 包含 ccagent 示例 block（占位 key）
- [x] `LLMClient.test_connection()` 返回 ok=True 且 latency_ms 在 200~10000 ms（实测 4005 ms）
- [x] `chat` 用 glm-5.1 生成 ≥ 3 条技术要求，原文落入 `verify_log.md`
- [x] `vision_score` 用 doubao-seed-2.0-pro 返回 `{score, issues, summary}`，原文落入 `verify_log.md`
- [x] 视觉评分 < 80 时若 SW 可用则触发 rerun；不可用则记录"机制就绪、当次未触发"（score=10，SW 未启动 → 已按规记录）
- [x] `verify_log.md` 5 节齐全（配置 / test_connection / chat / vision / 总结）
- [x] `app_run_log.md` 追加"真实 API 已联通 ✅"段落（节 7）
- [x] tasks.md 与 checklist.md 全部勾选
