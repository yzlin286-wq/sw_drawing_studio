# 真实模型接入与全量图纸视觉验证 Spec

## Why
v1.1 已交付，但 LLM 密钥已更换（旧密钥失效，仓库文档不记录明文密钥），且至今只在单个图纸 `LB26001-A-04-001` 上跑过 vision_score=65。用户要求：(1) 用新密钥接入真实模型；(2) 用 `3D转2D测试图纸/` 文件夹的全部真实 3D 图纸做一轮完整验证；(3) 视觉校验要同时对标 GB 制图标准 **和** 已有案例 2D 图片；(4) 自动生成的 2D 图纸要与原有 2D 图纸对标。当前缺少批量验证脚本、案例图库、对标对比能力。

## What Changes
- 更新 `%APPDATA%/sw_drawing_studio/llm.yaml` 与 `config/llm.yaml.example` 的 ccagent provider 密钥配置（仓库文档仅记录占位符）。
- 新增 `app/services/case_library.py`：把 `3D转2D测试图纸/` 中已有的 40 个 SLDDRW 渲染成 PNG 基准库，建立 `drw_output/case_library/<base>.png` + `case_index.json`。
- 增强 `app/services/vision_qc.py`：新增 `vision_score_with_reference()` 函数，支持"生成图 vs 案例图"双图对比模式，输出 `reference_diff` 字段（结构差异 + 相似度评分）。
- 新增 `app/services/batch_validator.py`：遍历 `3D转2D测试图纸/*.SLDPRT`，对每个跑 `full_pipeline` + `vision_score_with_reference`，汇总到 `drw_output/batch_validation/<batch_id>/`。
- 新增批量验证报告：`batch_summary.json` + `batch_report.md`，含每件 vision_score / 对标差异 / 通过率 / 失败清单。
- **BREAKING**：无（纯增强，不修改 v1.1 既有链路）。

## Impact
- Affected specs: `wire-real-llm-api-and-verify`（密钥更新）、`enhance-v1-1-complete-deliverable`（vision_qc 增强）、`harden-v5-and-vision-loop`（vision 闭环扩展）
- Affected code:
  - `config/llm.yaml.example`（ccagent key 占位符保持）
  - `%APPDATA%/sw_drawing_studio/llm.yaml`（用户配置，更新密钥）
  - `app/services/vision_qc.py`（新增 `vision_score_with_reference`）
  - `app/services/case_library.py`（**新增**）
  - `app/services/batch_validator.py`（**新增**）
  - `app/services/__init__.py`（导出新模块）
  - `drw_output/case_library/`（**新增**产物目录）
  - `drw_output/batch_validation/`（**新增**产物目录）

## ADDED Requirements

### Requirement: 真实模型密钥更新
系统 SHALL 把 ccagent provider 的 api_key 更新为本机私有密钥，并验证 `test_connection()` 返回 ok=True；仓库文档不得记录明文密钥。

#### Scenario: 密钥生效
- **WHEN** 调用 `build_default_client().test_connection()`
- **THEN** 返回 `(True, 'ok: ...', latency_ms)`，latency_ms < 10000

### Requirement: 案例 2D 图库构建
系统 SHALL 提供 `build_case_library()` 函数，把 `3D转2D测试图纸/` 中所有已有 SLDDRW 渲染成 PNG，建立案例基准库。

#### Scenario: 构建案例库
- **WHEN** 调用 `build_case_library()`
- **THEN** 在 `drw_output/case_library/` 下生成每个 SLDDRW 对应的 PNG（约 40 个），并写 `case_index.json` 记录 `{base_name, slddrw_path, png_path, file_size}`

#### Scenario: 案例库查询
- **WHEN** 给定一个 SLDPRT base_name 查询案例图
- **THEN** 若该 base_name 在案例库中存在，返回对应 PNG 路径；否则返回 None

### Requirement: 对标视觉评分
系统 SHALL 提供 `vision_score_with_reference()` 函数，在原有 `vision_score` 基础上增加"对标案例图"能力。

#### Scenario: 有案例图对标
- **WHEN** 输入生成图 PNG + 案例图 PNG
- **THEN** LLM 同时接收两张图，返回 JSON 含 `score`（0-100）、`issues`、`reference_diff`（{similarity: 0-100, structural_diff: str, missing_elements: list}）、`summary`

#### Scenario: 无案例图降级
- **WHEN** 输入生成图 PNG 但无对应案例图
- **THEN** 退化为单图评分（与 v1.1 `vision_score` 行为一致），`reference_diff` 字段为 `null`，不阻断

### Requirement: 批量全量验证
系统 SHALL 提供 `run_batch_validation()` 函数，遍历 `3D转2D测试图纸/*.SLDPRT`（排除 `~$` 临时文件），对每个执行 full_pipeline + vision_score_with_reference。

#### Scenario: 批量跑通
- **WHEN** 调用 `run_batch_validation(strategy="v6_recommended")`
- **THEN** 对每个 SLDPRT 生成独立 run_id，产物归集到 `drw_output/runs/<run_id>/`，并在 `drw_output/batch_validation/<batch_id>/` 下写汇总

#### Scenario: 单件失败不阻断批量
- **WHEN** 某个 SLDPRT 出图失败（如 SW OpenDoc6 失败）
- **THEN** 记录该件为 `failed`，继续处理下一个，不中断批量

### Requirement: 批量汇总报告
系统 SHALL 在批量验证结束后生成 `batch_summary.json` 与 `batch_report.md`。

#### Scenario: 报告内容完整
- **WHEN** 批量验证结束
- **THEN** `batch_summary.json` 含 `{batch_id, started_at, finished_at, total, success, warning, failed, items: [{base, run_id, vision_score, reference_diff, hard_fail, status}]}`；`batch_report.md` 含通过率统计 + 失败清单 + top 5 vision_score + bottom 5 vision_score

## MODIFIED Requirements

### Requirement: vision_qc 输出结构
v1.1 的 `vision_score()` 输出 `{score, issues, summary, png, png_ok, raw_text, error, threshold, pass, image_path, model, fix_suggestions}`。v1.2 新增 `vision_score_with_reference()` 输出在原结构基础上增加 `reference_diff: {similarity, structural_diff, missing_elements} | null` 与 `reference_png: str | null`。原 `vision_score()` 保持不变以兼容 v1.1 链路。

## REMOVED Requirements
（无）
