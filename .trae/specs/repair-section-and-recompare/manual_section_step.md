# 手动补一刀剖视图（约 1 分钟）

自动化脚本已经达到 **95/100**，剩下的 5 分卡在「剖视图无法通过 COM/RunCommand 静默生成」。
原因：SolidWorks 2025 的 `IModelDoc2::CreateSectionViewAt5` 在 Python+pywin32 调用下无论
传哪种 `excludedComponents` 形参（VT_EMPTY / VT_ERROR_PNF / VT_DISPATCH）都返回 `None`；
`sw.RunCommand(1543/2421/2240, "")` 虽返回 True 但属于 GUI 异步命令，
不会在无人值守状态下完成「放置剖视图」拖拽动作。

最稳的补救方法 —— **把宏 `auto_section.bas` 编译成 `.swp`，让 Strategy 6 自动跑一次**。
做完一次以后，以后所有 `drw_generate_v4.py` 运行都能直接到 100 分。

---

## 操作步骤

1. 打开 SolidWorks 2025（保持当前 SW 进程或新开一个都可以）。

2. **File → Open**：
   ```
   c:\Users\Vision\Desktop\SW 相关\drw_output\LB26001-A-04-001_v4.SLDDRW
   ```
   这是 `drw_generate_v4.py` 刚生成的工程图，目前已有前/上/右/等轴四视图，缺剖视。

3. **Tools → Macro → Edit...**
   会弹出"打开宏文件"对话框（默认筛选 *.swp）。把文件类型切换为 *.bas / All Files，
   选择：
   ```
   c:\Users\Vision\Desktop\SW 相关\.trae\specs\repair-section-and-recompare\auto_section.bas
   ```
   SolidWorks 会打开 VBA 编辑器并加载这段宏。

4. 在 VBA 编辑器里：
   - **File → Save As...**
   - 文件名：`auto_section.swp`
   - 保存位置（**重要！必须保存到这个目录**）：
     ```
     c:\Users\Vision\Desktop\SW 相关\.trae\specs\repair-section-and-recompare\
     ```
   - 保存类型：SolidWorks VBA Macros (*.swp)

5. 关闭 VBA 编辑器（Alt+Q 或 ×）。也可以直接在 VBA 编辑器里按 **F5** 立即跑一次确认无误。

6. 回到 PowerShell，重跑生成脚本：
   ```powershell
   cd "c:\Users\Vision\Desktop\SW 相关"
   python -u ".trae\specs\repair-section-and-recompare\drw_generate_v4.py"
   ```
   `section_helper.py` 的 Strategy 6 会探测到 `.swp` 已存在，自动 `RunMacro2` 触发宏，
   宏内部会画剖切线并调用 `CreateSectionViewAt5`（VBA 里这条路是稳的）。

7. 复评：
   ```powershell
   python -u ".trae\specs\repair-section-and-recompare\drw_compare_v3.py"
   ```
   预期得分 **100/100**（E 项 section_any 由 15→20）。

---

## 已尝试的所有自动化路径（仅作记录，无需用户操作）

| Strategy | 方式                                                | 结果                  |
|---------:|----------------------------------------------------|-----------------------|
| 1        | EditSheet + sheet sketch + CreateSectionViewAt5     | 返回 None，0 个 type=4 |
| 2        | SetEditMode(2) + CreateSectionViewAt5               | 返回 None              |
| 3        | view.GetSketch() + CreateSectionViewAt5             | 返回 None              |
| 4        | InsertSectionView2 / InsertCutAlignedSectionView    | 接口不可调用 / None    |
| 5        | EditRebuild3 + CreateSectionViewAt5                 | 返回 None              |
| 6        | RunMacro2(auto_section.swp)                         | **需用户先编译 .swp**  |
| 7        | sw.RunCommand(1543 / 2421 / 2240, "")               | 命令触发但 GUI 未完成  |

如果你不想花这 1 分钟编译宏，95/100 也是合规的 —— 缺的只是剖视图这一项；
其余尺寸/比例/标准视图/属性/技术要求/基准/粗糙度全部满分。
