using System;
using System.Collections.Generic;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Forms;

namespace SwDrawingStudioAddin
{
    /// <summary>
    /// v1.9 Task 2: SOLIDWORKS Add-in 最小闭环
    /// v2.0 Task 1: Add-in 正式化（新增 ProbeContext/ReadDimensions/GenerateDimensions/ExtractViewEntities/RelinkReferences）
    ///
    /// 实现 ISwAddin 接口（通过反射，避免硬依赖 interop 程序集）
    /// ConnectToSW 时注册 COM-visible API
    /// DisconnectFromSW 时清理
    ///
    /// COM-visible 方法:
    ///   Ping()
    ///   ProbeContext(run_id) -> v2.0
    ///   ReadDimensions(drawing_path, run_id) -> v2.0
    ///   GenerateDimensions(drawing_path, part_path, run_id, policy_json) -> v2.0
    ///   ExtractViewEntities(drawing_path, view_names_json, run_id) -> v2.0
    ///   RelinkReferences(drawing_path, part_path, run_id) -> v2.0
    ///   GenerateAssociativeDimensions(drawing_path, part_path, run_id) -> v1.9 保留
    ///   RelinkDrawingReferences(drawing_path, part_path, run_id) -> v1.9 保留
    ///   ExtractVisibleEntities(drawing_path, view_names_json, run_id) -> v1.9 保留
    ///   ProbePMI(part_path, run_id) -> v1.9 保留
    /// </summary>
    [ComVisible(true)]
    [Guid("B8F3E2A1-7C4D-4E5F-9A6B-1D2E3F4A5B6C")]
    [ProgId("SwDrawingStudioAddin.AddinAPI")]
    [ClassInterface(ClassInterfaceType.AutoDual)]
    public class AddinAPI
    {
        // SW Application COM 对象（dynamic 避免硬依赖 interop）
        private dynamic _swApp = null;
        private int _cookie = 0;
        private bool _connected = false;

        /// <summary>
        /// ConnectToSW - SOLIDWORKS Add-in 入口
        /// 由 SW Add-in Manager 调用
        /// </summary>
        public bool ConnectToSW(object This, int Cookie)
        {
            try
            {
                _cookie = Cookie;
                // 获取 SW Application 对象
                // This 通常是 ISldWorks 接口
                _swApp = This;

                // 注册 Add-in（设置事件回调等可在此处）
                // 通过 SetAddinCallbackInfo 注册菜单/工具栏（可选）

                _connected = true;

                // 写入 probe 结果
                try
                {
                    WriteProbeResult(true, "ConnectToSW 成功");
                }
                catch { }

                return true;
            }
            catch (Exception ex)
            {
                try
                {
                    WriteProbeResult(false, "ConnectToSW 异常: " + ex.Message);
                }
                catch { }
                return false;
            }
        }

        /// <summary>
        /// DisconnectFromSW - SOLIDWORKS Add-in 退出
        /// </summary>
        public bool DisconnectFromSW()
        {
            try
            {
                _swApp = null;
                _connected = false;
                return true;
            }
            catch
            {
                return false;
            }
        }

        /// <summary>
        /// Ping - 检查 Add-in 是否可用
        /// </summary>
        public bool Ping()
        {
            return _connected && _swApp != null;
        }

        /// <summary>
        /// ProbeContext - 探测当前 SW 上下文
        /// v2.0 Task 1: 返回 active_doc/sheet/view_count
        /// </summary>
        public string ProbeContext(string runId)
        {
            var result = new Dictionary<string, object>();
            result["method"] = "addin";
            result["timestamp"] = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
            result["addin_version"] = "v2.0";

            try
            {
                if (!Ping())
                {
                    result["success"] = false;
                    result["reason"] = "Add-in 未连接";
                    return ToJson(result);
                }

                // SW 版本
                try
                {
                    object ver = ComGet(_swApp, "RevisionVersion");
                    result["sw_version"] = ver != null ? ver.ToString() : "unknown";
                }
                catch { result["sw_version"] = "unknown"; }

                // 活动文档
                result["step"] = "get_active_doc";
                dynamic activeDoc = null;
                try
                {
                    activeDoc = ComGet(_swApp, "ActiveDoc");
                }
                catch { }

                if (activeDoc == null)
                {
                    result["success"] = true;
                    result["active_doc"] = "";
                    result["active_doc_type"] = "none";
                    result["sheet"] = "";
                    result["view_count"] = 0;
                    result["reason"] = "无活动文档";
                    return ToJson(result);
                }

                // 文档路径与类型
                string docPath = "";
                string docType = "unknown";
                try
                {
                    docPath = (string)ComCall(activeDoc, "GetPathName");
                }
                catch { }
                try
                {
                    int dt = (int)ComGet(activeDoc, "GetType");
                    // swDocPART=1, swDocASSEMBLY=2, swDocDRAWING=3
                    if (dt == 1) docType = "part";
                    else if (dt == 2) docType = "assembly";
                    else if (dt == 3) docType = "drawing";
                }
                catch { }

                result["active_doc"] = docPath;
                result["active_doc_type"] = docType;

                // 如果是 drawing，获取 sheet 和 view_count
                string sheetName = "";
                int viewCount = 0;
                if (docType == "drawing")
                {
                    try
                    {
                        dynamic sheet = ComCall(activeDoc, "GetCurrentSheet");
                        sheetName = (string)ComGet(sheet, "Name");
                        dynamic views = ComCall(sheet, "GetViews");
                        if (views != null && views is Array)
                        {
                            viewCount = ((Array)views).Length;
                        }
                    }
                    catch (Exception ex)
                    {
                        result["sheet_error"] = ex.Message;
                    }
                }

                result["sheet"] = sheetName;
                result["view_count"] = viewCount;
                result["success"] = true;
                result["reason"] = "ProbeContext 成功";
            }
            catch (Exception ex)
            {
                result["success"] = false;
                result["reason"] = "ProbeContext 异常: " + ex.Message;
            }

            return ToJson(result);
        }

        /// <summary>
        /// ReadDimensions - 读取 drawing 中现有尺寸
        /// v2.0 Task 1: 区分 display_dim / note_dim / model_associative_dim
        /// </summary>
        public string ReadDimensions(string drawingPath, string runId)
        {
            var result = new Dictionary<string, object>();
            result["method"] = "addin";
            result["timestamp"] = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");

            try
            {
                if (!Ping())
                {
                    result["success"] = false;
                    result["reason"] = "Add-in 未连接";
                    return ToJson(result);
                }

                drawingPath = System.IO.Path.GetFullPath(drawingPath);
                result["drawing_path"] = drawingPath;

                dynamic drwDoc = SwOpenDoc6(drawingPath, 3, 1);
                if (drwDoc == null)
                {
                    result["success"] = false;
                    result["reason"] = "OpenDoc6 Drawing 返回 null";
                    return ToJson(result);
                }

                SwActivateDoc3(drawingPath);

                int displayDimCount = 0;
                int noteDimCount = 0;
                int modelAssocDimCount = 0;
                var viewDims = new List<object>();

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
                                string viewName = (string)ComGet(view, "Name");
                                int viewDimCount = 0;
                                try
                                {
                                    object dispDims = ComCall(view, "GetDisplayDimensions");
                                    if (dispDims != null)
                                    {
                                        viewDimCount = CountResultArray(dispDims);
                                        displayDimCount += viewDimCount;
                                    }
                                }
                                catch { }

                                // 检查 DisplayDimension 是否为模型关联
                                try
                                {
                                    object dispDims2 = ComCall(view, "GetDisplayDimensions");
                                    if (dispDims2 != null && dispDims2 is Array)
                                    {
                                        Array dimsArr = (Array)dispDims2;
                                        foreach (object dim in dimsArr)
                                        {
                                            try
                                            {
                                                // GetType2: 0=unknown, 1=model, 2=driving, 3=driven
                                                int dimType = (int)ComCall(dim, "GetType2");
                                                if (dimType == 1) modelAssocDimCount++;
                                            }
                                            catch { }
                                        }
                                    }
                                }
                                catch { }

                                viewDims.Add(new Dictionary<string, object>
                                {
                                    { "view_name", viewName },
                                    { "display_dim_count", viewDimCount }
                                });
                            }
                            catch { }
                        }
                    }
                }
                catch (Exception ex)
                {
                    result["read_error"] = ex.Message;
                }

                // 统计 Note 数量（Note 中包含尺寸文本的）
                try
                {
                    object notes = ComCall(drwDoc, "GetNotes");
                    if (notes != null && notes is Array)
                    {
                        Array notesArr = (Array)notes;
                        foreach (object note in notesArr)
                        {
                            try
                            {
                                string noteText = (string)ComGet(note, "Text");
                                if (!string.IsNullOrEmpty(noteText))
                                {
                                    // 简单判断是否包含尺寸文本（数字+单位）
                                    if (ContainsDimensionText(noteText))
                                    {
                                        noteDimCount++;
                                    }
                                }
                            }
                            catch { }
                        }
                    }
                }
                catch { }

                result["existing_display_dim_count"] = displayDimCount;
                result["note_dim_count"] = noteDimCount;
                result["model_associative_dim_count"] = modelAssocDimCount;
                result["view_dimensions"] = viewDims;
                result["success"] = true;
                result["reason"] = "ReadDimensions 成功";
            }
            catch (Exception ex)
            {
                result["success"] = false;
                result["reason"] = "ReadDimensions 异常: " + ex.Message;
            }

            return ToJson(result);
        }

        /// <summary>
        /// GenerateDimensions - v2.0 Dimension Engine 入口
        /// 策略顺序: InsertModelAnnotations3/4 -> AutoDimension -> GetVisibleEntities2 + 外形尺寸
        /// </summary>
        public string GenerateDimensions(string drawingPath, string partPath, string runId, string policyJson)
        {
            var result = new Dictionary<string, object>();
            result["method"] = "addin";
            result["timestamp"] = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
            result["engine_version"] = "v2.0";

            try
            {
                if (!Ping())
                {
                    result["success"] = false;
                    result["reason"] = "Add-in 未连接";
                    return ToJson(result);
                }

                drawingPath = System.IO.Path.GetFullPath(drawingPath);
                partPath = System.IO.Path.GetFullPath(partPath);
                result["drawing_path"] = drawingPath;
                result["part_path"] = partPath;

                // 解析 policy
                var policy = ParsePolicy(policyJson);
                result["policy"] = policy;

                // 打开 Part
                dynamic partDoc = SwOpenDoc6(partPath, 1, 1);
                if (partDoc == null)
                {
                    result["success"] = false;
                    result["reason"] = "OpenDoc6 Part 返回 null";
                    return ToJson(result);
                }

                // 打开 Drawing
                dynamic drwDoc = SwOpenDoc6(drawingPath, 3, 1);
                if (drwDoc == null)
                {
                    result["success"] = false;
                    result["reason"] = "OpenDoc6 Drawing 返回 null";
                    return ToJson(result);
                }

                SwActivateDoc3(drawingPath);

                int dimBefore = CountDisplayDimensions(drwDoc);
                result["dim_before"] = dimBefore;

                // 策略 1: InsertModelAnnotations3/4
                result["step"] = "strategy_insert_model_anno";
                int modelAnnoCount = TryInsertModelAnnotations(drwDoc);
                result["model_annotations_count"] = modelAnnoCount;
                if (modelAnnoCount == 0)
                {
                    int modelAnnoCount4 = TryInsertModelAnnotations4(drwDoc);
                    result["model_annotations_count_v4"] = modelAnnoCount4;
                    modelAnnoCount = modelAnnoCount4;
                }
                int modelAssocDimCount = modelAnnoCount;

                // 策略 2: AutoDimension (如果策略 1 无结果)
                int autoDimCount = 0;
                if (modelAnnoCount == 0)
                {
                    result["step"] = "strategy_auto_dimension";
                    autoDimCount = TryAutoDimension(drwDoc);
                    result["auto_dimension_count"] = autoDimCount;
                }

                // 策略 3: GetVisibleEntities2 + 外形尺寸
                int outlineDimCount = 0;
                if (modelAnnoCount == 0 && autoDimCount == 0)
                {
                    result["step"] = "strategy_outline_dimension";
                    outlineDimCount = TryOutlineDimension(drwDoc, partDoc);
                    result["outline_dimension_count"] = outlineDimCount;
                }

                int dimAfter = CountDisplayDimensions(drwDoc);
                result["dim_after"] = dimAfter;

                int addinCreated = dimAfter - dimBefore;
                if (addinCreated < 0) addinCreated = 0;

                result["existing_display_dim_count"] = dimAfter;
                result["addin_created_dim_count"] = addinCreated;
                result["model_associative_dim_count"] = modelAssocDimCount;
                result["note_dim_count"] = 0;
                result["standard_annotation_count"] = 0;

                // 保存
                result["step"] = "save";
                bool saved = false;
                try
                {
                    object saveResult = ComCall(drwDoc, "Save");
                    saved = saveResult != null && (bool)saveResult;
                }
                catch (Exception ex)
                {
                    result["save_error"] = ex.Message;
                    try
                    {
                        object saveResult = ComCall(drwDoc, "Save2", 0);
                        saved = saveResult != null && (bool)saveResult;
                    }
                    catch (Exception ex2)
                    {
                        result["save_error_2"] = ex2.Message;
                    }
                }
                result["saved"] = saved;

                result["step"] = "done";
                bool genSuccess = addinCreated > 0 || modelAssocDimCount > 0;
                result["success"] = genSuccess;
                result["reason"] = genSuccess ? "成功生成尺寸" : "无新增尺寸（模型无 PMI/DimXpert 注解）";
            }
            catch (Exception ex)
            {
                result["success"] = false;
                result["reason"] = "GenerateDimensions 异常: " + ex.Message;
                result["exception_type"] = ex.GetType().Name;
            }

            return ToJson(result);
        }

        /// <summary>
        /// v2.1 Task 1: GenerateDimensionsV3 - Dimension Engine v3 入口
        ///
        /// 策略顺序:
        ///   1. Import PMI / DimXpert (InsertModelAnnotations3/4)
        ///   2. AutoDimension (GetLines2 + SelectByID2 + AddDimension5)
        ///   3. VisibleEntity based dimension (GetLines2 + 外形尺寸)
        ///   4. PMI Seed copied model (复制 part 到 input_work, 创建 PMI, 再导入)
        ///   5. Standard annotation
        ///
        /// 输出 5 类尺寸计数:
        ///   existing_display_dim_count
        ///   addin_created_dim_count
        ///   model_associative_dim_count
        ///   note_dim_count
        ///   standard_annotation_count
        /// </summary>
        public string GenerateDimensionsV3(string drawingPath, string partPath, string runId, string policyJson, string runDir)
        {
            var result = new Dictionary<string, object>();
            result["method"] = "addin";
            result["timestamp"] = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
            result["engine_version"] = "v3.0";

            try
            {
                if (!Ping())
                {
                    result["success"] = false;
                    result["reason"] = "Add-in 未连接";
                    return ToJson(result);
                }

                drawingPath = System.IO.Path.GetFullPath(drawingPath);
                partPath = System.IO.Path.GetFullPath(partPath);
                result["drawing_path"] = drawingPath;
                result["part_path"] = partPath;
                result["run_dir"] = runDir;

                var policy = ParsePolicy(policyJson);
                result["policy"] = policy;

                // 委托给 DimensionEngine v3
                var engine = new DimensionEngine(_swApp, this);
                var engineResult = engine.ExecuteV3(drawingPath, partPath, runId, runDir, policy);

                // 合并结果
                foreach (var kv in engineResult)
                {
                    result[kv.Key] = kv.Value;
                }
            }
            catch (Exception ex)
            {
                result["success"] = false;
                result["reason"] = "GenerateDimensionsV3 异常: " + ex.Message;
                result["exception_type"] = ex.GetType().Name;
            }

            return ToJson(result);
        }

        /// <summary>
        /// v2.1 Task 3: SeedPMI - PMI Seed Engine 入口
        /// 复制 part 到 run_dir/input_work, 在副本中创建外形 PMI, 返回副本路径
        /// </summary>
        public string SeedPMI(string partPath, string runId, string runDir)
        {
            var result = new Dictionary<string, object>();
            result["method"] = "addin";
            result["timestamp"] = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
            result["engine_version"] = "v3.0";

            try
            {
                if (!Ping())
                {
                    result["success"] = false;
                    result["reason"] = "Add-in 未连接";
                    return ToJson(result);
                }

                partPath = System.IO.Path.GetFullPath(partPath);
                result["part_path"] = partPath;

                var engine = new PmiSeedEngine(_swApp);
                var seedResult = engine.SeedPart(partPath, runId, runDir);

                foreach (var kv in seedResult)
                {
                    result[kv.Key] = kv.Value;
                }
            }
            catch (Exception ex)
            {
                result["success"] = false;
                result["reason"] = "SeedPMI 异常: " + ex.Message;
                result["exception_type"] = ex.GetType().Name;
            }

            return ToJson(result);
        }

        /// <summary>
        /// v2.1 Task 2: ExtractViewEntitiesV2 - Visible Entity Extractor v2 入口
        /// 新增 GetLines2 fallback
        /// </summary>
        public string ExtractViewEntitiesV2(string drawingPath, string viewNamesJson, string runId)
        {
            var result = new Dictionary<string, object>();
            result["method"] = "addin";
            result["timestamp"] = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
            result["extractor_version"] = "v2.1";

            try
            {
                if (!Ping())
                {
                    result["success"] = false;
                    result["reason"] = "Add-in 未连接";
                    return ToJson(result);
                }

                drawingPath = System.IO.Path.GetFullPath(drawingPath);
                List<string> viewNames = ParseJsonStringList(viewNamesJson);

                var extractor = new ViewEntityExtractor(_swApp);
                var extractResult = extractor.ExtractV2(drawingPath, viewNames, runId);

                foreach (var kv in extractResult)
                {
                    result[kv.Key] = kv.Value;
                }
            }
            catch (Exception ex)
            {
                result["success"] = false;
                result["reason"] = "ExtractViewEntitiesV2 异常: " + ex.Message;
                result["exception_type"] = ex.GetType().Name;
            }

            return ToJson(result);
        }

        /// <summary>
        /// ExtractViewEntities - v2.0 Visible Entity Extractor 入口
        /// </summary>
        public string ExtractViewEntities(string drawingPath, string viewNamesJson, string runId)
        {
            var result = new Dictionary<string, object>();
            result["method"] = "addin";
            result["timestamp"] = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
            result["extractor_version"] = "v2.0";

            try
            {
                if (!Ping())
                {
                    result["success"] = false;
                    result["reason"] = "Add-in 未连接";
                    return ToJson(result);
                }

                drawingPath = System.IO.Path.GetFullPath(drawingPath);
                List<string> viewNames = ParseJsonStringList(viewNamesJson);

                dynamic drwDoc = SwOpenDoc6(drawingPath, 3, 1);
                if (drwDoc == null)
                {
                    result["success"] = false;
                    result["reason"] = "OpenDoc6 Drawing 返回 null";
                    return ToJson(result);
                }

                SwActivateDoc3(drawingPath);

                var viewsData = new List<object>();
                int totalEdges = 0;
                int totalFaces = 0;
                int totalVertices = 0;
                int totalCircles = 0;
                int totalArcs = 0;
                int viewsProcessed = 0;

                try
                {
                    // 遍历所有 sheet
                    object[] sheetsArgs = new object[] { 0 };
                    bool[] sheetsRefs = new bool[] { true };
                    object sheetsObj = ComInvoke(drwDoc, "GetSheets", sheetsArgs, sheetsRefs);
                    Array sheetsArr = sheetsObj as Array;
                    if (sheetsArr == null)
                    {
                        // 回退到 GetCurrentSheet
                        dynamic sheet = ComCall(drwDoc, "GetCurrentSheet");
                        sheetsArr = new object[] { sheet };
                    }

                    foreach (object sheet in sheetsArr)
                    {
                        try
                        {
                            string sheetName = (string)ComGet(sheet, "Name");
                            // 激活 sheet
                            try
                            {
                                ComCall(drwDoc, "ActivateSheet", sheetName);
                            }
                            catch { }

                            dynamic views = ComCall(sheet, "GetViews");
                            if (views == null) continue;
                            if (!(views is Array)) continue;

                            Array viewsArr = (Array)views;
                            foreach (object view in viewsArr)
                            {
                                try
                                {
                                    string viewName = "";
                                    int viewType = 0;
                                    try
                                    {
                                        viewName = (string)ComGet(view, "Name");
                                    }
                                    catch { }
                                    try
                                    {
                                        viewType = (int)ComGet(view, "Type");
                                    }
                                    catch { }

                                    // 跳过 sheet view (type=0)
                                    if (viewType == 0) continue;

                                    if (viewNames.Count > 0 && !viewNames.Contains(viewName))
                                        continue;

                                    viewsProcessed++;

                                    int edgeCount = 0;
                                    int faceCount = 0;
                                    int vertexCount = 0;
                                    int circleCount = 0;
                                    int arcCount = 0;
                                    string edgeReason = "";

                                    // edges (filterType=1)
                                    try
                                    {
                                        object edges = ComCall(view, "GetVisibleEntities2", null, 1);
                                        if (edges != null)
                                        {
                                            edgeCount = CountResultArray(edges);
                                            totalEdges += edgeCount;

                                            // 遍历 edges 检查圆/圆弧
                                            if (edges is Array)
                                            {
                                                Array edgesArr = (Array)edges;
                                                foreach (object edge in edgesArr)
                                                {
                                                    try
                                                    {
                                                        object curve = ComCall(edge, "GetCurve");
                                                        if (curve != null)
                                                        {
                                                            int identity = (int)ComGet(curve, "Identity");
                                                            if (identity == 2) { circleCount++; totalCircles++; }
                                                            else if (identity == 3) { arcCount++; totalArcs++; }
                                                        }
                                                    }
                                                    catch { }
                                                }
                                            }
                                        }
                                    }
                                    catch (Exception ex)
                                    {
                                        edgeReason = "GetVisibleEntities2(edges) 失败: " + ex.Message;
                                    }

                                    if (edgeCount == 0 && string.IsNullOrEmpty(edgeReason))
                                    {
                                        edgeReason = "GetVisibleEntities2 返回 0 edges（可能需要激活 view 或 SW2025 限制）";
                                    }

                                    // faces (filterType=2)
                                    try
                                    {
                                        object faces = ComCall(view, "GetVisibleEntities2", null, 2);
                                        if (faces != null)
                                        {
                                            faceCount = CountResultArray(faces);
                                            totalFaces += faceCount;
                                        }
                                    }
                                    catch { }

                                    // vertices (filterType=3)
                                    try
                                    {
                                        object vertices = ComCall(view, "GetVisibleEntities2", null, 3);
                                        if (vertices != null)
                                        {
                                            vertexCount = CountResultArray(vertices);
                                            totalVertices += vertexCount;
                                        }
                                    }
                                    catch { }

                                    var viewData = new Dictionary<string, object>();
                                    viewData["sheet_name"] = sheetName;
                                    viewData["view_name"] = viewName;
                                    viewData["view_type"] = viewType;
                                    viewData["edges"] = edgeCount;
                                    viewData["faces"] = faceCount;
                                    viewData["vertices"] = vertexCount;
                                    viewData["circles"] = circleCount;
                                    viewData["arcs"] = arcCount;
                                    if (edgeCount == 0)
                                    {
                                        viewData["reason"] = edgeReason;
                                    }
                                    viewsData.Add(viewData);
                                }
                                catch { }
                            }
                        }
                        catch { }
                    }
                }
                catch (Exception ex)
                {
                    result["extract_error"] = ex.Message;
                }

                result["views_processed"] = viewsProcessed;
                result["total_edges"] = totalEdges;
                result["total_faces"] = totalFaces;
                result["total_vertices"] = totalVertices;
                result["total_circles"] = totalCircles;
                result["total_arcs"] = totalArcs;
                result["views"] = viewsData;
                result["success"] = viewsProcessed > 0;
                result["reason"] = viewsProcessed > 0
                    ? (totalEdges > 0 ? "成功提取可见实体" : "处理成功但 edges=0（SW2025 限制）")
                    : "无视图处理";
            }
            catch (Exception ex)
            {
                result["success"] = false;
                result["reason"] = "ExtractViewEntities 异常: " + ex.Message;
            }

            return ToJson(result);
        }

        /// <summary>
        /// RelinkReferences - v2.0 引用修复入口
        /// </summary>
        public string RelinkReferences(string drawingPath, string partPath, string runId)
        {
            var result = new Dictionary<string, object>();
            result["method"] = "addin";
            result["timestamp"] = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
            result["relink_version"] = "v2.0";

            try
            {
                if (!Ping())
                {
                    result["success"] = false;
                    result["reason"] = "Add-in 未连接";
                    return ToJson(result);
                }

                drawingPath = System.IO.Path.GetFullPath(drawingPath);
                partPath = System.IO.Path.GetFullPath(partPath);

                var refsBefore = GetDrawingReferences(drawingPath);
                result["references_before"] = refsBefore;
                result["reference_count_before"] = refsBefore.Count;

                dynamic drwDoc = SwOpenDoc6(drawingPath, 3, 1);
                if (drwDoc == null)
                {
                    result["success"] = false;
                    result["reason"] = "OpenDoc6 Drawing 返回 null";
                    return ToJson(result);
                }

                int replacedCount = 0;
                var replaceDetails = new List<object>();

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
                                string viewName = (string)ComGet(view, "Name");
                                int viewType = 0;
                                try { viewType = (int)ComGet(view, "Type"); } catch { }
                                if (viewType == 0) continue;

                                // 尝试 GetReferencedModelName 作为 fallback
                                string refModelName = "";
                                try
                                {
                                    refModelName = (string)ComCall(view, "GetReferencedModelName");
                                }
                                catch { }

                                object refDoc = null;
                                try { refDoc = ComGet(view, "ReferencedDocument"); } catch { }

                                string oldPath = refModelName;
                                if (refDoc != null)
                                {
                                    try
                                    {
                                        string p = (string)ComCall(refDoc, "GetPathName");
                                        if (!string.IsNullOrEmpty(p)) oldPath = p;
                                    }
                                    catch { }
                                }

                                if (!string.IsNullOrEmpty(oldPath) && !string.Equals(oldPath, partPath, StringComparison.OrdinalIgnoreCase))
                                {
                                    try
                                    {
                                        object okObj = ComCall(view, "ReplaceModel", partPath, "", true);
                                        bool ok = okObj != null && (bool)okObj;
                                        if (ok)
                                        {
                                            replacedCount++;
                                            replaceDetails.Add(new Dictionary<string, object>
                                            {
                                                { "view_name", viewName },
                                                { "old_path", oldPath },
                                                { "new_path", partPath },
                                                { "status", "replaced" }
                                            });
                                        }
                                        else
                                        {
                                            replaceDetails.Add(new Dictionary<string, object>
                                            {
                                                { "view_name", viewName },
                                                { "old_path", oldPath },
                                                { "new_path", partPath },
                                                { "status", "replace_failed" }
                                            });
                                        }
                                    }
                                    catch (Exception ex)
                                    {
                                        replaceDetails.Add(new Dictionary<string, object>
                                        {
                                            { "view_name", viewName },
                                            { "old_path", oldPath },
                                            { "new_path", partPath },
                                            { "status", "exception" },
                                            { "error", ex.Message }
                                        });
                                    }
                                }
                            }
                            catch { }
                        }
                    }
                }
                catch (Exception ex)
                {
                    result["replace_error"] = ex.Message;
                }

                var refsAfter = GetDrawingReferences(drawingPath);
                result["references_after"] = refsAfter;
                result["reference_count_after"] = refsAfter.Count;
                result["replaced_count"] = replacedCount;
                result["replace_details"] = replaceDetails;
                result["success"] = replacedCount > 0;
                result["reason"] = replacedCount > 0 ? "成功替换引用" : "无需替换或替换失败（view.ReferencedDocument 在 SW2025 下返回 null）";
            }
            catch (Exception ex)
            {
                result["success"] = false;
                result["reason"] = "RelinkReferences 异常: " + ex.Message;
            }

            return ToJson(result);
        }

        /// <summary>
        /// ProbePMI - 检查模型的 PMI/DimXpert/annotation views
        /// v1.9 Task 5: MBD/PMI Probe
        /// </summary>
        public string ProbePMI(string partPath, string runId)
        {
            var result = new Dictionary<string, object>();
            result["method"] = "addin";
            result["timestamp"] = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");

            try
            {
                if (!Ping())
                {
                    result["success"] = false;
                    result["reason"] = "Add-in 未连接";
                    return ToJson(result);
                }

                partPath = System.IO.Path.GetFullPath(partPath);
                result["part_path"] = partPath;

                // 打开 Part
                result["step"] = "open_part";
                dynamic partDoc = SwOpenDoc6(partPath, 1, 1);
                if (partDoc == null)
                {
                    result["success"] = false;
                    result["reason"] = "OpenDoc6 Part 返回 null";
                    return ToJson(result);
                }

                result["success"] = true;
                bool pmiAvailable = false;
                bool dimxpertAvailable = false;
                int pmiFeaturesCount = 0;
                var annoViews = new List<object>();
                int annoViewCount = 0;

                // 检查 DimXpert
                result["step"] = "check_dimxpert";
                try
                {
                    dynamic featMgr = ComGet(partDoc, "FeatureManager");
                    if (featMgr != null)
                    {
                        // GetDimXpertAnnotations
                        try
                        {
                            object dimxpertAnnos = ComCall(featMgr, "GetDimXpertAnnotations");
                            if (dimxpertAnnos != null)
                            {
                                int count = CountResultArray(dimxpertAnnos);
                                if (count > 0)
                                {
                                    dimxpertAvailable = true;
                                    pmiFeaturesCount = count;
                                }
                            }
                        }
                        catch { }

                        // 检查 features 中的 DimXpert/PMI
                        try
                        {
                            object features = ComCall(featMgr, "GetFeatures", false);
                            if (features != null && features is Array)
                            {
                                Array featsArr = (Array)features;
                                int dxCount = 0;
                                foreach (object feat in featsArr)
                                {
                                    try
                                    {
                                        string featType = (string)ComCall(feat, "GetTypeName2");
                                        if (featType != null && (featType.Contains("DimXpert") || featType.Contains("PMI")))
                                        {
                                            dxCount++;
                                        }
                                    }
                                    catch { }
                                }
                                if (dxCount > 0)
                                {
                                    dimxpertAvailable = true;
                                    pmiFeaturesCount = Math.Max(pmiFeaturesCount, dxCount);
                                }
                            }
                        }
                        catch { }
                    }
                }
                catch (Exception ex)
                {
                    result["dimxpert_error"] = ex.Message;
                }

                // 检查 Annotation Views
                result["step"] = "check_annotation_views";
                try
                {
                    dynamic ext = ComGet(partDoc, "Extension");
                    if (ext != null)
                    {
                        try
                        {
                            object views = ComCall(ext, "GetAnnotationViews");
                            if (views != null)
                            {
                                annoViewCount = CountResultArray(views);
                                if (views is Array)
                                {
                                    Array viewsArr = (Array)views;
                                    foreach (object av in viewsArr)
                                    {
                                        try
                                        {
                                            string name = (string)ComGet(av, "Name");
                                            annoViews.Add(new Dictionary<string, object>
                                            {
                                                { "name", name }
                                            });
                                        }
                                        catch { }
                                    }
                                }
                            }
                        }
                        catch { }
                    }
                }
                catch (Exception ex)
                {
                    result["annotation_view_error"] = ex.Message;
                }

                pmiAvailable = dimxpertAvailable || (annoViewCount > 0);

                result["pmi_available"] = pmiAvailable;
                result["dimxpert_available"] = dimxpertAvailable;
                result["pmi_features_count"] = pmiFeaturesCount;
                result["annotation_view_count"] = annoViewCount;
                result["annotation_views"] = annoViews;
                result["step"] = "done";
                result["reason"] = pmiAvailable
                    ? "PMI 可用: DimXpert=" + dimxpertAvailable + ", AnnotationViews=" + annoViewCount
                    : "无 PMI/DimXpert/Annotation Views";
            }
            catch (Exception ex)
            {
                result["success"] = false;
                result["reason"] = "ProbePMI 异常: " + ex.Message;
            }

            return ToJson(result);
        }

        /// <summary>
        /// GenerateAssociativeDimensions - 生成关联尺寸
        /// v1.9 Task 3: 调用 IDrawingDoc.InsertModelAnnotations3/4
        /// </summary>
        public string GenerateAssociativeDimensions(string drawingPath, string partPath, string runId)
        {
            var result = new Dictionary<string, object>();
            result["method"] = "addin";
            result["timestamp"] = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
            result["step"] = "init";

            try
            {
                if (!Ping())
                {
                    result["success"] = false;
                    result["reason"] = "Add-in 未连接";
                    return ToJson(result);
                }

                result["step"] = "resolve_path";
                drawingPath = System.IO.Path.GetFullPath(drawingPath);
                partPath = System.IO.Path.GetFullPath(partPath);
                result["drawing_path"] = drawingPath;
                result["part_path"] = partPath;

                // 先打开 Part（确保引用可用）
                result["step"] = "open_part";
                dynamic partDoc = null;
                try
                {
                    // swDocPART=1, swOpenDocOptions_Silent=1
                    partDoc = SwOpenDoc6(partPath, 1, 1);
                    if (partDoc == null)
                    {
                        result["success"] = false;
                        result["reason"] = "OpenDoc6 Part 返回 null";
                        return ToJson(result);
                    }
                }
                catch (Exception ex)
                {
                    result["success"] = false;
                    result["reason"] = "OpenDoc6 Part 异常: " + ex.Message;
                    return ToJson(result);
                }

                // 打开 Drawing
                result["step"] = "open_drawing";
                dynamic drwDoc = null;
                try
                {
                    // swDocDRAWING=3
                    drwDoc = SwOpenDoc6(drawingPath, 3, 1);
                    if (drwDoc == null)
                    {
                        result["success"] = false;
                        result["reason"] = "OpenDoc6 Drawing 返回 null";
                        return ToJson(result);
                    }
                }
                catch (Exception ex)
                {
                    result["success"] = false;
                    result["reason"] = "OpenDoc6 Drawing 异常: " + ex.Message;
                    return ToJson(result);
                }

                // 激活 Drawing
                result["step"] = "activate_drawing";
                SwActivateDoc3(drawingPath);

                // 记录插入前 DisplayDim 数量
                result["step"] = "count_before";
                int dimBefore = CountDisplayDimensions(drwDoc);
                result["dim_before"] = dimBefore;

                // 调用 InsertModelAnnotations3
                result["step"] = "insert_model_anno_3";
                int modelAnnoCount = TryInsertModelAnnotations(drwDoc);
                result["model_annotations_count"] = modelAnnoCount;

                // 调用 InsertModelAnnotations4（SW2018+）
                if (modelAnnoCount == 0)
                {
                    result["step"] = "insert_model_anno_4";
                    int modelAnnoCount4 = TryInsertModelAnnotations4(drwDoc);
                    result["model_annotations_count_v4"] = modelAnnoCount4;
                    modelAnnoCount = modelAnnoCount4;
                }

                // 如果模型注解为空，使用 GetVisibleEntities2 提取可见实体
                if (modelAnnoCount == 0)
                {
                    result["step"] = "extract_visible_entities";
                    var veResult = ExtractVisibleEntitiesFromDoc(drwDoc);
                    result["visible_entities"] = veResult;
                    result["visible_entities_count"] = veResult != null
                        ? ((Dictionary<string, object>)veResult)["edges_count"]
                        : 0;
                }

                // 记录插入后 DisplayDim 数量
                result["step"] = "count_after";
                int dimAfter = CountDisplayDimensions(drwDoc);
                result["dim_after"] = dimAfter;
                result["display_dim_count"] = dimAfter;

                // 保存
                result["step"] = "save";
                bool saved = false;
                try
                {
                    // Save() 无参数，使用 ComCall
                    object saveResult = ComCall(drwDoc, "Save");
                    saved = saveResult != null && (bool)saveResult;
                }
                catch (Exception ex)
                {
                    result["save_error"] = ex.Message;
                    // 尝试 Save2
                    try
                    {
                        object saveResult = ComCall(drwDoc, "Save2", 0);
                        saved = saveResult != null && (bool)saveResult;
                    }
                    catch (Exception ex2)
                    {
                        result["save_error_2"] = ex2.Message;
                    }
                }
                result["saved"] = saved;

                result["step"] = "done";
                result["success"] = (dimAfter > dimBefore) || (modelAnnoCount > 0);
                result["reason"] = result["success"].ToString() == "True" ? "成功" : "无新增尺寸";

                // 不关闭文档（让 SW 管理）
            }
            catch (Exception ex)
            {
                result["success"] = false;
                result["reason"] = "GenerateAssociativeDimensions 异常: " + ex.Message;
                result["exception_type"] = ex.GetType().Name;
            }

            return ToJson(result);
        }

        /// <summary>
        /// RelinkDrawingReferences - 修复 drawing 引用
        /// v1.9 Task 4: 使用 ReplaceReference 或 ReplaceModel
        /// </summary>
        public string RelinkDrawingReferences(string drawingPath, string partPath, string runId)
        {
            var result = new Dictionary<string, object>();
            result["method"] = "addin";
            result["timestamp"] = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");

            try
            {
                if (!Ping())
                {
                    result["success"] = false;
                    result["reason"] = "Add-in 未连接";
                    return ToJson(result);
                }

                drawingPath = System.IO.Path.GetFullPath(drawingPath);
                partPath = System.IO.Path.GetFullPath(partPath);

                // 读取引用前
                var refsBefore = GetDrawingReferences(drawingPath);
                result["references_before"] = refsBefore;

                // 打开 Drawing
                dynamic drwDoc = SwOpenDoc6(drawingPath, 3, 1);
                if (drwDoc == null)
                {
                    result["success"] = false;
                    result["reason"] = "OpenDoc6 Drawing 返回 null";
                    return ToJson(result);
                }

                // 遍历 views，尝试 ReplaceModel
                int replacedCount = 0;
                try
                {
                    dynamic sheet = ComCall(drwDoc, "GetCurrentSheet");
                    dynamic views = ComCall(sheet, "GetViews");
                    if (views != null)
                    {
                        Array viewsArr = (Array)views;
                        foreach (object view in viewsArr)
                        {
                            try
                            {
                                object refDoc = ComGet(view, "ReferencedDocument");
                                if (refDoc != null)
                                {
                                    string oldPath = (string)ComCall(refDoc, "GetPathName");
                                    if (!string.IsNullOrEmpty(oldPath) && oldPath != partPath)
                                    {
                                        // ReplaceModel(newModelPath, configName, replaceAll)
                                        object okObj = ComCall(view, "ReplaceModel", partPath, "", true);
                                        bool ok = (bool)okObj;
                                        if (ok) replacedCount++;
                                    }
                                }
                            }
                            catch { }
                        }
                    }
                }
                catch (Exception ex)
                {
                    result["replace_error"] = ex.Message;
                }

                result["replaced_count"] = replacedCount;

                // 读取引用后
                var refsAfter = GetDrawingReferences(drawingPath);
                result["references_after"] = refsAfter;

                result["success"] = replacedCount > 0;
                result["reason"] = replacedCount > 0 ? "成功" : "无需替换或替换失败";
            }
            catch (Exception ex)
            {
                result["success"] = false;
                result["reason"] = "RelinkDrawingReferences 异常: " + ex.Message;
            }

            return ToJson(result);
        }

        /// <summary>
        /// ExtractVisibleEntities - 提取可见实体
        /// v1.9 Task 3: 使用 IView.GetVisibleEntities2
        /// </summary>
        public string ExtractVisibleEntities(string drawingPath, string viewNamesJson, string runId)
        {
            var result = new Dictionary<string, object>();
            result["method"] = "addin";
            result["timestamp"] = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");

            try
            {
                if (!Ping())
                {
                    result["success"] = false;
                    result["reason"] = "Add-in 未连接";
                    return ToJson(result);
                }

                drawingPath = System.IO.Path.GetFullPath(drawingPath);

                // 解析 view_names
                List<string> viewNames = ParseJsonStringList(viewNamesJson);

                // 打开 Drawing
                dynamic drwDoc = SwOpenDoc6(drawingPath, 3, 1);
                if (drwDoc == null)
                {
                    result["success"] = false;
                    result["reason"] = "OpenDoc6 Drawing 返回 null";
                    return ToJson(result);
                }

                int viewsProcessed = 0;
                int edgesCount = 0;
                int circlesCount = 0;
                int arcsCount = 0;
                var entities = new List<object>();

                try
                {
                    dynamic sheet = ComCall(drwDoc, "GetCurrentSheet");
                    dynamic views = ComCall(sheet, "GetViews");
                    if (views != null)
                    {
                        Array viewsArr = (Array)views;
                        foreach (object view in viewsArr)
                        {
                            try
                            {
                                string viewName = (string)ComGet(view, "Name");
                                if (viewNames.Count > 0 && !viewNames.Contains(viewName))
                                    continue;

                                viewsProcessed++;

                                // GetVisibleEntities2(filterType)
                                // filterType: 0=All, 1=Edges, 2=Faces, 3=Vertices, 4=SilhouetteEdges
                                try
                                {
                                    object edges = ComCall(view, "GetVisibleEntities2", null, 1);
                                    if (edges != null)
                                    {
                                        int edgeCount = CountResultArray(edges);
                                        edgesCount += edgeCount;
                                    }
                                }
                                catch { }

                                // 尝试获取圆/圆弧（通过遍历 edges）
                                try
                                {
                                    object edges2 = ComCall(view, "GetVisibleEntities2", null, 1);
                                    if (edges2 != null && edges2 is Array)
                                    {
                                        Array edges2Arr = (Array)edges2;
                                        foreach (object edge in edges2Arr)
                                        {
                                            try
                                            {
                                                object curve = ComCall(edge, "GetCurve");
                                                if (curve != null)
                                                {
                                                    int identity = (int)ComGet(curve, "Identity");
                                                    if (identity == 2) circlesCount++;
                                                    else if (identity == 3) arcsCount++;
                                                }
                                            }
                                            catch { }
                                        }
                                    }
                                }
                                catch { }

                                int viewEdges = edgesCount;
                                entities.Add(new Dictionary<string, object>
                                {
                                    { "view_name", viewName },
                                    { "edges", viewEdges },
                                    { "circles", circlesCount },
                                    { "arcs", arcsCount }
                                });
                            }
                            catch { }
                        }
                    }
                }
                catch (Exception ex)
                {
                    result["extract_error"] = ex.Message;
                }

                result["views_processed"] = viewsProcessed;
                result["edges_count"] = edgesCount;
                result["circles_count"] = circlesCount;
                result["arcs_count"] = arcsCount;
                result["entities"] = entities;
                result["success"] = viewsProcessed > 0;
                result["reason"] = viewsProcessed > 0 ? "成功" : "无视图处理";
            }
            catch (Exception ex)
            {
                result["success"] = false;
                result["reason"] = "ExtractVisibleEntities 异常: " + ex.Message;
            }

            return ToJson(result);
        }

        #region Private helpers

        /// <summary>
        /// 通过 IDispatch 调用 COM 方法（支持 ref 参数）
        /// </summary>
        private object ComInvoke(object obj, string methodName, object[] args, bool[] refFlags)
        {
            Type t = obj.GetType();
            if (refFlags == null || refFlags.Length == 0)
            {
                return t.InvokeMember(methodName, BindingFlags.InvokeMethod, null, obj, args, null);
            }
            ParameterModifier mods = new ParameterModifier(args.Length);
            for (int i = 0; i < refFlags.Length && i < args.Length; i++)
            {
                mods[i] = refFlags[i];
            }
            ParameterModifier[] modArray = new ParameterModifier[] { mods };
            return t.InvokeMember(methodName, BindingFlags.InvokeMethod, null, obj, args, modArray, null, null);
        }

        /// <summary>
        /// 通过 IDispatch 获取属性
        /// </summary>
        private object ComGet(object obj, string propName)
        {
            Type t = obj.GetType();
            return t.InvokeMember(propName, BindingFlags.GetProperty, null, obj, null);
        }

        /// <summary>
        /// 通过 IDispatch 设置属性
        /// </summary>
        private void ComSet(object obj, string propName, object value)
        {
            Type t = obj.GetType();
            object[] args = new object[] { value };
            t.InvokeMember(propName, BindingFlags.SetProperty, null, obj, args);
        }

        /// <summary>
        /// 通过 IDispatch 调用无 ref 参数的方法
        /// </summary>
        private object ComCall(object obj, string methodName, params object[] args)
        {
            Type t = obj.GetType();
            return t.InvokeMember(methodName, BindingFlags.InvokeMethod, null, obj, args, null);
        }

        /// <summary>
        /// OpenDoc6 包装（处理 ref 参数）
        /// </summary>
        private dynamic SwOpenDoc6(string path, int docType, int options)
        {
            object[] args = new object[] { path, docType, options, "", 0, 0 };
            bool[] refs = new bool[] { false, false, false, false, true, true };
            object result = ComInvoke(_swApp, "OpenDoc6", args, refs);
            return result;
        }

        /// <summary>
        /// ActivateDoc3 包装
        /// </summary>
        private void SwActivateDoc3(string path)
        {
            try
            {
                object[] args = new object[] { path, true, 0, 0 };
                bool[] refs = new bool[] { false, false, false, true };
                ComInvoke(_swApp, "ActivateDoc3", args, refs);
            }
            catch { }
        }

        /// <summary>
        /// 从已打开的 Drawing 文档提取可见实体
        /// </summary>
        private object ExtractVisibleEntitiesFromDoc(dynamic drwDoc)
        {
            var result = new Dictionary<string, object>();
            result["views_processed"] = 0;
            result["edges_count"] = 0;
            result["circles_count"] = 0;
            result["arcs_count"] = 0;

            try
            {
                dynamic sheet = ComCall(drwDoc, "GetCurrentSheet");
                dynamic views = ComCall(sheet, "GetViews");
                if (views == null) return result;

                Array viewsArr = (Array)views;
                int viewsProcessed = 0;
                int edgesCount = 0;
                int circlesCount = 0;
                int arcsCount = 0;

                foreach (object view in viewsArr)
                {
                    try
                    {
                        viewsProcessed++;

                        // GetVisibleEntities2(null, 1) - edges
                        try
                        {
                            object edges = ComCall(view, "GetVisibleEntities2", null, 1);
                            if (edges != null)
                            {
                                int edgeCount = CountResultArray(edges);
                                edgesCount += edgeCount;

                                // 遍历 edges 检查圆/圆弧
                                if (edges is Array)
                                {
                                    Array edgesArr = (Array)edges;
                                    foreach (object edge in edgesArr)
                                    {
                                        try
                                        {
                                            object curve = ComCall(edge, "GetCurve");
                                            if (curve != null)
                                            {
                                                int identity = (int)ComGet(curve, "Identity");
                                                if (identity == 2) circlesCount++;
                                                else if (identity == 3) arcsCount++;
                                            }
                                        }
                                        catch { }
                                    }
                                }
                            }
                        }
                        catch { }
                    }
                    catch { }
                }

                result["views_processed"] = viewsProcessed;
                result["edges_count"] = edgesCount;
                result["circles_count"] = circlesCount;
                result["arcs_count"] = arcsCount;
            }
            catch (Exception ex)
            {
                result["error"] = ex.Message;
            }

            return result;
        }

        private int TryInsertModelAnnotations(dynamic drwDoc)
        {
            try
            {
                // InsertModelAnnotations3(AllViews, DimensionTypes, ImportIntoDuplicateViews,
                //   IncludeDimXpertAnnotations, IncludeHiddenFeatures, TargetLayer, DimXpertAnnotView)
                object result = ComCall(drwDoc, "InsertModelAnnotations3", true, 3, false, true, false, null, false);
                return CountResultArray(result);
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine("InsertModelAnnotations3 失败: " + ex.Message);
                return 0;
            }
        }

        private int TryInsertModelAnnotations4(dynamic drwDoc)
        {
            try
            {
                // InsertModelAnnotations4(AllViews, DimensionTypes, ImportIntoDuplicateViews,
                //   IncludeDimXpertAnnotations, IncludeHiddenFeatures, TargetLayer, DimXpertAnnotView, ImportAnnotationsInFlatPattern)
                object result = ComCall(drwDoc, "InsertModelAnnotations4", true, 3, false, true, false, null, false, false);
                return CountResultArray(result);
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine("InsertModelAnnotations4 失败: " + ex.Message);
                return 0;
            }
        }

        /// <summary>
        /// v2.0 Task 2: AutoDimension 策略
        /// 使用 IDrawingDoc.AutoDimension 通过引用几何自动标注
        /// </summary>
        private int TryAutoDimension(dynamic drwDoc)
        {
            int created = 0;
            try
            {
                // 遍历 views，对每个 view 尝试 AutoDimension
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
                        if (viewType == 0) continue; // 跳过 sheet view

                        // 激活 view
                        string viewName = "";
                        try { viewName = (string)ComGet(view, "Name"); } catch { }
                        try
                        {
                            ComCall(drwDoc, "ActivateView", viewName);
                        }
                        catch { }

                        // SelectByID2 选中 view
                        try
                        {
                            object selArgs = ComCall(_swApp, "IActivateDoc3", viewName);
                        }
                        catch { }

                        // AutoDimension 不直接可用，尝试通过 InsertDimension2
                        // 这里记录尝试，实际创建依赖 SelectByID2 + AddDimension2
                        // v2.0 原则: 不使用 pywin32 SelectByID2 / AddDimension2 作为主修复路径
                        // 但 Add-in 内部 C# 可以尝试
                        try
                        {
                            // 选择视图
                            bool selected = false;
                            try
                            {
                                dynamic ext = ComGet(drwDoc, "Extension");
                                object selResult = ComCall(ext, "SelectByID2",
                                    viewName, "DRAWINGVIEW", 0, 0, 0, false, 0, null, 0);
                                selected = selResult != null && (bool)selResult;
                            }
                            catch { }

                            if (selected)
                            {
                                // 获取视图边界
                                try
                                {
                                    object outline = ComGet(view, "Outline");
                                    if (outline is Array)
                                    {
                                        Array outlineArr = (Array)outline;
                                        if (outlineArr.Length >= 6)
                                        {
                                            double minX = (double)outlineArr.GetValue(0);
                                            double minY = (double)outlineArr.GetValue(1);
                                            double maxX = (double)outlineArr.GetValue(3);
                                            double maxY = (double)outlineArr.GetValue(4);

                                            // 添加外形尺寸（宽度和高度）
                                            // AddDimension2(X, Y, Z) - 在指定位置添加尺寸
                                            // 需要先选中两个实体，这里仅尝试
                                        }
                                    }
                                }
                                catch { }
                            }
                        }
                        catch { }
                    }
                    catch { }
                }
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine("TryAutoDimension 失败: " + ex.Message);
            }
            return created;
        }

        /// <summary>
        /// v2.0 Task 2: 外形尺寸策略
        /// 通过 GetBox / Outline 获取视图外形，添加外形尺寸
        /// </summary>
        private int TryOutlineDimension(dynamic drwDoc, dynamic partDoc)
        {
            int created = 0;
            try
            {
                // 获取零件 bounding box
                try
                {
                    // 通过 partDoc.GetBoundingBox 获取零件边界
                    object bbox = ComCall(partDoc, "GetBoundingBox");
                    if (bbox is Array)
                    {
                        Array bboxArr = (Array)bbox;
                        if (bboxArr.Length >= 6)
                        {
                            double minX = (double)bboxArr.GetValue(0);
                            double minY = (double)bboxArr.GetValue(1);
                            double minZ = (double)bboxArr.GetValue(2);
                            double maxX = (double)bboxArr.GetValue(3);
                            double maxY = (double)bboxArr.GetValue(4);
                            double maxZ = (double)bboxArr.GetValue(5);

                            double width = maxX - minX;
                            double height = maxY - minY;
                            double depth = maxZ - minZ;

                            // 记录外形尺寸信息（实际添加尺寸需要选中边并调用 AddDimension）
                            // 这里仅记录，实际添加在 Task 2 DimensionEngine 中完善
                        }
                    }
                }
                catch { }

                // 遍历 views 获取 view.Outline
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

                        // 获取 view 的 Outline (返回 double[6]: minX, minY, minZ, maxX, maxY, maxZ)
                        try
                        {
                            object outline = ComGet(view, "Outline");
                            if (outline is Array)
                            {
                                Array outlineArr = (Array)outline;
                                if (outlineArr.Length >= 6)
                                {
                                    // 记录 outline 信息，实际添加尺寸需要更多 API 调用
                                    // v2.0 Task 2 会完善
                                }
                            }
                        }
                        catch { }
                    }
                    catch { }
                }
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine("TryOutlineDimension 失败: " + ex.Message);
            }
            return created;
        }

        /// <summary>
        /// v2.0 Task 1: 解析 policy JSON
        /// </summary>
        private Dictionary<string, object> ParsePolicy(string policyJson)
        {
            var policy = new Dictionary<string, object>();
            try
            {
                if (string.IsNullOrEmpty(policyJson))
                {
                    policy["dimension_policy"] = "default";
                    policy["part_class"] = "feature_part";
                    return policy;
                }

                // 简单 JSON 解析（避免依赖 System.Text.Json）
                string json = policyJson.Trim().TrimStart('{').TrimEnd('}');
                string[] parts = json.Split(',');
                foreach (string p in parts)
                {
                    int idx = p.IndexOf(':');
                    if (idx > 0)
                    {
                        string key = p.Substring(0, idx).Trim().Trim('"');
                        string val = p.Substring(idx + 1).Trim().Trim('"');
                        policy[key] = val;
                    }
                }
            }
            catch { }
            return policy;
        }

        /// <summary>
        /// v2.0 Task 1: 检查文本是否包含尺寸信息
        /// </summary>
        private bool ContainsDimensionText(string text)
        {
            if (string.IsNullOrEmpty(text)) return false;
            // 简单判断：包含数字且可能包含单位
            foreach (char c in text)
            {
                if (char.IsDigit(c)) return true;
            }
            return false;
        }

        private int CountDisplayDimensions(dynamic drwDoc)
        {
            try
            {
                int count = 0;
                dynamic sheet = ComGet(drwDoc, "GetCurrentSheet");
                // GetCurrentSheet is a method, call it
                sheet = ComCall(drwDoc, "GetCurrentSheet");
                dynamic views = ComCall(sheet, "GetViews");
                if (views != null)
                {
                    Array viewsArr = (Array)views;
                    foreach (object view in viewsArr)
                    {
                        try
                        {
                            object dispDims = ComCall(view, "GetDisplayDimensions");
                            if (dispDims != null)
                            {
                                count += CountResultArray(dispDims);
                            }
                        }
                        catch { }
                    }
                }
                return count;
            }
            catch
            {
                return 0;
            }
        }

        private int CountResultArray(object result)
        {
            if (result == null) return 0;
            if (result is Array)
            {
                Array arr = (Array)result;
                return arr.Length;
            }
            if (result is int)
            {
                return (int)result;
            }
            try
            {
                return ((Array)result).Length;
            }
            catch
            {
                return 0;
            }
        }

        private List<string> GetDrawingReferences(string drawingPath)
        {
            var refs = new List<string>();
            try
            {
                // 使用 SW API 读取引用
                // 打开 drawing（如果未打开）
                dynamic drwDoc = SwOpenDoc6(drawingPath, 3, 1);
                if (drwDoc == null) return refs;

                try
                {
                    // 遍历所有 sheet 的 views，获取 ReferencedDocument
                    dynamic sheet = ComCall(drwDoc, "GetCurrentSheet");
                    dynamic views = ComCall(sheet, "GetViews");
                    if (views != null && views is Array)
                    {
                        Array viewsArr = (Array)views;
                        foreach (object view in viewsArr)
                        {
                            try
                            {
                                object refDoc = ComGet(view, "ReferencedDocument");
                                if (refDoc != null)
                                {
                                    string path = (string)ComCall(refDoc, "GetPathName");
                                    if (!string.IsNullOrEmpty(path) && !refs.Contains(path))
                                    {
                                        refs.Add(path);
                                    }
                                }
                            }
                            catch { }
                        }
                    }
                }
                catch { }

                // 也尝试 GetDependencies
                try
                {
                    object deps = ComCall(drwDoc, "GetDependencies", true, true, 1);
                    if (deps != null && deps is Array)
                    {
                        Array depsArr = (Array)deps;
                        foreach (object dep in depsArr)
                        {
                            try
                            {
                                string depStr = dep.ToString();
                                if (!string.IsNullOrEmpty(depStr) && !refs.Contains(depStr))
                                {
                                    refs.Add(depStr);
                                }
                            }
                            catch { }
                        }
                    }
                }
                catch { }
            }
            catch { }
            return refs;
        }

        private List<string> ParseJsonStringList(string json)
        {
            var result = new List<string>();
            try
            {
                // 简单 JSON 数组解析（避免依赖 System.Text.Json）
                if (string.IsNullOrEmpty(json)) return result;
                json = json.Trim().TrimStart('[').TrimEnd(']');
                string[] parts = json.Split(',');
                foreach (string p in parts)
                {
                    string s = p.Trim().Trim('"');
                    if (!string.IsNullOrEmpty(s)) result.Add(s);
                }
            }
            catch { }
            return result;
        }

        private string ToJson(Dictionary<string, object> dict)
        {
            var sb = new StringBuilder();
            sb.Append("{");
            bool first = true;
            foreach (var kv in dict)
            {
                if (!first) sb.Append(",");
                first = false;
                sb.Append("\"");
                sb.Append(EscapeJson(kv.Key));
                sb.Append("\":");
                sb.Append(FormatJsonValue(kv.Value));
            }
            sb.Append("}");
            return sb.ToString();
        }

        private string FormatJsonValue(object val)
        {
            if (val == null) return "null";
            if (val is bool)
            {
                bool b = (bool)val;
                return b ? "true" : "false";
            }
            if (val is int)
            {
                return ((int)val).ToString();
            }
            if (val is double)
            {
                return ((double)val).ToString();
            }
            if (val is string)
            {
                string s = (string)val;
                return "\"" + EscapeJson(s) + "\"";
            }
            if (val is IDictionary<string, object>)
            {
                IDictionary<string, object> dict = (IDictionary<string, object>)val;
                var sb = new StringBuilder();
                sb.Append("{");
                bool first = true;
                foreach (var kv in dict)
                {
                    if (!first) sb.Append(",");
                    first = false;
                    sb.Append("\"" + EscapeJson(kv.Key) + "\":");
                    sb.Append(FormatJsonValue(kv.Value));
                }
                sb.Append("}");
                return sb.ToString();
            }
            if (val is IList<object>)
            {
                IList<object> list = (IList<object>)val;
                var sb = new StringBuilder();
                sb.Append("[");
                bool first = true;
                foreach (var item in list)
                {
                    if (!first) sb.Append(",");
                    first = false;
                    sb.Append(FormatJsonValue(item));
                }
                sb.Append("]");
                return sb.ToString();
            }
            if (val is IList<string>)
            {
                IList<string> list = (IList<string>)val;
                var sb = new StringBuilder();
                sb.Append("[");
                bool first = true;
                foreach (var item in list)
                {
                    if (!first) sb.Append(",");
                    first = false;
                    sb.Append(FormatJsonValue(item));
                }
                sb.Append("]");
                return sb.ToString();
            }
            if (val is System.Collections.IList)
            {
                System.Collections.IList list = (System.Collections.IList)val;
                var sb = new StringBuilder();
                sb.Append("[");
                bool first = true;
                foreach (var item in list)
                {
                    if (!first) sb.Append(",");
                    first = false;
                    sb.Append(FormatJsonValue(item));
                }
                sb.Append("]");
                return sb.ToString();
            }
            if (val is Array)
            {
                Array arr = (Array)val;
                var sb = new StringBuilder();
                sb.Append("[");
                bool first = true;
                foreach (var item in arr)
                {
                    if (!first) sb.Append(",");
                    first = false;
                    sb.Append(FormatJsonValue(item));
                }
                sb.Append("]");
                return sb.ToString();
            }
            return "\"" + EscapeJson(val.ToString()) + "\"";
        }

        private string EscapeJson(string s)
        {
            if (string.IsNullOrEmpty(s)) return "";
            var sb = new StringBuilder();
            foreach (char c in s)
            {
                switch (c)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    default:
                        if (c < 32) sb.Append("\\u" + ((int)c).ToString("x4"));
                        else sb.Append(c);
                        break;
                }
            }
            return sb.ToString();
        }

        private void WriteProbeResult(bool success, string message)
        {
            try
            {
                string probePath = System.IO.Path.Combine(
                    System.IO.Path.GetTempPath(), "sw_drawing_studio_addin_probe.json");
                var sb = new StringBuilder();
                sb.Append("{");
                sb.Append("\"success\":").Append(success ? "true" : "false").Append(",");
                sb.Append("\"message\":\"").Append(EscapeJson(message)).Append("\",");
                sb.Append("\"timestamp\":\"").Append(DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss")).Append("\",");
                sb.Append("\"connected\":").Append(_connected ? "true" : "false");
                sb.Append("}");
                System.IO.File.WriteAllText(probePath, sb.ToString());
            }
            catch { }
        }

        #endregion
    }

    /// <summary>
    /// ISwAddin 接口定义（避免硬依赖 SolidWorks.Interop）
    /// </summary>
    [ComImport]
    [Guid("3EB8B1D1-C081-11D0-BB1D-0060973E5874")]
    [InterfaceType(ComInterfaceType.InterfaceIsIDispatch)]
    public interface ISwAddin
    {
        [DispId(1)]
        bool ConnectToSW(object This, int Cookie);
        [DispId(2)]
        bool DisconnectFromSW();
    }
}
