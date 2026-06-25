# SolidWorks 自动化 — 当前可实现功能清单 (Capabilities)

> 环境：Windows + SolidWorks 2025 (Rev 33.5.0) + Python 3.11.4 (64-bit) + pywin32 + comtypes，连接已验证通过。
> 单位约定：长度米、角度弧度；通过 `mm()` / `deg()` 转换。
> 标记：✅ = 当前已经可直接调用；🔧 = 当前需先按 API Help 写 10~50 行胶水代码即可启用；🚧 = 需许可证 / 加载项支持。

---

## 1. 连接 / 应用层 ✅
- 自动连接已运行实例（`GetActiveObject`）或启动新实例（`Dispatch("SldWorks.Application[.{rev}]")`）
- 读取版本号、可见性、命令管理器
- 切换 Visible / 静默模式 / 抑制对话框（`SetUserPreferenceToggle`）
- 关闭单个文档 `CloseDoc(title)` / 全部关闭
- 切换活动文档 `ActivateDoc3`
- 读写用户偏好 `GetUserPreferenceStringValue / IntegerValue / DoubleValue / Toggle`

## 2. 文档管理 ✅
- 新建零件 / 装配 / 工程图（自动定位模板 .prtdot/.asmdot/.drwdot）
- 打开任意 SLDPRT / SLDASM / SLDDRW / STEP / IGES（含只读、静默、错误码捕获）
- 保存 (`Save3`) / 另存为 (`Extension.SaveAs` 各种导出格式)
- 读取 / 写入文档自定义属性、配置特定属性、Summary Info
- 切换、新增、删除、复制配置 (`AddConfiguration2 / DeleteConfiguration2`)
- 读取 `MassProperties`（体积、表面积、质量、惯性矩、重心）

## 3. 草图（2D & 3D） ✅
- 进入 / 退出草图（中英文基准面别名兜底）
- 直线、矩形（中心 / 对角）、圆、圆弧、多边形、槽口、样条曲线
- 草图几何关系：水平 / 垂直 / 平行 / 垂直 / 相切 / 同心 / 等长 / 对称 / 中点 / 重合
- 草图尺寸标注 `AddDimension2`
- 转换实体引用 / 偏移实体 / 镜像 / 修剪 / 延伸 (🔧 SketchManager 后续可扩展)
- 3D 草图 `Insert3DSketch` (🔧)

## 4. 零件特征 ✅
- 凸台拉伸 / 切除拉伸 / 中面拉伸 / 完全贯穿
- 旋转凸台 / 旋转切除 (🔧 切除)
- 倒圆角（常半径 / 变半径 🔧）、倒角（距 + 角，距 + 距 🔧）
- 抽壳、筋、镜像特征
- 线性阵列、圆周阵列（曲线 / 草图驱动阵列 🔧）
- 异型孔向导 HoleWizard5 (🔧 当前 Skill 仅占位)
- 螺纹孔 / 攻丝底孔（Skill 子模块 `subskills/solidworks-threaded-holes` 已稳定路径）
- 多体管理（`InsertCombineFeature` 🔧）
- 扫描 / 放样 / 边界凸台 (🔧 InsertProtrusionSwept4 / Blend2)
- 拔模 (🔧)、变形 / 弯曲 / 包覆 (🔧)
- 参考几何：基准面、基准轴、点、坐标系 (🔧 `CreatePlaneByXxx`、`CreateRefAxis`)

## 5. 装配体 ✅
- 添加零部件 / 子装配（绝对坐标定位、指定配置）
- 组件解析 / 轻化 / 压缩 / 隐藏 / 显示 (`SetSuppression2`)
- 组件固定 / 浮动 (`FixComponent / UnfixComponent`)
- 修改组件位姿 (`Component2.Transform2 / SetTransformAndSolve2`)
- 创建配合：重合、距离、平行、垂直、相切、同心、角度、对称、宽度
- 高级 / 机械配合：齿轮 (`Gear`)、铰链 (`Hinge`)、凸轮 (`CamFollower`)、螺旋 (`Screw`)、齿条 (`RackPinion`)、万向 (`Universal`)、槽 (`Slot`)、限制角度/距离 (🔧)
- 干涉检查 `InterferenceDetectionMgr` (🔧 一段标准代码即可)
- 装配体爆炸视图 (🔧 `IExplodeStep`)
- 智能扣件 SmartFasteners (🔧)
- 装配体特征：装配体切除、孔系列 (🔧)
- 子装配的零部件替换 / 重命名 / 配置切换 (🔧)
- 顶点 / 面 / 边映射到装配体上下文 (`GetCorresponding`)

## 6. Motion Study & 仿真
- ✅ 运动算例创建 / 激活 / 设置时长
- ✅ 匀速旋转马达 (`swFmAEMRotationalMotor=78`) + Calculate / Play
- 🔧 直线马达、伺服马达（按时间曲线）、施加力 / 力矩 / 弹簧 / 阻尼
- 🔧 接触约束、引力
- 🚧 Motion Analysis（需 Premium / Simulation 许可证），Basic Motion 自带
- 🚧 SolidWorks Simulation：Static / Frequency / Thermal / Buckling / Drop Test / Fatigue（需要 Simulation 加载项）
- 🚧 Flow Simulation（独立加载项）

## 7. 工程图 ✅
- 第三角投影三视图、第一角投影 (🔧)
- 单视图（Front/Top/Right/Iso/Trimetric/Dimetric）
- 剖视图 / 局部放大视图
- 模型项标注 / 自动尺寸 / 公差与基准 (🔧 GTOL/Datum)
- 注释、技术要求文本块、表面粗糙度 (🔧)
- BOM 表（顶层 / 仅零件 / 缩进），可链接配置
- 表格：修订表、孔表、设计表 (🔧)
- 图纸格式 .slddrt 切换、新增多页图纸
- 视图比例 / 显示模式 / 切边可见性 (🔧)
- 出图：PDF（多页一次）/ DXF / DWG / TIFF / JPG (🔧 后两者通过 SaveAs 拓展)

## 8. 文件导出 ✅
- 中性 3D 格式：STEP（203/214）/ IGES / Parasolid (.x_t/.x_b) / ACIS (.sat 🔧) / 3MF (🔧) / 3DXML (🔧)
- 网格：STL（fine/coarse + 自定义品质 🔧）/ OBJ (🔧) / PLY (🔧)
- 2D 矢量：PDF / DXF / DWG（含钣金展开图）
- 图片：BMP（已用作自审查）/ JPG / TIFF / PNG (🔧 经 SaveAs 输出)
- 渲染图：PhotoView / Visualize 帧 (🚧 需对应加载项)
- 批量导出：批量打开（Silent=1）→ 导出 → 关闭，已封装

## 9. 钣金 / 焊件
- 🔧 基体法兰 / 边线法兰 / 斜接法兰 / 折弯 / 展开 / 重叠
- 🔧 角撑板 / 闭合角 / 钣金成形工具
- 🔧 焊件结构构件 / 角撑板 / 切割清单 / 圆角焊缝 / 顶端盖
- ✅ 钣金展开图 DXF 导出 `ExportToDWG2`

## 10. 配置 / 设计表 / 方程式
- ✅ 创建 / 删除 / 切换 / 复制配置
- 🔧 通过 Excel 设计表批量驱动 (`InsertFamilyTableNew2`)
- 🔧 全局变量 / 方程式 (`IEquationMgr.Add3 / SetSuppression`)
- 🔧 配置特定外观 / 显示状态

## 11. 自定义属性 / 元数据
- ✅ 读 / 写 / 删除文件级、配置级自定义属性
- 🔧 链接到方程式或质量属性自动更新
- 🔧 工程图标题栏属性映射（按模板已有的 `$PRP:"xxx"` 即可）

## 12. 外观 / 材质 / 渲染
- ✅ 文档级 / 特征级 / 组件级颜色（9 元素材质数组三层兜底）
- ✅ 预设色：iron_red / armor_gold / dark_gunmetal / arc_blue / black / white / silver
- 🔧 完整 Appearance 库（贴图、贴花、纹理）`IModelDoc2.Extension.GetMaterialPropertyValues2 / IRenderMaterial`
- 🔧 材料分配 (`SetMaterialPropertyName2`，从 SolidWorks 自带材料库选 1060 铝、AISI 304…)
- 🚧 PhotoView 360 渲染（需加载项）

## 13. 自动化质检 / 复检
- ✅ 多视角 BMP 导出（iso/front/top/right）
- ✅ JSON + Markdown 自审查报告（status: pass/warn/fail；规则评分）
- ✅ 期望输出文件存在性 / 大小检查
- ✅ 特征树遍历摘要（`FirstFeature/GetNextFeature/GetTypeName2`）
- 🔧 模型重建错误检查 (`Model.GetRebuildState`、`GetFeatureManager.GetUpdateStamp`)
- 🔧 配合冲突 / 过约束诊断
- 🔧 草图欠定义 / 轮廓不闭合扫描

## 14. MCP / 代理集成
- ✅ 本地 stdio MCP Server（已注册 Codex/Claude Code/Claude Desktop/Cursor/Windsurf）
- ✅ 暴露 16 个 `solidworks_*` 工具：health_check / connect / new_document / open_document / save_document / close_documents / create_basic_part / add_component / set_component_fixed / add_coincident_mate / add_distance_mate / add_concentric_mate / set_appearance / export_active / review_active / add_rotary_motor
- ✅ 全局锁串行执行（避免桌面会话冲突）

## 15. 围绕你工作目录可立即落地的常用任务
你桌面 `SW 相关\3D转2D测试图纸\` 下有 100+ SLDPRT / SLDASM / SLDDRW，下面这些可以直接派单：
1. **批量 STEP 导出**（所有 SLDPRT → `output_step\*.STEP`）
2. **批量 PDF 出图**（已有 SLDDRW 一次性出 PDF）
3. **批量 DXF**（钣金件展开图 / 工程图）
4. **批量 STL**（用于 3D 打印 / FEA 网格预处理）
5. **批量自定义属性导出 CSV**（料号、材料、重量、版本）
6. **装配体 BOM 导出 Excel / CSV**
7. **多视角 BMP 预览 + 自审查报告**（用于 PR review）
8. **批量替换组件 / 升级版本**（同名替换）
9. **批量改色或材质统一化**
10. **基于现有 SLDPRT 自动生成 SLDDRW + 三视图 + 尺寸 + BOM**（按通用模板）

---

## 后续扩展优先级建议
- 最易扩展、最高回报：异型孔向导 HoleWizard5、材料分配、配置/设计表批量驱动、装配干涉检测、参考几何创建。
- 中等：扫描/放样/钣金折弯、爆炸视图、SmartFastener、BOM 自动写表头。
- 高难/受许可证限制：Simulation/Flow Simulation、PhotoView 360、MBD 标注。
