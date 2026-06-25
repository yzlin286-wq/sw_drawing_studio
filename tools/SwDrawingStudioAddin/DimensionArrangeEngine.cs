using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

namespace SwDrawingStudioAddin
{
    /// <summary>
    /// v2.2 Task 4: Dimension Arrange Engine
    ///
    /// 对 DisplayDimension 按 view 分组，自动偏移到轨道。
    /// 检查尺寸文本重叠、尺寸压线、标题栏碰撞。
    ///
    /// COM-visible 方法（通过 AddinAPI 反射调用）:
    ///   ArrangeDimensions(drawing_path, run_dir, run_id) -> JSON
    /// </summary>
    public class DimensionArrangeEngine
    {
        // 标题栏区域（A4 横式，单位：米）
        private static readonly double[] TITLEBAR_BOX = { 0.102, 0.005, 0.282, 0.095 };

        // 轨道间距（米）
        private const double TRACK_GAP_M = 0.015;

        // 尺寸文本最小间距
        private const double TEXT_MIN_GAP_M = 0.008;

        /// <summary>
        /// 排列尺寸
        /// </summary>
        /// <param name="swApp">SW Application COM 对象</param>
        /// <param name="drawingPath">SLDDRW 路径</param>
        /// <param name="runDir">运行目录</param>
        /// <param name="runId">运行 ID</param>
        /// <returns>JSON 结果</returns>
        public string ArrangeDimensions(dynamic swApp, string drawingPath, string runDir, string runId)
        {
            var result = new StringBuilder();
            result.Append("{");

            try
            {
                // 打开 drawing
                dynamic doc = null;
                try
                {
                    object err = 0, warn = 0;
                    doc = swApp.OpenDoc6(drawingPath, 3, 257, "", ref err, ref warn);
                }
                catch
                {
                    try
                    {
                        doc = swApp.OpenDoc(drawingPath, 3);
                    }
                    catch (Exception ex)
                    {
                        result.Append("\"success\":false,\"reason\":\"打开失败:" + EscapeJson(ex.Message) + "\"}");
                        return result.ToString() + "}";
                    }
                }

                if (doc == null)
                {
                    result.Append("\"success\":false,\"reason\":\"OpenDoc6 返回 null\"}");
                    return result.ToString() + "}";
                }

                // 收集尺寸信息
                var dimsByView = new Dictionary<string, List<DimInfo>>();
                int totalDims = 0;

                try
                {
                    dynamic sheet = doc.GetCurrentSheet();
                    dynamic views = sheet.GetViews();
                    if (views != null)
                    {
                        foreach (dynamic view in views)
                        {
                            string viewName = view.Name;
                            dynamic dispDims = view.GetDisplayDimensions();
                            if (dispDims == null) continue;

                            var dims = new List<DimInfo>();
                            int idx = 0;
                            foreach (dynamic dd in dispDims)
                            {
                                var dimInfo = new DimInfo
                                {
                                    Index = idx,
                                    ViewName = viewName
                                };

                                // 获取文本位置
                                try
                                {
                                    dynamic textPos = dd.TextPosition;
                                    if (textPos != null)
                                    {
                                        dimInfo.TextX = (double)textPos[0];
                                        dimInfo.TextY = (double)textPos[1];
                                        dimInfo.OrigX = dimInfo.TextX;
                                        dimInfo.OrigY = dimInfo.TextY;
                                    }
                                }
                                catch { }

                                // 获取尺寸文本
                                try
                                {
                                    dynamic dim = dd.GetDimension2(0);
                                    if (dim != null)
                                    {
                                        dimInfo.Text = dim.FullName ?? "";
                                    }
                                }
                                catch { }

                                dims.Add(dimInfo);
                                idx++;
                                totalDims++;
                            }

                            if (dims.Count > 0)
                            {
                                dimsByView[viewName] = dims;
                            }
                        }
                    }
                }
                catch (Exception ex)
                {
                    result.Append("\"success\":false,\"reason\":\"收集尺寸失败:" + EscapeJson(ex.Message) + "\"");
                    return result.ToString() + "}";
                }

                // 排列前检测
                int overlapBefore = 0;
                int titlebarCollisionBefore = 0;

                var allDims = new List<DimInfo>();
                foreach (var kv in dimsByView)
                {
                    allDims.AddRange(kv.Value);
                }

                overlapBefore = DetectTextOverlaps(allDims);
                titlebarCollisionBefore = DetectTitlebarCollisions(allDims);

                // 按 view 分组排列
                int adjustedCount = 0;
                foreach (var kv in dimsByView)
                {
                    adjustedCount += ArrangeViewDimensions(doc, kv.Key, kv.Value);
                }

                // 排列后检测
                int overlapAfter = DetectTextOverlaps(allDims);
                int titlebarCollisionAfter = DetectTitlebarCollisions(allDims);

                // 保存
                try
                {
                    doc.Save2(true);
                }
                catch { }

                // 关闭
                try
                {
                    swApp.CloseDoc(doc.GetTitle());
                }
                catch { }

                result.Append("\"success\":true,");
                result.Append("\"total_dimensions\":" + totalDims + ",");
                result.Append("\"adjusted_dimensions\":" + adjustedCount + ",");
                result.Append("\"overlap_before\":" + overlapBefore + ",");
                result.Append("\"overlap_after\":" + overlapAfter + ",");
                result.Append("\"titlebar_collision_before\":" + titlebarCollisionBefore + ",");
                result.Append("\"titlebar_collision_after\":" + titlebarCollisionAfter + ",");
                result.Append("\"reason\":\"排列完成\"");
            }
            catch (Exception ex)
            {
                result.Append("\"success\":false,\"reason\":\"" + EscapeJson(ex.Message) + "\"");
            }

            result.Append("}");
            return result.ToString();
        }

        /// <summary>
        /// 排列单个视图的尺寸
        /// </summary>
        private int ArrangeViewDimensions(dynamic doc, string viewName, List<DimInfo> dims)
        {
            if (dims.Count == 0) return 0;

            int adjusted = 0;

            // 获取视图 outline
            double[] outline = GetViewOutline(doc, viewName);
            if (outline == null) return 0;

            double xmin = outline[0], ymin = outline[1], xmax = outline[2], ymax = outline[3];

            // 按 Y 坐标排序（从上到下）
            dims.Sort((a, b) => b.TextY.CompareTo(a.TextY));

            // 分配轨道
            double trackYBase = ymax + TRACK_GAP_M;
            int currentTrack = 0;
            double lastY = double.MaxValue;

            foreach (var dim in dims)
            {
                // 如果与上一个太近，移到下一轨道
                if (Math.Abs(dim.TextY - lastY) < TEXT_MIN_GAP_M)
                {
                    currentTrack++;
                }

                double trackY = trackYBase + currentTrack * TRACK_GAP_M;

                // 检查标题栏碰撞
                if (PointInTitlebar(dim.TextX, trackY))
                {
                    trackY = ymin - TRACK_GAP_M - currentTrack * TRACK_GAP_M;
                }

                // 调整位置
                if (Math.Abs(dim.TextY - trackY) > 0.001)
                {
                    dim.NewX = dim.TextX;
                    dim.NewY = trackY;
                    dim.Track = currentTrack;

                    if (SetTextPosition(doc, viewName, dim.Index, dim.NewX, dim.NewY))
                    {
                        dim.Adjusted = true;
                        adjusted++;
                    }
                }
                else
                {
                    dim.NewX = dim.TextX;
                    dim.NewY = dim.TextY;
                    dim.Track = currentTrack;
                }

                lastY = trackY;
            }

            return adjusted;
        }

        /// <summary>
        /// 获取视图 outline
        /// </summary>
        private double[] GetViewOutline(dynamic doc, string viewName)
        {
            try
            {
                dynamic sheet = doc.GetCurrentSheet();
                dynamic views = sheet.GetViews();
                if (views == null) return null;

                foreach (dynamic view in views)
                {
                    if (view.Name == viewName)
                    {
                        dynamic outl = view.GetOutline();
                        if (outl != null && outl.Length >= 4)
                        {
                            return new double[] { (double)outl[0], (double)outl[1], (double)outl[2], (double)outl[3] };
                        }
                    }
                }
            }
            catch { }
            return null;
        }

        /// <summary>
        /// 设置尺寸文本位置
        /// </summary>
        private bool SetTextPosition(dynamic doc, string viewName, int index, double x, double y)
        {
            try
            {
                dynamic sheet = doc.GetCurrentSheet();
                dynamic views = sheet.GetViews();
                if (views == null) return false;

                foreach (dynamic view in views)
                {
                    if (view.Name != viewName) continue;
                    dynamic dispDims = view.GetDisplayDimensions();
                    if (dispDims == null) return false;

                    int i = 0;
                    foreach (dynamic dd in dispDims)
                    {
                        if (i == index)
                        {
                            // 使用 VARIANT 数组设置 TextPosition
                            try
                            {
                                dd.TextPosition = new double[] { x, y };
                                return true;
                            }
                            catch
                            {
                                return false;
                            }
                        }
                        i++;
                    }
                }
            }
            catch { }
            return false;
        }

        /// <summary>
        /// 检测尺寸文本重叠
        /// </summary>
        private int DetectTextOverlaps(List<DimInfo> dims)
        {
            int count = 0;
            for (int i = 0; i < dims.Count; i++)
            {
                for (int j = i + 1; j < dims.Count; j++)
                {
                    double dx = dims[i].NewX - dims[j].NewX;
                    double dy = dims[i].NewY - dims[j].NewY;
                    double dist = Math.Sqrt(dx * dx + dy * dy);
                    if (dist < TEXT_MIN_GAP_M)
                    {
                        count++;
                    }
                }
            }
            return count;
        }

        /// <summary>
        /// 检测标题栏碰撞
        /// </summary>
        private int DetectTitlebarCollisions(List<DimInfo> dims)
        {
            int count = 0;
            foreach (var dim in dims)
            {
                if (PointInTitlebar(dim.NewX, dim.NewY))
                {
                    count++;
                }
            }
            return count;
        }

        /// <summary>
        /// 点是否在标题栏内
        /// </summary>
        private bool PointInTitlebar(double x, double y)
        {
            return x >= TITLEBAR_BOX[0] && x <= TITLEBAR_BOX[2] &&
                   y >= TITLEBAR_BOX[1] && y <= TITLEBAR_BOX[3];
        }

        /// <summary>
        /// JSON 转义
        /// </summary>
        private string EscapeJson(string s)
        {
            if (string.IsNullOrEmpty(s)) return "";
            return s.Replace("\\", "\\\\").Replace("\"", "\\\"")
                    .Replace("\n", "\\n").Replace("\r", "\\r").Replace("\t", "\\t");
        }

        /// <summary>
        /// 尺寸信息内部类
        /// </summary>
        private class DimInfo
        {
            public int Index;
            public string ViewName;
            public string Text = "";
            public double TextX, TextY;
            public double OrigX, OrigY;
            public double NewX, NewY;
            public int Track;
            public bool Adjusted;
        }
    }
}
