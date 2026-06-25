# Tasks

- [x] Task 1: 修 v5 — 去掉 NoteBlock 注入副作用
  - [x] SubTask 1.1: 在 `drw_generate_v5.py` 删除 `_insert_note_n(text, base_pos, n=5)` 的多次调用，改为单次插入
  - [x] SubTask 1.2: 技术要求改为单 Note 多行：`"技术要求：\n1. ...\n2. ...\n3. ..."`
  - [x] SubTask 1.3: 表面粗糙度只在右上角插 1 个 `其余 Ra3.2`
  - [x] SubTask 1.4: 基准 A 只在主视图左侧用 `InsertDatumTag2` 插 1 次

- [x] Task 2: 修 v5 — 补 GB 图框 + 标题栏
  - [x] SubTask 2.1: 在 sheet sketch 用 `CreateLine2` 画 A4 横式外框（10mm 边距）+ 内框（左 25 / 其余 5mm）
  - [x] SubTask 2.2: 在右下角画 13 键标题栏框线（180×40 mm，分 5×3 网格）
  - [x] SubTask 2.3: 标题栏内逐格用 `InsertNote` 写 13 个 CustomProperty 的中文标签 + `$PRP:"<key>"` 链接（保留 BlockInst 持久化路径）
  - [x] SubTask 2.4: 图框线设为粗实线图层 0.7 mm；网格线设为细实线 0.35 mm

- [x] Task 3: 修 v5 — 强制尺寸 + 清箭头
  - [x] SubTask 3.1: 调 `RunCommand(826)` 后再扫描视图边界框，对前视图用 `SketchManager.AddDimension` 触发线性尺寸抽取，目标 ≥ 5 个 DisplayDim
  - [x] SubTask 3.2: 关闭显示选项：`sw.SetUserPreferenceToggle(swDetailingShowDisplaceArrows=False)` 等所有视图箭头开关
  - [x] SubTask 3.3: 删除每个视图的 SolidWorks 默认 viewLabel（`view.SetVisible(False)` for label）

- [x] Task 4: 放宽 has_tech_note 检查
  - [x] SubTask 4.1: 在 `drw_quality_check.py` 把 has_tech_note 改为：单 Note 含 ≥3 行带 `1./2./3.` 编号即 pass
  - [x] SubTask 4.2: has_ra_note / has_datum_a 同步放宽：NoteBlock_total ≥ 1 且文本含关键字即 pass

- [x] Task 5: vision_loop.py 闭环器
  - [x] SubTask 5.1: 写 `.trae/specs/harden-v5-and-vision-loop/vision_loop.py`：
    流程：v5 → quality_check → vision_score → if score<80: 写 vision_issues.json + 重跑 v5（最多 3 轮）
  - [x] SubTask 5.2: 把每轮的 score / issues / SLDDRW 路径写入 `vision_loop_log.md`
  - [x] SubTask 5.3: 若 SW 未启动（`win32com.client.GetActiveObject("SldWorks.Application")` 失败）→ 明确报错退出码 2

- [x] Task 6: 真实闭环执行
  - [x] SubTask 6.1: 检查 SolidWorks 2025 进程是否运行（用户已启动），未启动则提示用户启动
  - [x] SubTask 6.2: 用 `LB26001-A-04-001.SLDPRT` 跑 vision_loop.py
  - [x] SubTask 6.3: 记录最终 score / quality_check 通过项数 / 用了几轮
  - [x] SubTask 6.4: 若 ≥ 80 在 `vision_loop_log.md` 标"PASS"；否则记录最近一次的具体 issues 与下一步建议

- [x] Task 7: 修复 Task 6 暴露的 3 项 checklist 失败（依据 spec mode 第七步）
  - [x] SubTask 7.1: 修 `drw_quality_check.py` 的 OpenDoc6 短路：在 OpenDoc6 失败时尝试 OpenDoc6 with options=257（DontDisplayReferenceWarnings|Silent）+ 短延时 retry 3 次；失败再回退到读 SLDDRW XML 头里的 sheet 元数据
  - [x] SubTask 7.2: 调查并修复 v5 的 sheet sketch 图框/标题栏未渲染：确认 `EditSheet()` 的正确调用顺序（必须在视图布局**之后**且 SaveAs 前进入）+ 切到 sheet 后再画线 + 验证 PDF/PNG 上图框可见
  - [x] SubTask 7.3: 重跑 vision_loop（≤ 1 轮即可），用新数据更新 vision_loop_log.md 末尾"## 二次验证"节
  - [x] SubTask 7.4: 根据二次验证结果勾选 checklist.md 中之前未通过的 3 项

# Task Dependencies
- Task 4 与 Task 1/2/3 可并行（不同文件）
- Task 5 依赖 Task 1/2/3/4
- Task 6 依赖 Task 5
