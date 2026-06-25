using System;
using System.Collections.Generic;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;

namespace SwDrawingStudioAddin
{
    /// <summary>
    /// v2.0 Task 3: Visible Entity Extractor
    ///
    /// ActivateDoc3 -> ActivateSheet -> GetFirstView/GetNextView
    /// 对每个非 sheet view 获取 visible components
    /// 对每个 component 调 GetVisibleEntities2(edge/face/curve)
    ///
    /// 输出 view_entities.json
    /// 若 edges=0，必须给 reason
    /// </summary>
    public class ViewEntityExtractor
    {
        private object _swApp;

        public ViewEntityExtractor(object swApp)
        {
            _swApp = swApp;
        }

        /// <summary>
        /// 提取 drawing 中所有 view 的可见实体
        /// </summary>
        public Dictionary<string, object> Extract(
            string drawingPath,
            List<string> viewNames,
            string runId)
        {
            var result = new Dictionary<string, object>();
            result["extractor_version"] = "v2.0";
            result["timestamp"] = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
            result["drawing_path"] = drawingPath;

            try
            {
                dynamic drwDoc = OpenDrawing(drawingPath);
                if (drwDoc == null)
                {
                    result["success"] = false;
                    result["reason"] = "OpenDoc6 Drawing 返回 null";
                    return result;
                }

                ActivateDoc(drawingPath);

                var viewsData = new List<object>();
                int totalEdges = 0;
                int totalFaces = 0;
                int totalVertices = 0;
                int totalCircles = 0;
                int totalArcs = 0;
                int totalComponents = 0;
                int viewsProcessed = 0;

                // 遍历所有 sheet
                Array sheetsArr = GetSheets(drwDoc);
                foreach (object sheet in sheetsArr)
                {
                    try
                    {
                        string sheetName = (string)ComGet(sheet, "Name");
                        // 激活 sheet
                        try { ComCall(drwDoc, "ActivateSheet", sheetName); } catch { }

                        // 获取 sheet 的 views
                        // 使用 GetFirstView / GetNextView 遍历
                        dynamic firstView = ComCall(sheet, "GetFirstView");
                        object currentView = firstView;

                        while (currentView != null)
                        {
                            try
                            {
                                string viewName = "";
                                int viewType = 0;
                                try { viewName = (string)ComGet(currentView, "Name"); } catch { }
                                try { viewType = (int)ComGet(currentView, "Type"); } catch { }

                                // 跳过 sheet view (type=0)
                                if (viewType == 0)
                                {
                                    currentView = ComCall(currentView, "GetNextView");
                                    continue;
                                }

                                if (viewNames.Count > 0 && !viewNames.Contains(viewName))
                                {
                                    currentView = ComCall(currentView, "GetNextView");
                                    continue;
                                }

                                viewsProcessed++;

                                var viewData = ExtractViewEntities(drwDoc, currentView, sheetName, viewName, viewType);
                                viewsData.Add(viewData);

                                // 累加总数
                                Dictionary<string, object> vd = (Dictionary<string, object>)viewData;
                                totalEdges += (int)vd["edges"];
                                totalFaces += (int)vd["faces"];
                                totalVertices += (int)vd["vertices"];
                                totalCircles += (int)vd["circles"];
                                totalArcs += (int)vd["arcs"];
                                totalComponents += (int)vd["component_count"];
                            }
                            catch { }

                            try
                            {
                                currentView = ComCall(currentView, "GetNextView");
                            }
                            catch { break; }
                        }
                    }
                    catch { }
                }

                result["views_processed"] = viewsProcessed;
                result["total_edges"] = totalEdges;
                result["total_faces"] = totalFaces;
                result["total_vertices"] = totalVertices;
                result["total_circles"] = totalCircles;
                result["total_arcs"] = totalArcs;
                result["total_components"] = totalComponents;
                result["views"] = viewsData;
                result["success"] = viewsProcessed > 0;
                result["reason"] = viewsProcessed > 0
                    ? (totalEdges > 0 ? "成功提取可见实体" : "处理成功但 edges=0（SW2025 限制：GetVisibleEntities2 需要 component 参数）")
                    : "无视图处理";
            }
            catch (Exception ex)
            {
                result["success"] = false;
                result["reason"] = "ViewEntityExtractor 异常: " + ex.Message;
            }

            return result;
        }

        /// <summary>
        /// v2.1 Task 2: ExtractV2 - 新增 GetLines2 fallback
        ///
        /// 当 GetVisibleEntities2 返回 0 edges 时，fallback 到 GetLines2
        /// 输出 view_entities_v2.json，包含 reason_if_zero
        /// </summary>
        public Dictionary<string, object> ExtractV2(
            string drawingPath,
            List<string> viewNames,
            string runId)
        {
            var result = new Dictionary<string, object>();
            result["extractor_version"] = "v2.1";
            result["timestamp"] = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
            result["drawing_path"] = drawingPath;

            try
            {
                dynamic drwDoc = OpenDrawing(drawingPath);
                if (drwDoc == null)
                {
                    result["success"] = false;
                    result["reason"] = "OpenDoc6 Drawing 返回 null";
                    return result;
                }

                ActivateDoc(drawingPath);

                var viewsData = new List<object>();
                int totalEdges = 0;
                int totalLines = 0;
                int totalCircles = 0;
                int totalArcs = 0;
                int totalComponents = 0;
                int viewsProcessed = 0;
                int viewsWithGetLines2Fallback = 0;

                Array sheetsArr = GetSheets(drwDoc);
                foreach (object sheet in sheetsArr)
                {
                    try
                    {
                        string sheetName = (string)ComGet(sheet, "Name");
                        try { ComCall(drwDoc, "ActivateSheet", sheetName); } catch { }

                        dynamic firstView = ComCall(sheet, "GetFirstView");
                        object currentView = firstView;

                        while (currentView != null)
                        {
                            try
                            {
                                string viewName = "";
                                int viewType = 0;
                                try { viewName = (string)ComGet(currentView, "Name"); } catch { }
                                try { viewType = (int)ComGet(currentView, "Type"); } catch { }

                                if (viewType == 0)
                                {
                                    currentView = ComCall(currentView, "GetNextView");
                                    continue;
                                }

                                if (viewNames.Count > 0 && !viewNames.Contains(viewName))
                                {
                                    currentView = ComCall(currentView, "GetNextView");
                                    continue;
                                }

                                viewsProcessed++;

                                var viewData = ExtractViewEntitiesV2(drwDoc, currentView, sheetName, viewName, viewType);
                                viewsData.Add(viewData);

                                Dictionary<string, object> vd = (Dictionary<string, object>)viewData;
                                totalEdges += (int)vd["edges"];
                                totalLines += (int)vd["lines_count"];
                                totalCircles += (int)vd["circles"];
                                totalArcs += (int)vd["arcs"];
                                totalComponents += (int)vd["component_count"];
                                if ((bool)vd["used_getlines2_fallback"])
                                {
                                    viewsWithGetLines2Fallback++;
                                }
                            }
                            catch { }

                            try
                            {
                                currentView = ComCall(currentView, "GetNextView");
                            }
                            catch { break; }
                        }
                    }
                    catch { }
                }

                result["views_processed"] = viewsProcessed;
                result["total_edges"] = totalEdges;
                result["total_lines"] = totalLines;
                result["total_circles"] = totalCircles;
                result["total_arcs"] = totalArcs;
                result["total_components"] = totalComponents;
                result["views_with_getlines2_fallback"] = viewsWithGetLines2Fallback;
                result["views"] = viewsData;
                result["success"] = viewsProcessed > 0;

                // reason_if_zero
                if (viewsProcessed > 0 && totalEdges == 0 && totalLines == 0)
                {
                    result["reason_if_zero"] = "GetVisibleEntities2 和 GetLines2 均返回 0（SW2025 限制：view 可能未激活或无可见几何）";
                }
                else if (viewsProcessed > 0 && totalEdges == 0 && totalLines > 0)
                {
                    result["reason_if_zero"] = "GetVisibleEntities2 返回 0 edges，但 GetLines2 fallback 成功获取 " + totalLines + " 条线段";
                }
                else if (viewsProcessed > 0 && totalEdges > 0)
                {
                    result["reason_if_zero"] = "";
                }
                else
                {
                    result["reason_if_zero"] = "无视图处理";
                }

                result["reason"] = viewsProcessed > 0
                    ? (totalEdges > 0 ? "成功提取可见实体" : (totalLines > 0 ? "GetLines2 fallback 成功" : "edges=0 且 lines=0"))
                    : "无视图处理";
            }
            catch (Exception ex)
            {
                result["success"] = false;
                result["reason"] = "ViewEntityExtractor v2 异常: " + ex.Message;
            }

            return result;
        }

        /// <summary>
        /// v2.1: 对单个 view 提取可见实体 + GetLines2 fallback
        /// </summary>
        private Dictionary<string, object> ExtractViewEntitiesV2(
            dynamic drwDoc, object view,
            string sheetName, string viewName, int viewType)
        {
            var viewData = new Dictionary<string, object>();
            viewData["sheet_name"] = sheetName;
            viewData["view_name"] = viewName;
            viewData["view_type"] = viewType;

            int edgeCount = 0;
            int faceCount = 0;
            int vertexCount = 0;
            int circleCount = 0;
            int arcCount = 0;
            int componentCount = 0;
            int linesCount = 0;
            bool usedGetLines2Fallback = false;
            string reasonIfZero = "";

            // 1. 先尝试 GetVisibleEntities2
            try
            {
                object components = ComCall(view, "GetVisibleComponents");
                if (components != null && components is Array)
                {
                    Array compsArr = (Array)components;
                    componentCount = compsArr.Length;

                    foreach (object comp in compsArr)
                    {
                        try
                        {
                            // edges (filterType=1)
                            try
                            {
                                object edges = ComCall(view, "GetVisibleEntities2", comp, 1);
                                if (edges != null)
                                {
                                    int ec = CountArray(edges);
                                    edgeCount += ec;

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
                                                    if (identity == 2) circleCount++;
                                                    else if (identity == 3) arcCount++;
                                                }
                                            }
                                            catch { }
                                        }
                                    }
                                }
                            }
                            catch (Exception ex)
                            {
                                if (string.IsNullOrEmpty(reasonIfZero))
                                    reasonIfZero = "GetVisibleEntities2(edges) 失败: " + ex.Message;
                            }

                            // faces (filterType=2)
                            try
                            {
                                object faces = ComCall(view, "GetVisibleEntities2", comp, 2);
                                if (faces != null) faceCount += CountArray(faces);
                            }
                            catch { }

                            // vertices (filterType=3)
                            try
                            {
                                object vertices = ComCall(view, "GetVisibleEntities2", comp, 3);
                                if (vertices != null) vertexCount += CountArray(vertices);
                            }
                            catch { }
                        }
                        catch { }
                    }
                }
                else
                {
                    // 无 component，尝试无 component 参数的 GetVisibleEntities2
                    try
                    {
                        object edges = ComCall(view, "GetVisibleEntities2", null, 1);
                        if (edges != null) edgeCount += CountArray(edges);
                    }
                    catch (Exception ex)
                    {
                        reasonIfZero = "GetVisibleEntities2(null, edges) 失败: " + ex.Message;
                    }
                }
            }
            catch (Exception ex)
            {
                reasonIfZero = "GetVisibleComponents 失败: " + ex.Message;
            }

            // 2. 如果 edges=0，fallback 到 GetLines2
            if (edgeCount == 0)
            {
                try
                {
                    object lines = ComCall(view, "GetLines2");
                    if (lines != null && lines is Array)
                    {
                        Array linesArr = (Array)lines;
                        // 每条线 12 个 double
                        linesCount = linesArr.Length / 12;
                        usedGetLines2Fallback = linesCount > 0;

                        if (linesCount > 0)
                        {
                            // 分析线段类型（水平/垂直/斜线）
                            // 简单统计，不区分圆/圆弧（GetLines2 只返回直线）
                        }
                    }
                }
                catch (Exception ex)
                {
                    if (string.IsNullOrEmpty(reasonIfZero))
                    {
                        reasonIfZero = "GetLines2 失败: " + ex.Message;
                    }
                }
            }

            if (edgeCount == 0 && linesCount == 0 && string.IsNullOrEmpty(reasonIfZero))
            {
                reasonIfZero = "GetVisibleEntities2 返回 0 edges 且 GetLines2 返回 0 lines（SW2025 限制：可能需要激活 view）";
            }

            viewData["edges"] = edgeCount;
            viewData["faces"] = faceCount;
            viewData["vertices"] = vertexCount;
            viewData["circles"] = circleCount;
            viewData["arcs"] = arcCount;
            viewData["component_count"] = componentCount;
            viewData["lines_count"] = linesCount;
            viewData["used_getlines2_fallback"] = usedGetLines2Fallback;
            viewData["reason_if_zero"] = reasonIfZero;

            return viewData;
        }

        private Dictionary<string, object> ExtractViewEntities(
            dynamic drwDoc, object view,
            string sheetName, string viewName, int viewType)
        {
            var viewData = new Dictionary<string, object>();
            viewData["sheet_name"] = sheetName;
            viewData["view_name"] = viewName;
            viewData["view_type"] = viewType;

            int edgeCount = 0;
            int faceCount = 0;
            int vertexCount = 0;
            int circleCount = 0;
            int arcCount = 0;
            int componentCount = 0;
            string edgeReason = "";

            // 获取 visible components
            try
            {
                object components = ComCall(view, "GetVisibleComponents");
                if (components != null && components is Array)
                {
                    Array compsArr = (Array)components;
                    componentCount = compsArr.Length;

                    // 对每个 component 调用 GetVisibleEntities2
                    foreach (object comp in compsArr)
                    {
                        try
                        {
                            // edges (filterType=1)
                            try
                            {
                                object edges = ComCall(view, "GetVisibleEntities2", comp, 1);
                                if (edges != null)
                                {
                                    int ec = CountArray(edges);
                                    edgeCount += ec;

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
                                                    if (identity == 2) circleCount++;
                                                    else if (identity == 3) arcCount++;
                                                }
                                            }
                                            catch { }
                                        }
                                    }
                                }
                            }
                            catch (Exception ex)
                            {
                                if (string.IsNullOrEmpty(edgeReason))
                                    edgeReason = "GetVisibleEntities2(edges) 失败: " + ex.Message;
                            }

                            // faces (filterType=2)
                            try
                            {
                                object faces = ComCall(view, "GetVisibleEntities2", comp, 2);
                                if (faces != null) faceCount += CountArray(faces);
                            }
                            catch { }

                            // vertices (filterType=3)
                            try
                            {
                                object vertices = ComCall(view, "GetVisibleEntities2", comp, 3);
                                if (vertices != null) vertexCount += CountArray(vertices);
                            }
                            catch { }
                        }
                        catch { }
                    }
                }
                else
                {
                    // 无 component，尝试无 component 参数的 GetVisibleEntities2
                    try
                    {
                        object edges = ComCall(view, "GetVisibleEntities2", null, 1);
                        if (edges != null) edgeCount += CountArray(edges);
                    }
                    catch (Exception ex)
                    {
                        edgeReason = "GetVisibleEntities2(null, edges) 失败: " + ex.Message;
                    }
                }
            }
            catch (Exception ex)
            {
                edgeReason = "GetVisibleComponents 失败: " + ex.Message;
            }

            if (edgeCount == 0 && string.IsNullOrEmpty(edgeReason))
            {
                edgeReason = "GetVisibleEntities2 返回 0 edges（SW2025 限制：可能需要激活 view 或 component 参数）";
            }

            viewData["edges"] = edgeCount;
            viewData["faces"] = faceCount;
            viewData["vertices"] = vertexCount;
            viewData["circles"] = circleCount;
            viewData["arcs"] = arcCount;
            viewData["component_count"] = componentCount;
            if (edgeCount == 0)
            {
                viewData["reason"] = edgeReason;
            }

            return viewData;
        }

        #region COM helpers

        private dynamic OpenDrawing(string path)
        {
            try
            {
                object[] args = new object[] { path, 3, 1, "", 0, 0 };
                bool[] refs = new bool[] { false, false, false, false, true, true };
                Type t = _swApp.GetType();
                return t.InvokeMember("OpenDoc6", BindingFlags.InvokeMethod, null, _swApp, args,
                    new ParameterModifier[] { CreateModifier(args.Length, refs) }, null, null);
            }
            catch { return null; }
        }

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

        private Array GetSheets(dynamic drwDoc)
        {
            try
            {
                object[] args = new object[] { 0 };
                bool[] refs = new bool[] { true };
                Type t = drwDoc.GetType();
                object sheetsObj = t.InvokeMember("GetSheets", BindingFlags.InvokeMethod, null, drwDoc, args,
                    new ParameterModifier[] { CreateModifier(args.Length, refs) }, null, null);
                if (sheetsObj is Array) return (Array)sheetsObj;
            }
            catch { }
            // 回退到 GetCurrentSheet
            try
            {
                dynamic sheet = ComCall(drwDoc, "GetCurrentSheet");
                return new object[] { sheet };
            }
            catch { }
            return new object[0];
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
