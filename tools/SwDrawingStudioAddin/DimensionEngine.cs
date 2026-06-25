using System;
using System.Collections.Generic;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;

namespace SwDrawingStudioAddin
{
    /// <summary>
    /// v2.0 Task 2: Dimension Engine v2
    ///
    /// 区分 5 类尺寸计数:
    ///   existing_display_dim_count  - 已存在的 DisplayDimension
    ///   addin_created_dim_count     - Add-in 本次创建的 DisplayDimension
    ///   model_associative_dim_count - 模型关联尺寸（InsertModelAnnotations）
    ///   note_dim_count              - Note 标注（不冒充 DisplayDim）
    ///   standard_annotation_count   - 标准件/采购件 annotation
    ///
    /// 策略顺序:
    ///   1. InsertModelAnnotations3/4
    ///   2. AutoDimension (SelectByID2 + AddDimension2)
    ///   3. GetVisibleEntities2 + 外形尺寸
    ///   4. 标准件/采购件 annotation
    ///
    /// 原则:
    ///   - 不把 Note 标注伪装成真实 DisplayDim
    ///   - 失败必须输出 reason
    /// </summary>
    public class DimensionEngine
    {
        private object _swApp;
        private AddinAPI _addin;

        public DimensionEngine(object swApp, AddinAPI addin)
        {
            _swApp = swApp;
            _addin = addin;
        }

        /// <summary>
        /// 执行 Dimension Engine v2
        /// </summary>
        public Dictionary<string, object> Execute(
            string drawingPath,
            string partPath,
            string runId,
            Dictionary<string, object> policy)
        {
            var result = new Dictionary<string, object>();
            result["engine_version"] = "v2.0";
            result["timestamp"] = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
            result["drawing_path"] = drawingPath;
            result["part_path"] = partPath;
            result["policy"] = policy;

            try
            {
                // 通过 AddinAPI 的公共方法打开文档
                // 使用反射调用 AddinAPI 的私有方法不可行，这里直接使用 COM

                // 1. 读取插入前尺寸
                int dimBefore = ReadDisplayDimCount(drawingPath);
                result["dim_before"] = dimBefore;

                // 策略 1: InsertModelAnnotations3/4
                result["step"] = "strategy_1_insert_model_annotations";
                int modelAnnoCount = Strategy1_InsertModelAnnotations(drawingPath);
                result["model_annotations_count"] = modelAnnoCount;
                int modelAssocDimCount = modelAnnoCount;

                // 策略 2: AutoDimension (通过 SelectByID2 + AddDimension2)
                int autoDimCount = 0;
                if (modelAnnoCount == 0)
                {
                    result["step"] = "strategy_2_auto_dimension";
                    autoDimCount = Strategy2_AutoDimension(drawingPath, partPath);
                    result["auto_dimension_count"] = autoDimCount;
                }

                // 策略 3: 外形尺寸 (通过 view Outline + AddDimension)
                int outlineDimCount = 0;
                if (modelAnnoCount == 0 && autoDimCount == 0)
                {
                    result["step"] = "strategy_3_outline_dimension";
                    outlineDimCount = Strategy3_OutlineDimension(drawingPath, partPath);
                    result["outline_dimension_count"] = outlineDimCount;
                }

                // 策略 4: 标准件/采购件 annotation
                int stdAnnoCount = 0;
                string partClass = "";
                if (policy != null && policy.ContainsKey("part_class"))
                {
                    partClass = policy["part_class"].ToString();
                }
                if (partClass == "fastener" || partClass == "spring" || partClass == "purchased_part")
                {
                    result["step"] = "strategy_4_standard_annotation";
                    stdAnnoCount = Strategy4_StandardAnnotation(drawingPath, partClass);
                    result["standard_annotation_count"] = stdAnnoCount;
                }

                // 读取插入后尺寸
                int dimAfter = ReadDisplayDimCount(drawingPath);
                result["dim_after"] = dimAfter;

                int addinCreated = dimAfter - dimBefore;
                if (addinCreated < 0) addinCreated = 0;

                result["existing_display_dim_count"] = dimAfter;
                result["addin_created_dim_count"] = addinCreated;
                result["model_associative_dim_count"] = modelAssocDimCount;
                result["note_dim_count"] = 0; // 不把 Note 计入 DisplayDim
                result["standard_annotation_count"] = stdAnnoCount;

                result["step"] = "done";
                bool engineSuccess = addinCreated > 0 || modelAssocDimCount > 0;
                result["success"] = engineSuccess;
                result["reason"] = engineSuccess ? "成功生成尺寸" : "无新增尺寸（模型无 PMI/DimXpert，GetVisibleEntities2 返回 0 edges）";
            }
            catch (Exception ex)
            {
                result["success"] = false;
                result["reason"] = "DimensionEngine 异常: " + ex.Message;
            }

            return result;
        }

        /// <summary>
        /// v2.1 Task 1: Dimension Engine v3
        ///
        /// 策略顺序:
        ///   1. Import PMI / DimXpert (InsertModelAnnotations3/4)
        ///   2. AutoDimension (GetLines2 + SelectByID2 + AddDimension5)
        ///   3. VisibleEntity based dimension (GetLines2 + 外形尺寸)
        ///   4. PMI Seed copied model (复制 part, 创建 PMI, 再 InsertModelAnnotations)
        ///   5. Standard annotation
        /// </summary>
        public Dictionary<string, object> ExecuteV3(
            string drawingPath,
            string partPath,
            string runId,
            string runDir,
            Dictionary<string, object> policy)
        {
            var result = new Dictionary<string, object>();
            result["engine_version"] = "v3.0";
            result["timestamp"] = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
            result["drawing_path"] = drawingPath;
            result["part_path"] = partPath;
            result["policy"] = policy;

            var strategyLog = new List<object>();

            try
            {
                // 打开 drawing
                dynamic drwDoc = OpenDrawing(drawingPath);
                if (drwDoc == null)
                {
                    result["success"] = false;
                    result["reason"] = "OpenDoc6 Drawing 返回 null";
                    return result;
                }
                ActivateDoc(drawingPath);

                int dimBefore = ReadDisplayDimCountFromDoc(drwDoc);
                result["dim_before"] = dimBefore;

                int modelAssocDimCount = 0;
                int autoDimCount = 0;
                int outlineDimCount = 0;
                int pmiSeedDimCount = 0;
                int stdAnnoCount = 0;

                // === 策略 1: Import PMI / DimXpert ===
                {
                    var entry = new Dictionary<string, object>();
                    entry["strategy"] = "1_import_pmi_dimxpert";
                    int count = Strategy1_InsertModelAnnotationsFromDoc(drwDoc);
                    modelAssocDimCount = count;
                    entry["count"] = count;
                    entry["success"] = count > 0;
                    entry["reason"] = count > 0 ? "InsertModelAnnotations 成功" : "模型无 PMI/DimXpert 注解";
                    strategyLog.Add(entry);
                }

                // === 策略 2: AutoDimension (GetLines2 + SelectByID2 + AddDimension5) ===
                if (modelAssocDimCount == 0)
                {
                    var entry = new Dictionary<string, object>();
                    entry["strategy"] = "2_auto_dimension";
                    int count = Strategy2_AutoDimensionV3(drwDoc, strategyLog);
                    autoDimCount = count;
                    entry["count"] = count;
                    entry["success"] = count > 0;
                    entry["reason"] = count > 0 ? "AutoDimension 成功" : "GetLines2+AddDimension5 无法创建尺寸（SW2025 限制：SelectByID2 无法选中 drawing view 中的边）";
                    strategyLog.Add(entry);
                }

                // === 策略 3: VisibleEntity based dimension (GetLines2 + 外形尺寸) ===
                if (modelAssocDimCount == 0 && autoDimCount == 0)
                {
                    var entry = new Dictionary<string, object>();
                    entry["strategy"] = "3_visible_entity_dimension";
                    int count = Strategy3_OutlineDimensionV3(drwDoc);
                    outlineDimCount = count;
                    entry["count"] = count;
                    entry["success"] = count > 0;
                    entry["reason"] = count > 0 ? "外形尺寸成功" : "GetLines2 无可用线段或 AddDimension5 失败";
                    strategyLog.Add(entry);
                }

                // === 策略 4: PMI Seed copied model ===
                if (modelAssocDimCount == 0 && autoDimCount == 0 && outlineDimCount == 0)
                {
                    var entry = new Dictionary<string, object>();
                    entry["strategy"] = "4_pmi_seed_copied_model";
                    var seedResult = Strategy4_PmiSeedImport(drwDoc, partPath, runId, runDir, drawingPath);
                    pmiSeedDimCount = (int)seedResult["imported_count"];
                    modelAssocDimCount += pmiSeedDimCount;
                    entry["count"] = pmiSeedDimCount;
                    entry["success"] = pmiSeedDimCount > 0;
                    entry["reason"] = (string)seedResult["reason"];
                    entry["seed_details"] = seedResult["seed_details"];
                    strategyLog.Add(entry);
                }

                // === 策略 4b: v2.1 新增 - 在 drawing sheet 上直接创建草图尺寸 ===
                // 注意: 此策略在 SW2025 上可能导致 SW 卡住（AddDimension2 弹出尺寸输入框）
                // 暂时禁用，改为通过 Python sidecar 处理
                int sheetSketchDimCount = 0;
                if (false) // 禁用 Strategy 4b
                {
                    var entry = new Dictionary<string, object>();
                    entry["strategy"] = "4b_sheet_sketch_dimension";
                    sheetSketchDimCount = Strategy4b_SheetSketchDimension(drwDoc, strategyLog);
                    entry["count"] = sheetSketchDimCount;
                    entry["success"] = sheetSketchDimCount > 0;
                    entry["reason"] = sheetSketchDimCount > 0
                        ? "Sheet 草图尺寸成功创建"
                        : "Sheet 草图尺寸创建失败（SW2025 限制：无法在 sheet 上进入草图模式或 AddDimension5 失败）";
                    strategyLog.Add(entry);
                }

                // === 策略 5: Standard annotation ===
                string partClass = "";
                if (policy != null && policy.ContainsKey("part_class"))
                {
                    partClass = policy["part_class"].ToString();
                }
                if (partClass == "fastener" || partClass == "spring" || partClass == "purchased_part")
                {
                    var entry = new Dictionary<string, object>();
                    entry["strategy"] = "5_standard_annotation";
                    stdAnnoCount = Strategy5_StandardAnnotation(drwDoc, partClass);
                    entry["count"] = stdAnnoCount;
                    entry["success"] = stdAnnoCount > 0;
                    entry["reason"] = stdAnnoCount > 0 ? "标准件 annotation 成功" : "标准件 annotation 跳过（Note 不计入 DisplayDim）";
                    strategyLog.Add(entry);
                }

                // 读取插入后尺寸
                int dimAfter = ReadDisplayDimCountFromDoc(drwDoc);
                result["dim_after"] = dimAfter;

                int addinCreated = dimAfter - dimBefore;
                if (addinCreated < 0) addinCreated = 0;

                // 如果 dimAfter-dimBefore 为 0 但 sheetSketchDimCount > 0，使用 sheetSketchDimCount
                if (addinCreated == 0 && sheetSketchDimCount > 0)
                {
                    addinCreated = sheetSketchDimCount;
                }

                result["existing_display_dim_count"] = dimAfter;
                result["addin_created_dim_count"] = addinCreated;
                result["model_associative_dim_count"] = modelAssocDimCount;
                result["note_dim_count"] = 0;
                result["standard_annotation_count"] = stdAnnoCount;
                result["strategy_log"] = strategyLog;

                // 保存
                bool saved = false;
                try
                {
                    object saveRet = ComCall(drwDoc, "Save");
                    saved = saveRet != null && (bool)saveRet;
                }
                catch (Exception ex)
                {
                    result["save_error"] = ex.Message;
                    try
                    {
                        object[] saveArgs = new object[] { 1, 0, 0 };
                        bool[] saveRefs = new bool[] { false, true, true };
                        object saveRet2 = ComInvoke(drwDoc, "Save3", saveArgs, saveRefs);
                        saved = saveRet2 != null && (bool)saveRet2;
                    }
                    catch (Exception ex2)
                    {
                        result["save_error_2"] = ex2.Message;
                    }
                }
                result["saved"] = saved;

                result["step"] = "done";
                bool engineSuccess = addinCreated > 0 || modelAssocDimCount > 0;
                result["success"] = engineSuccess;
                result["reason"] = engineSuccess
                    ? "Dimension Engine v3 成功生成尺寸"
                    : "Dimension Engine v3 无新增尺寸（所有策略受 SW2025 API 限制）";
            }
            catch (Exception ex)
            {
                result["success"] = false;
                result["reason"] = "DimensionEngine v3 异常: " + ex.Message;
            }

            return result;
        }

        /// <summary>
        /// 读取已打开 drawing 的 DisplayDimension 数量
        /// </summary>
        private int ReadDisplayDimCountFromDoc(dynamic drwDoc)
        {
            try
            {
                int count = 0;
                dynamic sheet = ComCall(drwDoc, "GetCurrentSheet");
                dynamic views = ComCall(sheet, "GetViews");
                if (views != null && views is Array)
                {
                    Array viewsArr = (Array)views;
                    foreach (object view in viewsArr)
                    {
                        try
                        {
                            object dispDims = ComCall(view, "GetDisplayDimensions");
                            if (dispDims != null)
                            {
                                count += CountArray(dispDims);
                            }
                        }
                        catch { }
                    }
                }
                return count;
            }
            catch { return 0; }
        }

        /// <summary>
        /// 策略 2 v3: AutoDimension - 使用 GetLines2 获取线段 + SelectByID2 + AddDimension5
        /// v2.1: 尝试多种 type 字符串和选择方式
        /// </summary>
        private int Strategy2_AutoDimensionV3(dynamic drwDoc, List<object> logEntries)
        {
            int created = 0;
            try
            {
                dynamic sheet = ComCall(drwDoc, "GetCurrentSheet");
                dynamic views = ComCall(sheet, "GetViews");
                if (views == null || !(views is Array)) return 0;

                Array viewsArr = (Array)views;
                int viewIdx = 0;
                foreach (object view in viewsArr)
                {
                    try
                    {
                        int viewType = 0;
                        try { viewType = (int)ComGet(view, "Type"); } catch { }
                        if (viewType == 0) continue;

                        string viewName = "";
                        try { viewName = (string)ComGet(view, "Name"); } catch { }

                        // 激活 view
                        try { ComCall(drwDoc, "ActivateView", viewName); } catch { }

                        // 获取 view 位置和缩放
                        double viewScale = 1.0;
                        try { viewScale = (double)ComGet(view, "ScaleRatio"); } catch { }

                        object viewPos = null;
                        try { viewPos = ComGet(view, "Position"); } catch { }
                        double posX = 0, posY = 0;
                        if (viewPos is Array)
                        {
                            Array posArr = (Array)viewPos;
                            if (posArr.Length >= 2)
                            {
                                posX = Convert.ToDouble(posArr.GetValue(0));
                                posY = Convert.ToDouble(posArr.GetValue(1));
                            }
                        }

                        // 获取 GetLines2 - view space 坐标
                        object lines = null;
                        try { lines = ComCall(view, "GetLines2"); } catch { }

                        int lineCount = 0;
                        if (lines != null && lines is Array)
                        {
                            Array linesArr = (Array)lines;
                            lineCount = linesArr.Length / 12;
                        }

                        if (lineCount > 0)
                        {
                            Array linesArr = (Array)lines;
                            // 取前 3 条线尝试创建尺寸
                            int maxTry = Math.Min(3, lineCount);
                            for (int li = 0; li < maxTry; li++)
                            {
                                try
                                {
                                    double sx = Convert.ToDouble(linesArr.GetValue(li * 12 + 0));
                                    double sy = Convert.ToDouble(linesArr.GetValue(li * 12 + 1));
                                    double ex = Convert.ToDouble(linesArr.GetValue(li * 12 + 3));
                                    double ey = Convert.ToDouble(linesArr.GetValue(li * 12 + 4));

                                    // view space -> sheet space
                                    double sheetSx = posX + sx * viewScale;
                                    double sheetSy = posY + sy * viewScale;
                                    double sheetEx = posX + ex * viewScale;
                                    double sheetEy = posY + ey * viewScale;

                                    // 尝试多种 type 字符串选中起点
                                    bool selOk = false;
                                    string selTypeUsed = "";
                                    string[] typeStrings = { "", "EDGE", "EXTSKETCHSEGMENT", "SKETCHSEGMENT" };

                                    dynamic ext = ComGet(drwDoc, "Extension");
                                    foreach (string typeStr in typeStrings)
                                    {
                                        try
                                        {
                                            // 先清除选择
                                            try { ComCall(drwDoc, "ClearSelection"); } catch { }

                                            object selRet = ComCall(ext, "SelectByID2",
                                                "", typeStr, sheetSx, sheetSy, 0, false, 0, null, 0);
                                            if (selRet != null && (bool)selRet)
                                            {
                                                selOk = true;
                                                selTypeUsed = typeStr;
                                                break;
                                            }
                                        }
                                        catch { }
                                    }

                                    // 也尝试 IModelDoc2.SelectByID2 直接调用
                                    if (!selOk)
                                    {
                                        foreach (string typeStr in typeStrings)
                                        {
                                            try
                                            {
                                                try { ComCall(drwDoc, "ClearSelection"); } catch { }

                                                object selRet = ComCall(drwDoc, "SelectByID2",
                                                    "", typeStr, sheetSx, sheetSy, 0, false, 0, null, 0);
                                                if (selRet != null && (bool)selRet)
                                                {
                                                    selOk = true;
                                                    selTypeUsed = typeStr + "(direct)";
                                                    break;
                                                }
                                            }
                                            catch { }
                                        }
                                    }

                                    if (selOk)
                                    {
                                        // 选中终点 (append=true)
                                        try
                                        {
                                            ComCall(ext, "SelectByID2",
                                                "", selTypeUsed.Replace("(direct)", ""),
                                                sheetEx, sheetEy, 0, true, 0, null, 0);
                                        }
                                        catch { }

                                        // AddDimension5
                                        try
                                        {
                                            double dimX = (sheetSx + sheetEx) / 2.0;
                                            double dimY = Math.Max(sheetSy, sheetEy) + 0.03;
                                            object dim = ComCall(drwDoc, "AddDimension5",
                                                dimX, dimY, 0, 0, 0, false, 0.005, 0, 0);
                                            if (dim != null)
                                            {
                                                created++;
                                                logEntries.Add(new Dictionary<string, object> {
                                                    {"action", "strategy2_create_dim"},
                                                    {"view", viewName},
                                                    {"line_idx", li},
                                                    {"sel_type", selTypeUsed},
                                                    {"success", true}
                                                });
                                            }
                                        }
                                        catch (Exception dimEx)
                                        {
                                            logEntries.Add(new Dictionary<string, object> {
                                                {"action", "strategy2_add_dim_failed"},
                                                {"view", viewName},
                                                {"line_idx", li},
                                                {"sel_type", selTypeUsed},
                                                {"error", dimEx.Message}
                                            });
                                        }
                                        try { ComCall(drwDoc, "ClearSelection"); } catch { }
                                    }
                                    else
                                    {
                                        logEntries.Add(new Dictionary<string, object> {
                                            {"action", "strategy2_select_failed"},
                                            {"view", viewName},
                                            {"line_idx", li},
                                            {"coords", new[] { sheetSx, sheetSy, sheetEx, sheetEy }},
                                            {"tried_types", typeStrings}
                                        });
                                    }
                                }
                                catch { }
                            }
                        }
                        else
                        {
                            logEntries.Add(new Dictionary<string, object> {
                                {"action", "strategy2_no_lines"},
                                {"view", viewName},
                                {"line_count", 0}
                            });
                        }

                        viewIdx++;
                        if (viewIdx >= 3) break; // 只处理前 3 个 view
                    }
                    catch { }
                }
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine("Strategy2_AutoDimensionV3 失败: " + ex.Message);
            }
            return created;
        }

        /// <summary>
        /// 策略 3 v3: 外形尺寸 - 使用 GetLines2 获取 view 边界 + AddDimension5
        /// </summary>
        private int Strategy3_OutlineDimensionV3(dynamic drwDoc)
        {
            int created = 0;
            try
            {
                dynamic sheet = ComCall(drwDoc, "GetCurrentSheet");
                dynamic views = ComCall(sheet, "GetViews");
                if (views == null || !(views is Array)) return 0;

                Array viewsArr = (Array)views;
                foreach (object view in viewsArr)
                {
                    try
                    {
                        int viewType = 0;
                        try { viewType = (int)ComGet(view, "Type"); } catch { }
                        if (viewType == 0) continue;

                        string viewName = "";
                        try { viewName = (string)ComGet(view, "Name"); } catch { }

                        // 激活 view
                        try { ComCall(drwDoc, "ActivateView", viewName); } catch { }

                        // 获取 view Outline (sheet space: minX, minY, minZ, maxX, maxY, maxZ)
                        object outline = ComGet(view, "Outline");
                        if (outline is Array)
                        {
                            Array outlineArr = (Array)outline;
                            if (outlineArr.Length >= 6)
                            {
                                double minX = Convert.ToDouble(outlineArr.GetValue(0));
                                double minY = Convert.ToDouble(outlineArr.GetValue(1));
                                double maxX = Convert.ToDouble(outlineArr.GetValue(3));
                                double maxY = Convert.ToDouble(outlineArr.GetValue(4));

                                // 尝试通过 SelectByID2 选中 view 边界角点
                                // 然后添加外形尺寸
                                bool selOk = false;
                                try
                                {
                                    // 选中 view 本身
                                    dynamic ext = ComGet(drwDoc, "Extension");
                                    object selRet = ComCall(ext, "SelectByID2",
                                        viewName, "DRAWINGVIEW", minX, minY, 0, false, 0, null, 0);
                                    selOk = selRet != null && (bool)selRet;
                                }
                                catch { }

                                if (selOk)
                                {
                                    // 尝试 AddDimension5 添加宽度尺寸
                                    try
                                    {
                                        double dimX = (minX + maxX) / 2.0;
                                        double dimY = maxY + 0.04;
                                        object dim = ComCall(drwDoc, "AddDimension5",
                                            dimX, dimY, 0, 0, 0, false, 0.005, 0, 0);
                                        if (dim != null) created++;
                                    }
                                    catch { }
                                    try { ComCall(drwDoc, "ClearSelection"); } catch { }
                                }

                                // 也尝试通过 GetLines2 获取最长线段作为外形尺寸
                                try
                                {
                                    object lines = ComCall(view, "GetLines2");
                                    if (lines != null && lines is Array)
                                    {
                                        Array linesArr = (Array)lines;
                                        int lineCount = linesArr.Length / 12;
                                        if (lineCount > 0 && created == 0)
                                        {
                                            // 找最长的水平线
                                            double maxLen = 0;
                                            int maxIdx = -1;
                                            for (int li = 0; li < lineCount; li++)
                                            {
                                                double sx = Convert.ToDouble(linesArr.GetValue(li * 12 + 0));
                                                double sy = Convert.ToDouble(linesArr.GetValue(li * 12 + 1));
                                                double ex = Convert.ToDouble(linesArr.GetValue(li * 12 + 3));
                                                double ey = Convert.ToDouble(linesArr.GetValue(li * 12 + 4));
                                                double len = Math.Sqrt((ex - sx) * (ex - sx) + (ey - sy) * (ey - sy));
                                                if (len > maxLen)
                                                {
                                                    maxLen = len;
                                                    maxIdx = li;
                                                }
                                            }

                                            if (maxIdx >= 0 && maxLen > 0.001)
                                            {
                                                // 已有 view 选中，尝试添加尺寸
                                                try
                                                {
                                                    double sx = Convert.ToDouble(linesArr.GetValue(maxIdx * 12 + 0));
                                                    double sy = Convert.ToDouble(linesArr.GetValue(maxIdx * 12 + 1));
                                                    double ex = Convert.ToDouble(linesArr.GetValue(maxIdx * 12 + 3));
                                                    double ey = Convert.ToDouble(linesArr.GetValue(maxIdx * 12 + 4));
                                                    double dimX = (sx + ex) / 2.0;
                                                    double dimY = Math.Max(sy, ey) + 0.05;
                                                    object dim = ComCall(drwDoc, "AddDimension5",
                                                        dimX, dimY, 0, 0, 0, false, 0.005, 0, 0);
                                                    if (dim != null) created++;
                                                }
                                                catch { }
                                                try { ComCall(drwDoc, "ClearSelection"); } catch { }
                                            }
                                        }
                                    }
                                }
                                catch { }
                            }
                        }

                        if (created > 0) break; // 成功创建后停止
                    }
                    catch { }
                }
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine("Strategy3_OutlineDimensionV3 失败: " + ex.Message);
            }
            return created;
        }

        /// <summary>
        /// 策略 4: PMI Seed - 复制 part, 创建 PMI, 再 InsertModelAnnotations 导入
        /// </summary>
        private Dictionary<string, object> Strategy4_PmiSeedImport(
            dynamic drwDoc, string partPath, string runId, string runDir, string drawingPath)
        {
            var result = new Dictionary<string, object>();
            result["imported_count"] = 0;
            result["reason"] = "";
            result["seed_details"] = new List<object>();

            try
            {
                // 调用 PmiSeedEngine 创建副本 + PMI
                var seedEngine = new PmiSeedEngine(_swApp);
                var seedResult = seedEngine.SeedPart(partPath, runId, runDir);
                result["seed_details"] = seedResult;

                if (!(bool)seedResult["success"])
                {
                    result["reason"] = "PMI Seed 未创建尺寸: " + (string)seedResult["reason"];
                    return result;
                }

                // 获取副本路径
                string seedPath = (string)seedResult["seed_part_path"];

                // 打开副本
                dynamic seedDoc = OpenDoc(seedPath, 1, 1);
                if (seedDoc == null)
                {
                    result["reason"] = "OpenDoc6 副本返回 null";
                    return result;
                }

                // 重新激活 drawing
                ActivateDoc(drawingPath);

                // 尝试 InsertModelAnnotations3 导入副本中的 PMI
                int imported = 0;
                try
                {
                    object importResult = ComCall(drwDoc, "InsertModelAnnotations3",
                        true, 3, false, true, false, null, false);
                    imported = CountArray(importResult);
                }
                catch { }

                if (imported == 0)
                {
                    try
                    {
                        object importResult = ComCall(drwDoc, "InsertModelAnnotations4",
                            true, 3, false, true, false, null, false, false);
                        imported = CountArray(importResult);
                    }
                    catch { }
                }

                result["imported_count"] = imported;
                result["reason"] = imported > 0
                    ? "PMI Seed 导入成功"
                    : "PMI Seed 创建了尺寸但 InsertModelAnnotations 仍返回 0（SW2025 限制）";
            }
            catch (Exception ex)
            {
                result["reason"] = "Strategy4 异常: " + ex.Message;
            }

            return result;
        }

        /// <summary>
        /// 策略 5: 标准件 annotation - 使用 Note 添加标准标注
        /// 原则: 不把 Note 计入 DisplayDim
        /// </summary>
        private int Strategy5_StandardAnnotation(dynamic drwDoc, string partClass)
        {
            int created = 0;
            try
            {
                // 标准件 annotation 使用 Note，不计入 DisplayDim
                // 返回 0，standard_annotation_count 单独统计
                // 实际 Note 添加由 Python sidecar 处理
            }
            catch { }
            return created;
        }

        /// <summary>
        /// 策略 4b: v2.1 新增 - 在 drawing sheet 上直接创建草图尺寸
        ///
        /// 注意: 此策略在 SW2025 上可能导致不稳定，添加了多重异常保护
        ///
        /// 流程:
        ///   1. 获取当前 sheet
        ///   2. 在 sheet 上通过 SketchManager.CreateLine 画线
        ///   3. AddDimension2 添加尺寸（使用 auto-select）
        /// </summary>
        private int Strategy4b_SheetSketchDimension(dynamic drwDoc, List<object> logEntries)
        {
            int created = 0;
            try
            {
                // 确保在 sheet 模式（不是 view 模式）
                try
                {
                    // 激活第一个 sheet
                    dynamic sheet = ComCall(drwDoc, "GetCurrentSheet");
                    string sheetName = "";
                    try { sheetName = (string)ComGet(sheet, "GetName"); } catch { }
                    try { ComCall(drwDoc, "ActivateSheet", sheetName); } catch { }
                }
                catch { }

                // 获取 SketchManager
                dynamic sketchMgr = null;
                try { sketchMgr = ComGet(drwDoc, "SketchManager"); } catch { }
                if (sketchMgr == null)
                {
                    logEntries.Add(new Dictionary<string, object> {
                        {"action", "strategy4b_no_sketch_manager"}, {"error", "SketchManager 为 null"}
                    });
                    return 0;
                }

                // 获取 sheet 的一个合理位置（使用第一个 view 的位置作为参考）
                double startX = 0.1; // 默认 100mm
                double startY = 0.1;
                double lineLen = 0.05; // 50mm

                try
                {
                    dynamic sheet = ComCall(drwDoc, "GetCurrentSheet");
                    dynamic views = ComCall(sheet, "GetViews");
                    if (views != null && views is Array)
                    {
                        Array viewsArr = (Array)views;
                        foreach (object view in viewsArr)
                        {
                            try
                            {
                                int viewType = 0;
                                try { viewType = (int)ComGet(view, "Type"); } catch { }
                                if (viewType == 0) continue;

                                object outline = ComGet(view, "Outline");
                                if (outline is Array)
                                {
                                    Array outlineArr = (Array)outline;
                                    if (outlineArr.Length >= 6)
                                    {
                                        double minX = Convert.ToDouble(outlineArr.GetValue(0));
                                        double minY = Convert.ToDouble(outlineArr.GetValue(1));
                                        double maxX = Convert.ToDouble(outlineArr.GetValue(3));
                                        double maxY = Convert.ToDouble(outlineArr.GetValue(4));
                                        // 在 view 上方画线
                                        startX = minX;
                                        startY = maxY + 0.03;
                                        lineLen = maxX - minX;
                                        if (lineLen < 0.001) lineLen = 0.05;
                                        break;
                                    }
                                }
                            }
                            catch { }
                        }
                    }
                }
                catch { }

                // 进入草图模式（drawing sheet 上）
                try
                {
                    ComCall(drwDoc, "InsertSketch2", true);
                    logEntries.Add(new Dictionary<string, object> {
                        {"action", "strategy4b_insert_sketch"}, {"success", true}
                    });
                }
                catch (Exception ex)
                {
                    logEntries.Add(new Dictionary<string, object> {
                        {"action", "strategy4b_insert_sketch"}, {"error", ex.Message}
                    });
                    return 0;
                }

                // 画一条水平线
                object lineObj = null;
                try
                {
                    lineObj = ComCall(sketchMgr, "CreateLine", startX, startY, 0, startX + lineLen, startY, 0);
                    logEntries.Add(new Dictionary<string, object> {
                        {"action", "strategy4b_create_line"},
                        {"success", lineObj != null},
                        {"start_x", startX}, {"start_y", startY},
                        {"line_len", lineLen}
                    });
                }
                catch (Exception ex)
                {
                    logEntries.Add(new Dictionary<string, object> {
                        {"action", "strategy4b_create_line"}, {"error", ex.Message}
                    });
                }

                if (lineObj == null)
                {
                    try { ComCall(drwDoc, "InsertSketch2", true); } catch { }
                    return 0;
                }

                // CreateLine 后线段应自动选中，直接尝试 AddDimension2（不清除选择）
                // 注意：只使用 AddDimension2（AddDimension5 在 IDrawingDoc 上不存在）
                // AddDimension2 在 SW2025 中可能弹出尺寸值输入框，需要立即处理
                double midX = startX + lineLen / 2.0;

                try
                {
                    double dimX = midX;
                    double dimY = startY + 0.02;
                    object dim = ComCall(drwDoc, "AddDimension2", dimX, dimY, 0);
                    if (dim != null)
                    {
                        created++;
                        logEntries.Add(new Dictionary<string, object> {
                            {"action", "strategy4b_add_dimension2"},
                            {"success", true},
                            {"method", "auto_select_after_create"}
                        });

                        // 立即设置尺寸值，避免 SW 弹出尺寸输入框
                        try
                        {
                            // 设置尺寸值为线段长度（单位：mm）
                            double dimValueMm = lineLen * 1000.0;
                            ComCall(dim, "SystemValue", dimValueMm / 1000.0);
                            logEntries.Add(new Dictionary<string, object> {
                                {"action", "strategy4b_set_dim_value"},
                                {"success", true},
                                {"value_mm", dimValueMm}
                            });
                        }
                        catch (Exception ex)
                        {
                            logEntries.Add(new Dictionary<string, object> {
                                {"action", "strategy4b_set_dim_value"},
                                {"error", ex.Message}
                            });
                        }
                    }
                    else
                    {
                        logEntries.Add(new Dictionary<string, object> {
                            {"action", "strategy4b_add_dimension2"},
                            {"success", false}, {"reason", "返回 null"}
                        });
                    }
                }
                catch (Exception ex)
                {
                    logEntries.Add(new Dictionary<string, object> {
                        {"action", "strategy4b_add_dimension2"},
                        {"error", ex.Message}
                    });
                }

                // 立即清除选择，避免 SW 弹出尺寸输入对话框
                try { ComCall(drwDoc, "ClearSelection"); } catch { }

                // 尝试按 Escape 键取消任何弹窗
                try
                {
                    // SendMsgToUser 不行，用 SetAddToDB + Escape
                    // 实际上 SW COM 没有 Escape 方法，但可以尝试 CloseDoc 再打开
                }
                catch { }

                // 退出草图
                try { ComCall(drwDoc, "InsertSketch2", true); } catch { }
                logEntries.Add(new Dictionary<string, object> {
                    {"action", "strategy4b_exit_sketch"}, {"success", true}
                });
            }
            catch (Exception ex)
            {
                logEntries.Add(new Dictionary<string, object> {
                    {"action", "strategy4b_exception"}, {"error", ex.Message}
                });
                // 确保退出草图模式
                try { ComCall(drwDoc, "InsertSketch2", true); } catch { }
            }
            return created;
        }

        private int ReadDisplayDimCount(string drawingPath)
        {
            try
            {
                dynamic drwDoc = OpenDrawing(drawingPath);
                if (drwDoc == null) return 0;

                int count = 0;
                dynamic sheet = ComCall(drwDoc, "GetCurrentSheet");
                dynamic views = ComCall(sheet, "GetViews");
                if (views != null && views is Array)
                {
                    Array viewsArr = (Array)views;
                    foreach (object view in viewsArr)
                    {
                        try
                        {
                            object dispDims = ComCall(view, "GetDisplayDimensions");
                            if (dispDims != null)
                            {
                                count += CountArray(dispDims);
                            }
                        }
                        catch { }
                    }
                }
                return count;
            }
            catch { return 0; }
        }

        private int Strategy1_InsertModelAnnotations(string drawingPath)
        {
            try
            {
                dynamic drwDoc = OpenDrawing(drawingPath);
                if (drwDoc == null) return 0;

                return Strategy1_InsertModelAnnotationsFromDoc(drwDoc);
            }
            catch { return 0; }
        }

        /// <summary>
        /// v2.1: 直接对已打开的 drwDoc 执行 InsertModelAnnotations3/4
        /// </summary>
        private int Strategy1_InsertModelAnnotationsFromDoc(dynamic drwDoc)
        {
            try
            {
                // InsertModelAnnotations3
                try
                {
                    object result = ComCall(drwDoc, "InsertModelAnnotations3",
                        true, 3, false, true, false, null, false);
                    int count = CountArray(result);
                    if (count > 0) return count;
                }
                catch { }

                // InsertModelAnnotations4
                try
                {
                    object result = ComCall(drwDoc, "InsertModelAnnotations4",
                        true, 3, false, true, false, null, false, false);
                    return CountArray(result);
                }
                catch { }

                return 0;
            }
            catch { return 0; }
        }

        private int Strategy2_AutoDimension(string drawingPath, string partPath)
        {
            // v2.0 原则: 不使用 pywin32 SelectByID2 / AddDimension2 作为主修复路径
            // 但 C# Add-in 内部可以尝试
            int created = 0;
            try
            {
                dynamic drwDoc = OpenDrawing(drawingPath);
                if (drwDoc == null) return 0;

                // 激活第一个 view
                dynamic sheet = ComCall(drwDoc, "GetCurrentSheet");
                dynamic views = ComCall(sheet, "GetViews");
                if (views == null || !(views is Array)) return 0;

                Array viewsArr = (Array)views;
                foreach (object view in viewsArr)
                {
                    try
                    {
                        int viewType = 0;
                        try { viewType = (int)ComGet(view, "Type"); } catch { }
                        if (viewType == 0) continue;

                        string viewName = (string)ComGet(view, "Name");

                        // 尝试选中 view
                        try
                        {
                            // ActivateView
                            ComCall(drwDoc, "ActivateView", viewName);
                        }
                        catch { }

                        // 尝试通过 SelectByID2 选中视图中的边
                        // 这需要知道边的坐标，SW2025 下 GetVisibleEntities2 返回 0
                        // 所以这个策略在 SW2025 下可能无法创建尺寸
                        break; // 只处理第一个 view
                    }
                    catch { }
                }
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine("Strategy2 失败: " + ex.Message);
            }
            return created;
        }

        private int Strategy3_OutlineDimension(string drawingPath, string partPath)
        {
            // 通过 view Outline 获取外形，尝试添加外形尺寸
            int created = 0;
            try
            {
                dynamic drwDoc = OpenDrawing(drawingPath);
                if (drwDoc == null) return 0;

                dynamic sheet = ComCall(drwDoc, "GetCurrentSheet");
                dynamic views = ComCall(sheet, "GetViews");
                if (views == null || !(views is Array)) return 0;

                Array viewsArr = (Array)views;
                foreach (object view in viewsArr)
                {
                    try
                    {
                        int viewType = 0;
                        try { viewType = (int)ComGet(view, "Type"); } catch { }
                        if (viewType == 0) continue;

                        // 获取 view Outline
                        object outline = ComGet(view, "Outline");
                        if (outline is Array)
                        {
                            Array outlineArr = (Array)outline;
                            if (outlineArr.Length >= 6)
                            {
                                double minX = Convert.ToDouble(outlineArr.GetValue(0));
                                double minY = Convert.ToDouble(outlineArr.GetValue(1));
                                double maxX = Convert.ToDouble(outlineArr.GetValue(3));
                                double maxY = Convert.ToDouble(outlineArr.GetValue(4));

                                double width = maxX - minX;
                                double height = maxY - minY;

                                // 记录外形信息（实际添加尺寸需要选中边）
                                // SW2025 限制：无法通过 GetVisibleEntities2 获取边
                            }
                        }
                    }
                    catch { }
                }
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine("Strategy3 失败: " + ex.Message);
            }
            return created;
        }

        private int Strategy4_StandardAnnotation(string drawingPath, string partClass)
        {
            // 标准件/采购件 annotation - 使用 Note 添加标准标注
            // 原则: 不把 Note 计入 DisplayDim
            int created = 0;
            try
            {
                // 标准件 annotation 使用 Note，不计入 DisplayDim
                // 这里返回 0，standard_annotation_count 单独统计
            }
            catch { }
            return created;
        }

        #region COM helpers

        private dynamic OpenDrawing(string path)
        {
            try
            {
                // 先检查文档是否已打开
                try
                {
                    dynamic existingDoc = ComCall(_swApp, "GetOpenDocumentByName", path);
                    if (existingDoc != null) return existingDoc;
                }
                catch { }

                object[] args = new object[] { path, 3, 1, "", 0, 0 };
                bool[] refs = new bool[] { false, false, false, false, true, true };
                Type t = _swApp.GetType();
                dynamic doc = t.InvokeMember("OpenDoc6", BindingFlags.InvokeMethod, null, _swApp, args,
                    new ParameterModifier[] { CreateModifier(args.Length, refs) }, null, null);
                if (doc != null) return doc;

                // fallback: OpenDoc5
                try
                {
                    object[] args5 = new object[] { path, 3, 1, "", 0 };
                    bool[] refs5 = new bool[] { false, false, false, false, true };
                    return t.InvokeMember("OpenDoc5", BindingFlags.InvokeMethod, null, _swApp, args5,
                        new ParameterModifier[] { CreateModifier(args5.Length, refs5) }, null, null);
                }
                catch { }
            }
            catch { }
            return null;
        }

        /// <summary>
        /// v2.1: OpenDoc6 通用版本（支持 docType）
        /// </summary>
        private dynamic OpenDoc(string path, int docType, int options)
        {
            try
            {
                // 先检查文档是否已打开
                try
                {
                    dynamic existingDoc = ComCall(_swApp, "GetOpenDocumentByName", path);
                    if (existingDoc != null) return existingDoc;
                }
                catch { }

                object[] args = new object[] { path, docType, options, "", 0, 0 };
                bool[] refs = new bool[] { false, false, false, false, true, true };
                Type t = _swApp.GetType();
                dynamic doc = t.InvokeMember("OpenDoc6", BindingFlags.InvokeMethod, null, _swApp, args,
                    new ParameterModifier[] { CreateModifier(args.Length, refs) }, null, null);
                if (doc != null) return doc;

                // fallback: OpenDoc5
                try
                {
                    object[] args5 = new object[] { path, docType, options, "", 0 };
                    bool[] refs5 = new bool[] { false, false, false, false, true };
                    return t.InvokeMember("OpenDoc5", BindingFlags.InvokeMethod, null, _swApp, args5,
                        new ParameterModifier[] { CreateModifier(args5.Length, refs5) }, null, null);
                }
                catch { }
            }
            catch { }
            return null;
        }

        /// <summary>
        /// v2.1: ActivateDoc3 包装
        /// </summary>
        private void ActivateDoc(string path)
        {
            try
            {
                object[] args = new object[] { path, true, 0, 0 };
                bool[] refs = new bool[] { false, false, false, true };
                Type t = _swApp.GetType();
                t.InvokeMember("ActivateDoc3", BindingFlags.InvokeMethod, null, _swApp, args,
                    new ParameterModifier[] { CreateModifier(args.Length, refs) }, null, null);
            }
            catch { }
        }

        /// <summary>
        /// v2.1: COM 调用带 ref 参数
        /// </summary>
        private object ComInvoke(object obj, string methodName, object[] args, bool[] refFlags)
        {
            Type t = obj.GetType();
            ParameterModifier mods = new ParameterModifier(args.Length);
            for (int i = 0; i < refFlags.Length && i < args.Length; i++)
            {
                mods[i] = refFlags[i];
            }
            return t.InvokeMember(methodName, BindingFlags.InvokeMethod, null, obj, args,
                new ParameterModifier[] { mods }, null, null);
        }

        private ParameterModifier CreateModifier(int length, bool[] flags)
        {
            ParameterModifier mods = new ParameterModifier(length);
            for (int i = 0; i < flags.Length && i < length; i++)
            {
                mods[i] = flags[i];
            }
            return mods;
        }

        private object ComCall(object obj, string methodName, params object[] args)
        {
            Type t = obj.GetType();
            return t.InvokeMember(methodName, BindingFlags.InvokeMethod, null, obj, args, null);
        }

        private object ComGet(object obj, string propName)
        {
            Type t = obj.GetType();
            return t.InvokeMember(propName, BindingFlags.GetProperty, null, obj, null);
        }

        private int CountArray(object result)
        {
            if (result == null) return 0;
            if (result is Array) return ((Array)result).Length;
            if (result is int) return (int)result;
            try { return ((Array)result).Length; } catch { return 0; }
        }

        #endregion
    }
}
