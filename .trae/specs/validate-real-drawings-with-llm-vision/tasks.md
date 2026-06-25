# Tasks

- [x] Task 1: 更新 LLM 密钥并验证真实连通
  - [x] SubTask 1.1: 更新 `%APPDATA%/sw_drawing_studio/llm.yaml` 的 ccagent api_key 为本机私有密钥（仓库文档已脱敏）
  - [x] SubTask 1.2: `config/llm.yaml.example` 的 ccagent block 保持占位符 `sk-xxxxxxxx`（可分享）
  - [x] SubTask 1.3: 真实跑 `build_default_client().test_connection()`，期望 ok=True、latency_ms<10000
  - [x] SubTask 1.4: 真实跑 `chat()` 用 glm-5.1 生成 1 句话 + `vision()` 用 doubao-seed-2.0-pro 识别 1 张 PNG
  - [x] SubTask 1.5: 把 3 条链路真实响应归档到 `verify_log_v1_2.md`

- [x] Task 2: 构建案例 2D 图库
  - [x] SubTask 2.1: 新增 `app/services/case_library.py`，提供 `build_case_library()` 与 `find_case_png(base_name)`
  - [x] SubTask 2.2: 遍历 `3D转2D测试图纸/*.SLDDRW`（约 40 个），用 PyMuPDF 把对应 PDF 渲染成 PNG（若无 PDF 则用 SLDDRW 自身渲染兜底）
  - [x] SubTask 2.3: 产物写入 `drw_output/case_library/<base>.png` + `case_index.json`
  - [x] SubTask 2.4: 真实跑一次 `build_case_library()`，验证 PNG 数量 ≥ 30 且每个 file_size > 5KB

- [x] Task 3: 增强 vision_qc 支持对标对比
  - [x] SubTask 3.1: 在 `app/services/vision_qc.py` 新增 `vision_score_with_reference(slddrw_path, qc_json_path, llm, reference_png_path=None)`
  - [x] SubTask 3.2: 当 `reference_png_path` 存在时，LLM messages 同时附 2 张图（生成图 + 案例图），prompt 要求输出 `reference_diff: {similarity, structural_diff, missing_elements}`
  - [x] SubTask 3.3: 当 `reference_png_path` 为 None 时，退化为单图评分，`reference_diff=null`
  - [x] SubTask 3.4: 真实用 1 张生成图 + 1 张案例图跑通 `vision_score_with_reference()`，验证返回 JSON 含 `reference_diff`

- [x] Task 4: 批量全量验证脚本
  - [x] SubTask 4.1: 新增 `app/services/batch_validator.py`，提供 `run_batch_validation(strategy="v6_recommended", limit=None)`
  - [x] SubTask 4.2: 遍历 `3D转2D测试图纸/*.SLDPRT`（排除 `~$` 临时文件），对每个调 `full_pipeline` + `vision_score_with_reference`
  - [x] SubTask 4.3: 单件失败 try/except 包裹，记录 `failed` 不中断批量
  - [x] SubTask 4.4: 每件的 run_id 与产物归集到 `drw_output/runs/<run_id>/`（复用 v1.1 机制）
  - [x] SubTask 4.5: 批量级汇总写入 `drw_output/batch_validation/<batch_id>/batch_summary.json`

- [x] Task 5: 批量汇总报告
  - [x] SubTask 5.1: 在 `batch_validator.py` 新增 `write_batch_report(batch_id)` 生成 `batch_report.md`
  - [x] SubTask 5.2: 报告含：通过率统计 / 失败清单 / top 5 vision_score / bottom 5 vision_score / 对标差异典型样例
  - [x] SubTask 5.3: 真实跑一次小批量验证（limit=3），验证 `batch_summary.json` + `batch_report.md` 结构完整

- [x] Task 6: 全量验证执行与归档
  - [x] SubTask 6.1: 启动 SolidWorks，跑 `run_batch_validation(strategy="v6_recommended")` 全量（约 130 个 SLDPRT）
  - [x] SubTask 6.2: 监控进度，记录失败项到 `exceptions.log`
  - [x] SubTask 6.3: 验证结束后生成最终 `batch_report.md` + `batch_summary.json`
  - [x] SubTask 6.4: 把全量验证结果归档到 `validate-real-drawings-with-llm-vision/full_validation_log.md`

# Task Dependencies
- Task 2 依赖 Task 1（需要 LLM 可用才能验证案例库构建脚本，但案例库构建本身不需要 LLM，可并行）
- Task 3 依赖 Task 1（需要真实 LLM 调用）
- Task 4 依赖 Task 1 + Task 2 + Task 3（需要 full_pipeline + case_library + vision_score_with_reference）
- Task 5 依赖 Task 4
- Task 6 依赖 Task 5（全量跑需要报告机制就绪）
- Task 1 与 Task 2 可并行
