# sw_drawing_studio v2.3 RC 验证日志

**版本**: v2.3-rc  
**生成时间**: 2026-06-21  
**状态**: RC smoke PASS, real CAD validation pending  

---

## 1. 本轮结论

v2.3 当前已完成一轮不启动 SolidWorks 的轻量验证和 EXE smoke：

- JobRuntimeFacade / QProcess mock worker: PASS
- v2.3 UI 页面 smoke: PASS
- PyInstaller spec 资源与 hiddenimports 检查: PASS
- onefile EXE smoke: PASS
- frozen worker dispatch: PASS
- frozen pipeline script lookup: PASS
- GUI 启动 5 秒存活: PASS
- 单件真实 SolidWorks 出图 smoke: PASS (`LB26001-A-04-040`)

**发布判定**: NOT READY FOR RELEASE。  
原因是 v2.3 仅完成 1 件真实 CAD smoke；EXE 级真人模拟点击/截图验证、历史视觉审计全覆盖、129 full、2 小时 UI 稳定性尚未完成。

---

## 2. 本轮已验证项目

### 2.1 源码层轻量测试

| 命令 | 结果 | 说明 |
|---|---|---|
| `python test_v2_3_job_runtime.py` | PASS | mock worker 验证 QProcess/job event/facade contract |
| `python test_v2_3_build_spec.py` | PASS | v2.3 datas/hiddenimports 检查 |
| `python test_v2_3_resource_paths.py` | PASS | source/frozen worker 和 pipeline 路径分发检查 |
| `python test_v2_3_batch_facade_integration.py` | PASS | 批量页通过 JobRuntimeFacade 提交和渲染结果 |
| `python test_v2_3_job_queue_page.py` | PASS | 作业队列页面 smoke |
| `python test_v2_3_system_health_page.py` | PASS | 系统健康页面 smoke |
| `python test_v2_3_visual_audit_page.py` | PASS | 视觉审计页面 smoke |
| `python test_v2_3_logs_diagnostics_page.py` | PASS | 日志诊断页面 smoke |
| `python test_v2_3_drawing_review_workbench.py` | PASS | Drawing Review Workbench smoke |
| `python test_v2_3_single_part_page.py` | PASS | 单件页面 smoke |

### 2.2 v2.3 EXE smoke

命令：

```powershell
python smoke_v2_3_exe.py
```

结果：

| 检查 | 结果 | 证据 |
|---|---|---|
| EXE 存在 | PASS | `dist_v23_smoke/sw_drawing_studio_v23_smoke.exe` |
| EXE 大小 | INFO | 540,514,218 bytes (约 515.5 MiB) |
| `--worker mock` | PASS | 输出 `job_started/progress/heartbeat/job_finished` JSONL |
| `--pipeline-script-info drw_quality_check` | PASS | `_MEI.../.trae/specs/enforce-drawing-quality/drw_quality_check.py`, exists=true |
| GUI alive | PASS | 启动 5 秒后进程仍存活并可终止 |

新增 smoke 文件：

- `smoke_v2_3_exe.py`

为避免 EXE smoke 误启动 SolidWorks，新增安全诊断入口：

- `app/main.py --pipeline-script-info <script_key>`

该入口只打印 bundled pipeline 脚本路径和存在状态，不执行 pipeline 脚本。

### 2.3 v2.3 单件真实 CAD smoke

命令：

```powershell
python run_v2_3_real_validation.py --part ".\3D转2D测试图纸\LB26001-A-04-040.SLDPRT" --timeout-s 900 --max-rounds 1
```

结果文件：

- `drw_output/v23_validation/real_validation_smoke.json`
- `drw_output/v23_validation/LB26001-A-04-040_20260621_033346/manifest.json`

结果：

| 检查 | 结果 | 证据 |
|---|---|---|
| CAD worker returncode | PASS | `returncode=0` |
| Job events | PASS | `job_started=1`, `progress=5`, `heartbeat=6`, `job_finished=1`, `job_failed=0` |
| 核心产物归档 | PASS | run_dir 内存在 `SLDDRW/PDF/DXF/PNG` |
| QC/诊断归档 | PASS | run_dir 内存在 `LB26001-A-04-040_v5_qc.json`, `warnings.json`, `part_class.json`, `dimension_sidecar_result.json` |
| worker manifest | PASS | `schema=sw_drawing_studio.worker_manifest.v1`, `core_files_ok=true` |
| drawing_usable | PASS | `drawing_usable.pass=true`, `hard_fail=[]` |
| QC 全项 pass | WARN | `qc_pass=false`, `score_pass_count=10`, 存在标题栏/技术要求/剖视图/尺寸 warning |
| 3D-2D 一致性 | PASS with caveat | `model_2d_consistency.pass=true`, consistency=76，但提示缺剖视/局部放大和部分关键尺寸 |

本轮修复：

- `app/workers/cad_job_worker.py` 现在会把 legacy `drw_output/v5` 产物复制到 job `run_dir`，并写入 `manifest.json`。
- 这使 EXE/UI 的作业队列、日志诊断、视觉审计和 release 证据可以引用同一个自包含目录。

---

## 3. 已知构建风险

| 风险 | 当前状态 | 建议 |
|---|---|---|
| EXE 体积偏大 | v2.3 smoke EXE 约 515.5 MiB，明显大于 v1.9 约 135 MiB | 后续排查 Paddle/torch/ultralytics 引入链，考虑懒加载或可选插件化 |
| `qt_material` data collection warning | PyInstaller 输出 `qt_material` 不是 package，跳过 data collection | UI 有 fallback 主题；发布前需做视觉确认 |
| ML hook 噪声多 | warn 文件包含大量可选 missing module，主要来自 torch/paddle/scipy 等 | 分类为 optional/real missing，避免遗漏真正 runtime 缺包 |
| 中文/空格路径 | source/frozen 路径测试 PASS，但部分脚本仍依赖 shell 编码 | 继续保持 `PYTHONUTF8=1` 和 `child_process_env()`，验证脚本避免管道编码假阴性 |

---

## 4. v2.2 真实验证基线

v2.3 尚未重跑真实 CAD 全链路；当前真实验证基线来自 v2.2：

| 验证集 | 结果文件 | 当前证据 |
|---|---|---|
| 024/040 | `drw_output/v22_validation/024_040_result.json` | pass=true, deliverable_count=1 |
| core_12 Vision QC v4 | `drw_output/v22_validation/vision_qc_v4/core_12_summary.json` | total=12, pass=12, production mode, fallback=0 |
| LB26001_36 | `drw_output/v22_validation/lb26001_36_status.json` | 36/36 deliverable, rate=100% |
| medium_30 | `drw_output/v22_validation/medium_30_status.json` | 30/30 deliverable, rate=100% |

这些证据证明 v2.2 基线较强，但不能自动证明 v2.3 release-ready，因为 v2.3 修改了进程隔离、UI 调用入口、frozen runtime 路径和打包方式。

---

## 5. v2.3 剩余发布门槛

以下项目必须完成后才能写 `release_log_v2_3.md` 并判定 release-ready：

- [ ] 真实 SolidWorks 验证: 024/040 至少 1 件恢复可交付
- [x] 真实 SolidWorks smoke: LB26001-A-04-040 1/1 可交付，run_dir 证据完整
- [ ] EXE 级 UI 真人模拟点击/截图验证：首页、单件、批量、作业队列、系统健康、视觉审计、AI 质检、BOM、日志诊断
- [ ] 真实 SolidWorks 验证: core_12 12/12 可交付，vision_qc_v5 12/12
- [ ] 真实 SolidWorks 验证: LB26001_36 36/36 可交付
- [ ] 真实 SolidWorks 验证: medium_30 30/30 可交付
- [ ] 历史产物 Visual Audit 覆盖率 100%
- [ ] 输出 `drw_output/visual_audit_report_v2_3.xlsx`
- [ ] 129 full 可交付率 >= 98%，永久卡死=0
- [ ] UI 连续运行 2 小时不假死
- [ ] 任意单个 job timeout 不拖死 UI
- [ ] EXE 真实工作流 smoke 通过
- [ ] 输出 `release_log_v2_3.md`

---

## 6. 下一步建议

1. 用 EXE 启动真实 UI，进行截图 + 模拟点击 walkthrough，覆盖所有主页面。
2. 用 EXE/UI 提交 mock 长任务 20 分钟，验证 Job Queue 不假死。
3. 用 EXE/UI 提交真实 SolidWorks 小批验证：024/040 和 core_12。
4. 修复 040 当前 QC warning 中最影响交付的项目：标题栏字段、技术要求、Ra/Datum/剖视策略、关键尺寸覆盖。
5. 若小批通过，再跑 LB26001_36 和 medium_30。
6. 使用 Visual Audit 页面/worker 扫描历史产物，补齐当前 index 中缺失 vision QC 的 4 个 base。
7. 最后跑 129 full 和 2 小时 UI stability，并生成最终 release log。
