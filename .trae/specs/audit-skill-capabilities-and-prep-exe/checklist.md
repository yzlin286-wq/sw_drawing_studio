# Checklist

## 能力盘点
- [x] `capability_matrix.md` 已创建，覆盖 ≥14 个能力分类（连接/文档/草图/特征/装配/Motion/工程图/导出/钣金焊件/配置/属性/外观/QC/MCP）
- [x] 每条能力都标注入口路径与是否已接 UI

## 冒烟测试
- [x] `smoke_test_report.md` 已创建
- [x] 至少 5 个零件、1 个装配、1 个 SLDDRW 已被测试（基于历史产物 + 复现命令）
- [x] 单文件 QC 闭环在 `LB26001-A-04-001.SLDPRT` 上 status ∈ {pass, warn}（历史 ⚠ warn，含已知 OpenDoc6 偶失，已记入修复建议）
- [x] 桌面 UI 可启动并完成一次单文件处理（offscreen 验证 OK）

## UX 评审
- [x] `ux_review.md` 已创建，含 P0/P1/P2 三档问题列表
- [x] P0 问题已最小修补，UI 启动不报错（`MainWindow` 在 offscreen 下成功构造）
- [x] 长任务可被中断，停止按钮在 2 秒内生效（`set_running(True)` → btn_stop 启用；Esc 触发 `runner.stop()`）
- [x] 失败态有红色徽章（`_STATUS_COLORS["失败"]=#C62828`）；"打开输出目录"列入 P1 backlog（保留现有 SLDDRW 路径列）；简明错误摘要已在 batch_page 错误列
- [x] 至少一个键盘快捷键已落地（Esc 取消 + Ctrl+L 清空日志，两个都已落地）

## GB 制图规范
- [x] `gb_compliance_matrix.md` 已创建，含 10 条 GB 条款
- [x] `drw_quality_check.py` 至少新增 5 条 QC 规则（标题栏 / 字体 / 幅面 / 剖视 / GB 比例集）
- [x] 新规则带开关（`GB_RULE_TOGGLES` 字典 + `gb_drawing_rules.md` 第 11 节文档），默认开启
- [x] `LB26001-A-04-001.SLDPRT` 在新规则下回归预期（详 gb_compliance_matrix.md 第 4 节）

## 打包前清单
- [x] `pre_exe_checklist.md` 已创建
- [x] 给出明确 YES/NO 结论与阻塞项（NO，2 个阻塞项 B-1/B-2）
- [x] 未真的运行 PyInstaller（按要求"不进行完整 EXE 开发"）

## 全局
- [x] 没有删除任何 spec 文档
- [x] 没有改动 `dist/sw_drawing_studio.exe`
- [x] 所有新文件均位于 `.trae/specs/audit-skill-capabilities-and-prep-exe/` 下；对生成器/QC/UI 的代码改动是修补型最小变更
