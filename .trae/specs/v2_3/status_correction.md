# v2.3 状态修正文档

**生成时间**: 2026-06-21  
**版本**: v2.3-rc1 (Release Candidate 1)  
**状态**: **NOT READY FOR RELEASE**

---

## 当前状态总结

### ✅ Task 1-5: Service Layer Complete

以下服务模块已创建并通过基础语法检查，但**未经 UI 集成验证**：

#### Task 1: Job Runner 进程隔离
- ✅ `app/services/job_event_bus.py` - JobEvent 事件总线
- ✅ `app/services/job_queue.py` - JobQueue 作业队列
- ✅ `app/services/job_runner.py` - JobRunner (QProcess 封装)
- ✅ `app/workers/cad_job_worker.py` - CAD 作业 worker
- ✅ `app/workers/vision_audit_worker.py` - 视觉审计 worker
- ✅ `app/workers/batch_job_worker.py` - 批量作业 worker

**状态**: Service implemented, **UI 集成未完成**

#### Task 2: SW Session Supervisor v2
- ✅ `app/services/sw_watchdog.py` - SW 进程监控
- ✅ `app/services/sw_recovery_policy.py` - 恢复策略
- ✅ `app/services/sw_session_supervisor.py` - 增强版 supervisor

**状态**: Service implemented, **UI 集成未完成**

#### Task 3: DialogGuard 生产化
- ✅ `app/services/sw_dialog_guard.py` - DialogGuardV2 (stage-aware, dry-run, whitelist)

**状态**: Service implemented, **UI 集成未完成**

#### Task 4: Generated Output Visual Audit
- ✅ `app/services/generated_output_scanner.py` - 产物扫描器
- ✅ `app/services/visual_audit_service.py` - 视觉审计服务
- ✅ `app/services/visual_audit_reporter.py` - 报告生成器

**状态**: Service implemented, **UI 集成未完成**

#### Task 5: Vision QC v5
- ✅ `app/services/vision_qc_v5.py` - Vision QC v5
- ✅ `app/services/vision_evidence_fusion.py` - 证据融合
- ✅ `app/services/vision_false_positive_filter.py` - 误报过滤
- ✅ `app/services/vision_issue_tracker.py` - 问题追踪器

**状态**: Service implemented, **UI 集成未完成**

---

### ❌ Task 6-12: Pending (未完成)

#### Task 6: UI 3.0 Dashboard
- ❌ SW 状态面板未实现
- ❌ 今日任务/质量分布/视觉审计卡片未实现
- ❌ 数据来源未接入 JobEventBus/sw_session.json

**验收标准未达成**:
- [ ] UI 显示 SW connected/disconnected/recovering/stuck
- [ ] UI 显示 sw_pid/revision/addin_ping/active_doc/transaction_status
- [ ] UI 显示今日任务/质量分布/视觉审计 pending/最近失败 Top 5
- [ ] 数据来源必须是 JobEventBus/sw_session.json/manifest，不得直接调用 COM

#### Task 7: Job Queue 页面
- ❌ `app/ui/job_queue_page.py` 未创建
- ❌ pause/resume/cancel/retry/skip/open run_dir 未实现
- ❌ stdout JSONL live view 未实现
- ❌ sw_session timeline 未实现
- ❌ 未接入 JobRunner/QProcess

**验收标准未达成**:
- [ ] 表格字段: job_id/part/stage/progress/status/retry_count/duration/sw_pid/last_event/action
- [ ] 支持 pause queue/resume queue/cancel current job/retry failed job/skip current job/open run_dir
- [ ] stdout JSONL live view 实时显示 worker 输出
- [ ] sw_session timeline 显示 transaction 事件
- [ ] 必须接入 JobRunner/QProcess，UI 线程不阻塞

#### Task 8: Visual Audit 页面
- ❌ `app/ui/visual_audit_page.py` 未创建
- ❌ 扫描历史产物未实现
- ❌ 只审计未审计/重审 failed/need_review 未实现
- ❌ issue_bucket 筛选未实现
- ❌ 导出 visual_audit_report.xlsx 未实现
- ❌ 未调用 visual_audit_worker.py

**验收标准未达成**:
- [ ] 扫描 drw_output/runs, v5, v22_validation, batch_reports
- [ ] 支持只审计未审计/重审 failed/need_review
- [ ] 支持按 issue_bucket 筛选
- [ ] 支持导出 visual_audit_report.xlsx
- [ ] 后端调用 visual_audit_worker.py，不在 UI 线程跑 OCR/YOLO

#### Task 9: Drawing Review 页面升级
- ❌ source/severity/human_review 筛选未实现
- ❌ PNG/PDF zoom/pan 未实现
- ❌ bbox overlay 未实现
- ❌ OCR/YOLO/template/geometry layer toggle 未实现
- ❌ evidence/fix_suggestion/manual_confirm/mark_false_positive 未实现
- ❌ 人工确认未写入 human_review.json 或 issue_tracker

**验收标准未达成**:
- [ ] 支持 source/severity/human_review 筛选
- [ ] PNG/PDF 预览支持 zoom/pan
- [ ] bbox overlay 支持 OCR/YOLO/template/geometry 分层开关
- [ ] 右侧显示 evidence/fix_suggestion/auto_fix/manual_confirm/mark_false_positive
- [ ] 点击 issue 可定位图纸区域并看到证据来源
- [ ] 人工确认写入 human_review.json 或 issue_tracker

#### Task 10: System Health 页面
- ❌ health_check 未分组 (SolidWorks/Vision/Data/License/UI-Worker)
- ❌ 检查项未扩展 (SW running/Add-in Ping/OpenDoc6 test/DialogGuard/fitz/cv2/ultralytics/paddleocr/yolo weights/vision model/Document Manager key)
- ❌ 每项未显示 pass/warning/fail + fix_suggestion

**验收标准未达成**:
- [ ] 按 SolidWorks/Vision/Data/License/UI-Worker 分组
- [ ] 检查项包括: SW running/Add-in Ping/OpenDoc6 test/DialogGuard/fitz/cv2/ultralytics/paddleocr/yolo weights/vision model/Document Manager key
- [ ] 每项有 pass/warning/fail + fix_suggestion
- [ ] SW 未启动时整个 UI 不 fail，只标记"制图功能不可用，历史查看可用"

#### Task 11: Logs & Diagnostics 页面
- ❌ `app/ui/logs_diagnostics_page.py` 未创建
- ❌ 按 job/run 查看日志未实现
- ❌ sw_session.json/vision_qc_v5.json/final_quality.json 展示未实现
- ❌ 一键生成 diagnostics zip 未实现
- ❌ 复制诊断摘要未实现

**验收标准未达成**:
- [ ] 按 job/run 查看 run.log/sw_session.json/vision_qc_v5.json/final_quality.json/worker stdout/stderr
- [ ] 一键生成 diagnostics zip
- [ ] 复制诊断摘要
- [ ] 任意失败件 30 秒内生成完整诊断包

#### Task 12: 全量验证
- ❌ 024/040 验证未完成
- ❌ core_12 验证未完成
- ❌ LB26001_36 验证未完成
- ❌ medium_30 验证未完成
- ❌ 历史产物 Visual Audit 未完成
- ❌ 129 full 验证未完成
- ❌ validation_log_v2_3.md 未生成
- ❌ visual_audit_report_v2_3.xlsx 未生成
- ❌ release_log_v2_3.md 未生成

**验收标准未达成**:
- [ ] 024/040 至少 1 件恢复可交付
- [ ] core_12 12/12 可交付，vision_qc_v5=12/12
- [ ] LB26001_36 36/36 可交付
- [ ] medium_30 30/30 可交付
- [ ] 历史产物视觉审计覆盖率 100%
- [ ] 129 full 可交付率 ≥98%，永久卡死=0
- [ ] 输出 validation_log_v2_3.md/visual_audit_report_v2_3.xlsx/release_log_v2_3.md

---

## v2.3 PASS 条件 (未达成)

以下所有条件必须满足才能判定 v2.3 PASS：

- [ ] UI 连续运行 2 小时不假死
- [ ] 任意单个 job timeout 不拖死 UI
- [ ] 024/040 自动恢复
- [ ] LB26001_36 36/36 可交付
- [ ] medium_30 30/30 可交付
- [ ] 历史产物视觉审计覆盖率 100%
- [ ] 所有 vision issue 都有 bbox/source/confidence/fix_suggestion/evidence
- [ ] UI 可查看 job queue/visual audit/review workbench/system health
- [ ] diagnostics zip 可生成
- [ ] EXE smoke 通过

---

## 禁止事项

1. **不允许 release** - Task 6-12 未完成，v2.3 不是 PASS 状态
2. **不允许勾选未验证项** - 未经 UI 验证/EXE 验证/2 小时稳定性验证的项不得勾选
3. **不允许跳过 UI 集成** - 所有 service 必须通过 UI 页面调用并验证
4. **不允许跳过真实验证** - 必须按顺序跑 024/040 → core_12 → LB26001_36 → medium_30 → visual audit → 129 full

---

## 下一步行动

### 优先级 1: UI 集成 (Task B-I)
1. Task B: 创建 `app/services/job_runtime_facade.py` 统一 UI 调用入口
2. Task C: 实现 Dashboard 页面
3. Task D: 实现 Job Queue 页面
4. Task E: 实现 Visual Audit 页面
5. Task F: 升级 Drawing Review 页面
6. Task G: 实现 System Health 页面
7. Task H: 实现 Logs & Diagnostics 页面
8. Task I: 主窗口集成 main_window.py

### 优先级 2: Mock 验证 (Task J)
9. Task J: 创建 mock_long_job_worker.py 验证 UI 20 分钟不假死

### 优先级 3: 真实验证 (Task K)
10. Task K: 按顺序跑 024/040 → core_12 → LB26001_36 → medium_30 → visual audit → 129 full

### 优先级 4: 发布判定 (Task L)
11. Task L: 只有满足所有 PASS 条件才能写 v2.3 PASS

---

## 结论

**v2.3 当前状态**: Service layer complete, UI 集成未完成, 验证未完成  
**v2.3 当前判定**: **NOT PASS**  
**v2.3 当前允许 release**: **NO**

必须完成 Task B-L 所有任务，并满足所有 PASS 条件后，才能判定 v2.3 PASS 并允许 release。
