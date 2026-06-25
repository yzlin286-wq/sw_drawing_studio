# Pre-EXE Checklist — sw_drawing_studio 打包前 must-have 检查

> 时间：2026-06-18
> 目的：在**不重新打包**的前提下，给出"如果今天要打包，是否具备条件"的快速判断清单。
> 验证方式：本清单逐项打钩；30 分钟内得出 YES / NO 与阻塞项。
> **本次审计不执行 PyInstaller**（按用户要求"目前不进行完整 EXE 开发"）。

---

## 1. 依赖（requirements_app.txt 现状）

| 包 | 版本约束 | 用途 | 状态 |
|---|---|---|---|
| PySide6 | ≥6.6 | UI | ✅ |
| qt-material | * | 主题 | ✅ |
| pyyaml | * | 配置 | ✅ |
| httpx | * | LLM HTTP | ✅ |
| pywin32 | * | SolidWorks COM | ✅ |
| pillow | * | 图像辅助 | ✅ |
| PyMuPDF | * | PDF→PNG | ✅ |
| pyinstaller | * | 打包 | ✅ |
| **comtypes** | 缺失 | capabilities.md 提到 SW 连接需要 comtypes（实际本仓库代码主要用 pywin32，已可工作；但 `solidworks-automation-skill` 上游脚本依赖） | ⚠ **建议补**（可选，仅在跑上游 MCP 脚本时需要）|

**结论**：核心依赖齐全，可打包。

---

## 2. 入口与配置

| 项 | 现状 | 状态 |
|---|---|---|
| 应用入口 `app/main.py` | 存在 | ✅ |
| MainWindow `app/ui/main_window.py` | 存在并可启动（offscreen 已验证） | ✅ |
| LLM 配置模板 `config/llm.yaml.example` | 存在；含 5 个 provider（openai/deepseek/dashscope/ollama/ccagent）| ✅ |
| App 配置模板 `config/app.yaml.example` | 存在；默认 `output_dir = .../drw_output/v5`、`max_qc_rounds=3`、`vision_min_score=80` | ✅ |
| 配置目录在首次启动自动复制 | 是（`_ensure_config()` 走 `%APPDATA%/sw_drawing_studio/`） | ✅ |
| 默认 `active_provider=deepseek` 但 vision_model 为空 | 用户必须切换到 dashscope/openai 才能用视觉 QC | ⚠ 建议默认改为 `dashscope`，或在首次启动后弹出引导卡 |

---

## 3. 运行时资源（PyInstaller 打包必带）

| 资源 | 当前 spec 是否含 | 状态 |
|---|---|---|
| `config/llm.yaml.example` → `config/` | datas 第 14 行已含 | ✅ |
| `config/app.yaml.example` → `config/` | datas 第 15 行已含 | ✅ |
| qt_material 数据 | `collect_data_files('qt_material')` | ✅ |
| `.trae/specs/enforce-drawing-quality/drw_qc_loop.py` | **未 bundle**！[sw_runner.py](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/app/services/sw_runner.py#L13-L15) 中 `QC_LOOP_SCRIPT` 用绝对路径硬编码到桌面仓库 | ❌ **阻塞** |
| `.trae/specs/enforce-drawing-quality/drw_quality_check.py` / `drw_generate_v5.py` | 同上，未 bundle | ❌ **阻塞** |
| `.trae/specs/enforce-drawing-quality/gb_drawing_rules.md`（帮助菜单链接） | 未 bundle | ⚠ |

**关键阻塞**：当前 EXE 只能在**当前桌面**那台机器跑，其他机器没有 `c:\Users\Vision\Desktop\SW 相关\.trae\specs\...`。

**修补方案（不在本次 EXE 重打包范围，但写入清单）**：
1. 在 `build_exe.spec` 的 `datas` 追加：
   ```
   datas += [('.trae/specs/enforce-drawing-quality/drw_qc_loop.py', '_resources/qc')]
   datas += [('.trae/specs/enforce-drawing-quality/drw_quality_check.py', '_resources/qc')]
   datas += [('.trae/specs/enforce-drawing-quality/drw_generate_v5.py', '_resources/qc')]
   datas += [('.trae/specs/enforce-drawing-quality/gb_drawing_rules.md', '_resources/docs')]
   ```
2. 在 `app/services/sw_runner.py` 增加运行时 base：当 `sys.frozen` 时，从 `sys._MEIPASS / "_resources/qc"` 找脚本；否则用现有 REPO_ROOT。
3. 在 `app/ui/main_window.py` 的 `_open_gb_rules` 增加同样的兜底路径。

---

## 4. 错误兜底（用户机器异常场景）

| 场景 | 当前行为 | 期望 | 状态 |
|---|---|---|---|
| 用户机器**未装 SolidWorks** | 首页 SW 状态卡片显示"未连接（pywin32 未安装）"；批量出图会立刻失败但不崩溃 | 同上即可，已加"刷新"按钮 | ✅ |
| 用户**未配置 LLM Key** | LLM 对象为 None，`statusBar` 显示"模型未配置"；视觉 QC 按钮触发后 QC 页显示"模型未配置，无法执行视觉质检" | 同上即可 | ✅ |
| 用户**无网络** | LLMClient 内置 2 次重试 + 指数退避；最终失败时 toast | OK | ✅ |
| 用户机器**未装中文字体（仿宋）** | `gb_font_is_changfangsong` 报 fail，但不阻塞 | 用户可在 `gb_drawing_rules.md` 关掉该规则 | ✅ |
| 模板 .drwdot 路径无效（默认指向 SW2023） | v5 启动会报 `OpenDoc6 returned None` | 需要在 settings 提示用户校正 | ⚠ |

---

## 5. 可执行性

| 检查 | 状态 |
|---|---|
| `python -c "import app.ui.main_window"` 不报错 | ✅（已在 Task 3 验证） |
| `python -c "import ast; ast.parse(...)"` 通过 4 个核心文件 | ✅ |
| 离线 GUI 启动（QT_QPA_PLATFORM=offscreen）打开 MainWindow | ✅ |
| `dist/sw_drawing_studio.exe` 已存在（旧版本） | ✅，但**不**在本次更新范围 |

---

## 6. YES / NO 结论

**当前是否具备打包条件？** → **NO（条件性）**

**阻塞项（必须先解决）**：
1. **B-1**: `.trae/specs/enforce-drawing-quality/*.py` 三个核心 QC 脚本未在 `build_exe.spec` 的 `datas` 中声明，打出来的 EXE 在他机无法找到。
2. **B-2**: [sw_runner.py:13](file:///c:/Users/Vision/Desktop/SW%20%E7%9B%B8%E5%85%B3/app/services/sw_runner.py#L13-L13) 用了绝对路径 `c:\Users\Vision\Desktop\SW 相关`；他机必然失败。

**非阻塞但建议**：
3. comtypes 加入 requirements（兼容上游 MCP 脚本）。
4. 默认 active_provider 改 dashscope（含 vision）。
5. `_open_gb_rules` 增加 frozen 兜底路径。
6. 模板路径在首次启动校验，无效时引导用户在设置中选择。

**结论解读**：UI 层与 QC 规则的本次审计已经全部就绪；只要补齐上述 B-1/B-2 两个**绝对路径与资源 bundle**问题，即可一键打包并在他机运行。这两条**不在本次 spec 范围**（用户明确"目前不进行完整 EXE 开发"），但已写入清单作为下一里程碑的 P0。
