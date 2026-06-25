# Checklist

- [x] Skill 仓库的目录结构已被完整还原（scripts/、references/、mcp-server/、examples/）
- [x] `SKILL.md` 与 `README.md` 中声明的所有特性条目均在 notes 中能找到对应说明
- [x] scripts/ 下每个模块（sw_session、sw_preflight、sw_macro_guard、sw_connect、sw_appearance、sw_part、sw_assembly、sw_motion、sw_drawing、sw_export、sw_review）的公开函数均被列出并附用法
- [x] mcp-server 暴露的所有 MCP 工具均有功能、参数、对应 Python 封装的说明
- [x] SolidWorks COM 核心对象树（SldWorks → ModelDoc2 → PartDoc/AssemblyDoc/DrawingDoc + Extension/Manager 系列）已成图或成表
- [x] 至少覆盖 6 类常用枚举（文档类型、选择类型、Mate 类型、Mate 对齐、拉伸终止条件、导出文件类型）
- [x] 单位（米/弧度）、中英文基准面、SelectByID2、SilentMode/对话框处理 等关键概念有说明
- [x] 提供了"未封装 API 查证 → 实现 → 自审查"工作流说明
- [x] 提供了至少 5 个 Skill 高层封装 ↔ COM 底层调用的对应关系示例（实际 19 条）
- [x] 提供了常见排错（连接失败、特征失败、Mate 失败、导出失败、Motion 失败）的排查清单
- [x] 笔记仅写入 `.trae/specs/study-solidworks-skill/` 目录，未触碰桌面工程文件
