# 接入真实大模型 API 并完成可用性验证 Spec

## Why
build-3d-to-2d-desktop-app 已交付完成，但 LLM 配置仍是占位符 `sk-your-deepseek-key`，`test_connection` 返回 401。用户提供了真实可用的 OpenAI 兼容端点（`https://api.ccagent.cn/v1`）和两个真实模型（`doubao-seed-2.0-pro` 多模态、`glm-5.1` 文本），需要把 key 填入、跑通 `test_connection / chat / vision_score` 三条真实链路，并把视觉评分结果纳入端到端验证日志。

## What Changes
- 修改 `%APPDATA%/sw_drawing_studio/llm.yaml`：新增 provider `ccagent`，含 `base_url=https://api.ccagent.cn/v1`、`api_key=sk-REDACTED`、`model=glm-5.1`、`vision_model=doubao-seed-2.0-pro`，`active_provider: ccagent`。
- 修改 `config/llm.yaml.example`：把 `ccagent` 作为第 5 个示例 provider（key 字段写占位符 `sk-xxxxxxxx`），保持文件可分享。
- 真实跑 3 条链路：
  1. `LLMClient.test_connection()` → 期望 `ok=True`、`latency_ms<10000`
  2. `LLMClient.chat()` 用 `glm-5.1` 生成"技术要求 ≥3 条"
  3. `LLMClient.vision()` 用 `doubao-seed-2.0-pro` + `LB26001-A-04-001_v5.PDF→PNG` 给出视觉评分 JSON
- 把 3 条链路的真实响应原文 + 截图（如果重新启动 EXE 看到状态卡变绿）写到 `.trae/specs/wire-real-llm-api-and-verify/verify_log.md`。
- 若视觉评分 < 80，按既定流程触发一次 `drw_qc_loop` 重跑（如果 SolidWorks 当前可用）；若 SW 不可用，记录"机制就绪、当次未触发"。
- **BREAKING**：无（纯配置 + 验证）。

## Impact
- Affected specs: `build-3d-to-2d-desktop-app`（验收闭环）。
- Affected code:
  - `%APPDATA%/sw_drawing_studio/llm.yaml`（用户机器配置，覆写 active_provider 与 ccagent block）
  - `config/llm.yaml.example`（仓库示例文件，新增 ccagent 占位 block）
  - `.trae/specs/wire-real-llm-api-and-verify/verify_log.md`（新增）
  - `.trae/specs/wire-real-llm-api-and-verify/screenshots/`（新增可选）

## ADDED Requirements

### Requirement: 真实 API 配置注入
系统 SHALL 把 ccagent 提供商加入 `llm.yaml`，并设为 `active_provider`，确保 `build_default_client()` 自动选用。

#### Scenario: 重新加载客户端
- **WHEN** 调用 `build_default_client()`
- **THEN** 返回的 `LLMClient` 满足 `base_url=https://api.ccagent.cn/v1`、`model=glm-5.1`、`vision_model=doubao-seed-2.0-pro`、`api_key` 末 4 位 `spoT`

### Requirement: test_connection 真实通过
系统 SHALL 通过真实 HTTP 调用 chat.completions 完成连接测试，期望 `ok=True`。

#### Scenario: 真实 ping
- **WHEN** 执行 `LLMClient.test_connection()`
- **THEN** 返回 `(True, 'ok: ...', latency_ms)`，`latency_ms` 在 200~10000 范围

### Requirement: chat 文本生成真实可用
系统 SHALL 用 `glm-5.1` 生成 ≥ 3 条符合 GB/T 4458 的中文技术要求。

#### Scenario: 生成技术要求
- **WHEN** 输入 prompt"为一钣金件生成 3 条技术要求"
- **THEN** 返回非空字符串，包含至少 3 行（按行号或编号排列）

### Requirement: vision 多模态评分真实可用
系统 SHALL 用 `doubao-seed-2.0-pro` 对 SLDDRW 渲染 PNG 给出 0~100 分。

#### Scenario: 视觉评分
- **WHEN** 输入 `LB26001-A-04-001_v5.PDF` 渲染的 PNG + `qc.json`
- **THEN** 返回 `{score: int 0-100, issues: list, summary: str}`

### Requirement: 验证日志归档
系统 SHALL 把 3 条链路的真实响应原文与时间戳归档到 `verify_log.md`。

#### Scenario: 报告完整
- **WHEN** 验证流程结束
- **THEN** `verify_log.md` 至少包含：(1) ccagent provider 配置块；(2) test_connection 原文；(3) chat 返回的 ≥3 条技术要求原文；(4) vision_score JSON 原文；(5) 总结（pass/fail）

## MODIFIED Requirements
（无 — 仅注入配置 + 跑测试）

## REMOVED Requirements
（无）
