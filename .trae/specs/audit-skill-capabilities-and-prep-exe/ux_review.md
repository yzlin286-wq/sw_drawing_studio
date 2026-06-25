# UX Review — SW Drawing Studio 桌面应用

> 时间：2026-06-18
> 评审范围：[app/ui/](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/app/ui)（main_window / home_page / batch_page / qc_page / log_panel / settings_dialog）
> 参考原则：Nielsen 10 项可用性启发 + Microsoft Fluent / GNOME HIG 桌面长任务模式（清晰状态反馈、可中断、错误可恢复、防错、键盘可达、空/加载/失败三态）

---

## 1. 8 维度评审

### 1.1 状态可见性
- ✅ `statusBar()` 用于显示就绪/出图中
- ✅ `progress` QProgressBar 显示批量百分比
- ⚠ 工具栏的"开始出图"在跑批时未禁用，用户可重复点击
- ⚠ 首页 SW 连接状态卡片只在 init 时检测一次，无手动刷新

### 1.2 用户控制
- ❌ **批量页无"停止"按钮**（虽 `SwRunner.stop()` 存在，但 UI 不暴露）
- ⚠ 当前运行的子进程被 terminate 后，UI 仍在子进程信号未 finish 时停留 1-2s
- ✅ 日志面板有"清空 / 暂停滚动 / 导出"
- ❌ QC 页"AI 视觉质检"按钮在跑分中不禁用

### 1.3 错误处理
- ⚠ 批量页"错误"列只显字符串，长错误被截断；缺"复制错误"或"打开 _qc.json"动作
- ⚠ "失败"行无法快速跳到对应输出目录
- ✅ Vision 失败有 toast 文案（在日志面板）
- ⚠ 模型未配置时仅状态栏一行提示，进入 QC 页才看到红字

### 1.4 一致性
- ✅ 颜色语义已部分到位（log_panel: ERROR=红, WARN=橙, INFO=黑）
- ❌ 批量页"状态"列纯文本（待处理/排队中/完成/失败），无颜色徽章
- ⚠ 工具栏图标缺失（仅文本），与首页大按钮风格不一致

### 1.5 防错
- ⚠ 批量页空列表时点"开始出图"也会触发，仅打印 `[batch] 开始出图，共 0 个文件` 然后什么都不做
- ⚠ 跑批途中关闭窗口无确认弹窗，可能丢失进度
- ⚠ 文件已存在的输出会被静默覆盖，无确认

### 1.6 空 / 加载 / 失败 三态
- ❌ 批量页空表格无引导文案
- ⚠ QC 页未选 SLDDRW 时 preview 仅显"（无预览）"，无"请先出图后选择 SLDDRW 文件"指引
- ✅ 加载态在 vision/tech_text 已有 "请稍候…"

### 1.7 键盘可达
- ✅ `Ctrl+Q` 退出（StandardKey.Quit）
- ❌ 缺 `Esc` 取消当前批量
- ❌ 缺 `Ctrl+L` 清空日志
- ⚠ 设置对话框 Tab 顺序未显式设置

### 1.8 文档可达
- ❌ "帮助" 菜单仅"关于…"，无"GB 制图规范"快捷链接
- ❌ 无内嵌新手引导

---

## 2. P0 / P1 / P2 问题清单

### P0（阻断流程或显眼缺陷）
- **P0-1** 批量页缺"停止"按钮 → 长任务无法人工中断（spec 要求 2s 内回 idle）
- **P0-2** 批量页"开始出图"在空列表时仍可点 → 无意义触发
- **P0-3** 批量页"状态"列无颜色徽章 → 完成/失败混在一起难以肉眼扫
- **P0-4** 缺 `Esc` 取消、`Ctrl+L` 清空日志快捷键 → 键盘流断
- **P0-5** 首页 SW 状态无"刷新"按钮 → 启动 SolidWorks 后必须重启 App 才能更新

### P1（影响体验但不阻断）
- **P1-1** 失败行无"打开输出目录 / 复制错误 / 重试"行内动作
- **P1-2** 跑批中"开始出图"按钮不禁用
- **P1-3** 空状态文案缺失（批量页/QC 页）
- **P1-4** 帮助菜单缺"打开规范文档"
- **P1-5** 工具栏图标缺失

### P2（润色）
- **P2-1** 设置对话框 Tab 顺序
- **P2-2** 关闭窗口时如有任务在跑，弹确认
- **P2-3** 输出已存在时弹覆盖确认

---

## 3. 本次落地的 P0 微调（最小修补）

| 编号 | 文件 | 修改 |
|---|---|---|
| Patch-A | [batch_page.py](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/app/ui/batch_page.py) | 新增"停止"按钮（默认禁用，运行时启用），暴露 `request_stop` 信号；新增 `set_running(bool)` 用于切换按钮可用态；空状态文案 placeholder；颜色徽章 |
| Patch-B | [main_window.py](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/app/ui/main_window.py) | 监听 `batch_page.request_stop` → `self.runner.stop()` + 状态栏"已停止"；批量开始/结束时切换 `set_running`；新增全局 `Esc` 触发 stop、`Ctrl+L` 清空日志；批量页空列表防御 |
| Patch-C | [home_page.py](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/app/ui/home_page.py) | 在 SW 状态卡片加"刷新"按钮，调用 `_refresh_sw_status()` |
| Patch-D | [main_window.py](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/app/ui/main_window.py) | 帮助菜单加"打开 GB 制图规范"项，指向 `gb_drawing_rules.md` |

P1/P2 不在本次范围（见 backlog）。

---

## 4. 验证

- 修补后启动：`python -m app.main`（如本会话不在线 run，由用户在桌面验证）
- 验证点：
  1. 批量页底部出现"停止"按钮，初始置灰
  2. 在空列表时点"开始出图"无副作用且日志显示 "请先添加文件"
  3. 添加文件后状态列显示"待处理"且为灰色徽章；完成显示绿色"完成"，失败显示红色"失败"
  4. 跑批中按 `Esc` 立即触发 stop，状态栏显示"已停止"
  5. 任意时刻 `Ctrl+L` 清空日志面板
  6. 首页 SW 状态卡片右上角"刷新"按钮可用，点击后重新检测连接
  7. 帮助菜单 → 打开 GB 制图规范，操作系统默认程序打开 `gb_drawing_rules.md`
