using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;

namespace SwDimensionSidecar
{
    /// <summary>
    /// v1.7 Task 3: C# 早期绑定 Dimension Sidecar
    ///
    /// 通过 SolidWorks 早期绑定 API 插入尺寸或标注：
    ///   - overall_length / overall_width / overall_height
    ///   - fastener_spec / spring_spec
    ///
    /// 输出 dimension_sidecar_result.json
    ///
    /// 用法:
    ///   SwDimensionSidecar.exe --drawing <path> --part <path> --run-dir <dir>
    ///                          --part-class <class> --out <json_path>
    /// </summary>
    internal class Program
    {
        private const string SW_PROGID = "SldWorks.Application";

        static int Main(string[] args)
        {
            var opts = ParseArgs(args);
            string drawingPath = GetArg(opts, "--drawing", "");
            string partPath = GetArg(opts, "--part", "");
            string runDir = GetArg(opts, "--run-dir", "");
            string partClass = GetArg(opts, "--part-class", "feature_part");
            string outPath = GetArg(opts, "--out", "");

            // 转为绝对路径（SolidWorks 需要绝对路径）
            try
            {
                if (!string.IsNullOrEmpty(drawingPath))
                    drawingPath = Path.GetFullPath(drawingPath);
                if (!string.IsNullOrEmpty(partPath))
                    partPath = Path.GetFullPath(partPath);
            }
            catch { }

            var result = new Dictionary<string, object>
            {
                { "version", "v1.7" },
                { "success", false },
                { "status", "init" },
                { "msg", "" },
                { "reason", "" },
                { "drawing_path", drawingPath },
                { "part_path", partPath },
                { "part_class", partClass },
                { "annotations_added", 0 },
                { "overall_length", (double?)null },
                { "overall_width", (double?)null },
                { "overall_height", (double?)null },
                { "fastener_spec", "" },
                { "spring_spec", "" },
                { "standard_annotation_present", false },
                { "dimension_count_before", 0 },
                { "dimension_count_after", 0 },
                { "fallback_mode", "csharp_dynamic" },
            };

            try
            {
                if (string.IsNullOrEmpty(drawingPath) || !File.Exists(drawingPath))
                {
                    result["status"] = "error";
                    result["reason"] = "drawing not found: " + drawingPath;
                    WriteResult(outPath, result);
                    return 2;
                }

                // 连接 SolidWorks（使用 dynamic 进行 COM 互操作，自动处理 ref 参数）
                Type swType = Type.GetTypeFromProgID(SW_PROGID);
                if (swType == null)
                {
                    result["status"] = "error";
                    result["reason"] = "SldWorks.Application ProgID not found";
                    WriteResult(outPath, result);
                    return 3;
                }

                object swAppObj = Marshal.GetActiveObject(SW_PROGID);
                if (swAppObj == null)
                {
                    result["status"] = "error";
                    result["reason"] = "SolidWorks not running (GetActiveObject failed)";
                    WriteResult(outPath, result);
                    return 4;
                }

                // 使用 dynamic 类型，让 C# 运行时自动处理 COM 调用
                dynamic swApp = swAppObj;
                result["status"] = "connected";

                // 激活工程图
                dynamic drwModel = null;
                try
                {
                    int errStatus = 0;
                    drwModel = swApp.ActivateDoc3(drawingPath, true, 0, ref errStatus);
                }
                catch { }
                if (drwModel == null)
                {
                    // 尝试 OpenDoc6
                    try
                    {
                        int errStatus = 0;
                        int warnStatus = 0;
                        drwModel = swApp.OpenDoc6(drawingPath, 3, 257, "", ref errStatus, ref warnStatus);
                    }
                    catch { }
                }
                if (drwModel == null)
                {
                    result["status"] = "error";
                    result["reason"] = "cannot activate/open drawing";
                    WriteResult(outPath, result);
                    return 5;
                }

                // 计数前尺寸数
                int dimBefore = CountDisplayDimensions(drwModel);
                result["dimension_count_before"] = dimBefore;

                int added = 0;
                bool standardAnno = false;

                // 根据零件类别执行不同策略
                switch (partClass)
                {
                    case "fastener":
                    case "spring":
                    case "purchased_part":
                        // 采购类：插入标准标注
                        added = InsertStandardAnnotations(drwModel, partPath, partClass, result, swApp);
                        standardAnno = added > 0;
                        result["standard_annotation_present"] = standardAnno;
                        break;

                    default:
                        // feature_part / imported_body / long_thin / tiny_part / sheet_like
                        // 尝试 InsertModelAnnotations3（dynamic 早期绑定）
                        added = TryInsertModelAnnotations3(drwModel);
                        if (added == 0)
                        {
                            // 降级：插入总长/总宽/总高参考标注
                            added = InsertOverallDimensions(drwModel, partPath, result, swApp);
                        }
                        break;
                }

                // ForceRebuild3
                try
                {
                    drwModel.ForceRebuild3(true);
                }
                catch { }

                // 计数后尺寸数
                int dimAfter = CountDisplayDimensions(drwModel);
                result["dimension_count_after"] = dimAfter;
                result["annotations_added"] = added;
                bool success = added > 0 || standardAnno;
                result["success"] = success;
                result["status"] = success ? "ok" : "no_annotation_added";
                if (!success)
                {
                    result["reason"] = "no annotations could be added";
                }
            }
            catch (Exception ex)
            {
                result["status"] = "exception";
                result["reason"] = ex.Message;
                result["success"] = false;
            }

            WriteResult(outPath, result);
            return (bool)result["success"] ? 0 : 1;
        }

        private static Dictionary<string, string> ParseArgs(string[] args)
        {
            var d = new Dictionary<string, string>();
            for (int i = 0; i < args.Length - 1; i++)
            {
                if (args[i].StartsWith("--"))
                    d[args[i]] = args[i + 1];
            }
            return d;
        }

        private static void WriteResult(string path, Dictionary<string, object> result)
        {
            try
            {
                if (string.IsNullOrEmpty(path))
                {
                    path = Path.Combine(
                        Environment.CurrentDirectory,
                        "dimension_sidecar_result.json");
                }
                string dir = Path.GetDirectoryName(path);
                if (!string.IsNullOrEmpty(dir))
                    Directory.CreateDirectory(dir);
                string json = ManualJsonSerialize(result, 0);
                File.WriteAllText(path, json, Encoding.UTF8);
                Console.WriteLine("[SwDimensionSidecar] result written to " + path);
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine("[SwDimensionSidecar] write result failed: " + ex.Message);
            }
        }

        private static string ManualJsonSerialize(Dictionary<string, object> dict, int indent)
        {
            var sb = new StringBuilder();
            string pad = new string(' ', (indent + 1) * 2);
            string closePad = new string(' ', indent * 2);
            sb.Append("{\n");
            int i = 0;
            foreach (var kv in dict)
            {
                if (i > 0) sb.Append(",\n");
                sb.Append(pad);
                sb.Append("\"").Append(EscapeJsonString(kv.Key)).Append("\": ");
                sb.Append(FormatJsonValue(kv.Value, indent + 1));
                i++;
            }
            sb.Append("\n").Append(closePad).Append("}");
            return sb.ToString();
        }

        private static string FormatJsonValue(object val, int indent)
        {
            if (val == null) return "null";
            if (val is bool) return (bool)val ? "true" : "false";
            if (val is int || val is long) return val.ToString();
            if (val is double)
            {
                double d = (double)val;
                if (double.IsNaN(d) || double.IsInfinity(d)) return "null";
                return d.ToString("F1", System.Globalization.CultureInfo.InvariantCulture);
            }
            if (val is double?)
            {
                double? dn = (double?)val;
                if (!dn.HasValue) return "null";
                return dn.Value.ToString("F1", System.Globalization.CultureInfo.InvariantCulture);
            }
            if (val is string) return "\"" + EscapeJsonString((string)val) + "\"";
            if (val is Dictionary<string, object>) return ManualJsonSerialize((Dictionary<string, object>)val, indent);
            if (val is object[])
            {
                object[] arr = (object[])val;
                var sb = new StringBuilder("[");
                for (int j = 0; j < arr.Length; j++)
                {
                    if (j > 0) sb.Append(", ");
                    sb.Append(FormatJsonValue(arr[j], indent));
                }
                sb.Append("]");
                return sb.ToString();
            }
            return "\"" + EscapeJsonString(val.ToString()) + "\"";
        }

        private static string EscapeJsonString(string s)
        {
            if (string.IsNullOrEmpty(s)) return "";
            return s.Replace("\\", "\\\\").Replace("\"", "\\\"")
                    .Replace("\n", "\\n").Replace("\r", "\\r").Replace("\t", "\\t");
        }

        private static string GetArg(Dictionary<string, string> opts, string key, string def)
        {
            string v;
            return opts.TryGetValue(key, out v) ? v : def;
        }

        // ========== COM 调用方法（使用 dynamic） ==========

        private static int CountDisplayDimensions(dynamic drwModel)
        {
            try
            {
                int count = 0;
                dynamic view = drwModel.GetFirstView();
                while (view != null)
                {
                    try
                    {
                        dynamic dispDim = view.GetFirstDisplayDimension();
                        while (dispDim != null)
                        {
                            count++;
                            dispDim = view.GetNextDisplayDimension(dispDim);
                        }
                    }
                    catch { }
                    try
                    {
                        view = view.GetNextView();
                    }
                    catch { break; }
                }
                return count;
            }
            catch { return 0; }
        }

        private static int TryInsertModelAnnotations3(dynamic drwModel)
        {
            try
            {
                // InsertModelAnnotations3(AllViews, DimensionTypes, ImportIntoDuplicateViews,
                //   IncludeDimXpertAnnotations, IncludeHiddenFeatures, TargetLayer, DimXpertAnnotView)
                // DimensionTypes: 1=尺寸, 2=注解, 4=参考尺寸 (OR 组合)
                // 使用 1 | 2 = 3
                object result = drwModel.InsertModelAnnotations3(true, 3, false, true, false, "", false);
                if (result == null) return 0;
                if (result is object[])
                {
                    object[] arr = (object[])result;
                    return arr.Length;
                }
                if (result is Array)
                {
                    Array a = (Array)result;
                    return a.Length;
                }
                return 1;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine("[SwDimensionSidecar] InsertModelAnnotations3 failed: " + ex.Message);
                return 0;
            }
        }

        private static int InsertOverallDimensions(dynamic drwModel, string partPath,
            Dictionary<string, object> result, dynamic swApp)
        {
            try
            {
                double[] bbox = GetPartBbox(partPath, swApp);
                if (bbox != null && bbox.Length >= 3)
                {
                    double length = bbox[0];
                    double width = bbox[1];
                    double height = bbox[2];
                    result["overall_length"] = length;
                    result["overall_width"] = width;
                    result["overall_height"] = height;

                    string noteText = string.Format("总长={0:F1}mm  总宽={1:F1}mm  总高={2:F1}mm", length, width, height);
                    int added = InsertNote(drwModel, noteText, 0.15, 0.05);
                    return added;
                }
            }
            catch (Exception ex)
            {
                result["reason"] = "InsertOverallDimensions failed: " + ex.Message;
            }
            return 0;
        }

        private static int InsertStandardAnnotations(dynamic drwModel, string partPath, string partClass,
            Dictionary<string, object> result, dynamic swApp)
        {
            try
            {
                string partName = Path.GetFileNameWithoutExtension(partPath);
                var notes = new List<string>();

                string spec = ParseSpec(partName, partClass);
                if (!string.IsNullOrEmpty(spec))
                {
                    notes.Add("规格: " + spec);
                    if (partClass == "fastener") result["fastener_spec"] = spec;
                    if (partClass == "spring") result["spring_spec"] = spec;
                }

                string stdNo = LookupStdNo(partName);
                if (!string.IsNullOrEmpty(stdNo))
                    notes.Add("标准号: " + stdNo);

                notes.Add("数量: 1");
                notes.Add("按外购件图纸");

                double[] bbox = GetPartBbox(partPath, swApp);
                if (bbox != null && bbox.Length >= 3)
                {
                    result["overall_length"] = bbox[0];
                    result["overall_width"] = bbox[1];
                    result["overall_height"] = bbox[2];
                    notes.Add(string.Format("外形参考: {0:F1}×{1:F1}×{2:F1}mm", bbox[0], bbox[1], bbox[2]));
                }

                int added = 0;
                double y = 0.05;
                foreach (var note in notes)
                {
                    added += InsertNote(drwModel, note, 0.15, y);
                    y += 0.015;
                }
                return added;
            }
            catch (Exception ex)
            {
                result["reason"] = "InsertStandardAnnotations failed: " + ex.Message;
                return 0;
            }
        }

        private static string ParseSpec(string partName, string partClass)
        {
            var match = Regex.Match(partName, @"M(\d+)x(\d+)", RegexOptions.IgnoreCase);
            if (match.Success)
                return "M" + match.Groups[1].Value + "x" + match.Groups[2].Value;
            if (partName.Contains("弹簧") || partClass == "spring")
                return "弹簧";
            if (partName.Contains("铜套"))
                return "铜套";
            if (partName.Contains("导柱"))
                return "导柱";
            return "";
        }

        private static string LookupStdNo(string partName)
        {
            if (partName.Contains("螺丝") || partName.Contains("螺钉") || partName.Contains("螺栓"))
            {
                if (partName.Contains("十字")) return "GB/T 818";
                if (partName.Contains("内六角")) return "GB/T 70.1";
                return "GB/T 5783";
            }
            if (partName.Contains("弹簧")) return "GB/T 2089";
            if (partName.Contains("铜套")) return "GB/T 10446";
            if (partName.Contains("导柱")) return "GB/T 2861.1";
            return "";
        }

        private static int InsertNote(dynamic drwModel, string text, double x, double y)
        {
            try
            {
                // InsertNote(text, x, y) — 通过 DrawingDoc.InsertNote
                object note = drwModel.InsertNote(text, x, y);
                return note != null ? 1 : 0;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine("[SwDimensionSidecar] InsertNote failed: " + ex.Message);
                return 0;
            }
        }

        private static double[] GetPartBbox(string partPath, dynamic swApp)
        {
            try
            {
                // 尝试激活已打开的 part
                dynamic partModel = null;
                try
                {
                    int errStatus = 0;
                    partModel = swApp.ActivateDoc3(partPath, true, 0, ref errStatus);
                }
                catch { }
                if (partModel == null)
                {
                    try
                    {
                        int errStatus = 0;
                        int warnStatus = 0;
                        partModel = swApp.OpenDoc6(partPath, 1, 257, "", ref errStatus, ref warnStatus);
                    }
                    catch { }
                }
                if (partModel == null) return null;

                // GetPartBox(True) 返回 [xmin,ymin,zmin,xmax,ymax,zmax]（米）
                object box = partModel.GetPartBox(true);
                if (box is double[] && ((double[])box).Length >= 6)
                {
                    double[] arr = (double[])box;
                    double dx = Math.Abs(arr[3] - arr[0]) * 1000.0;
                    double dy = Math.Abs(arr[4] - arr[1]) * 1000.0;
                    double dz = Math.Abs(arr[5] - arr[2]) * 1000.0;
                    var dims = new List<double> { dx, dy, dz };
                    dims.Sort((a, b) => b.CompareTo(a));
                    return dims.ToArray();
                }

                // 重新激活工程图
                try
                {
                    string drwTitle = "";
                    // 不需要重新激活，调用方会处理
                }
                catch { }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine("[SwDimensionSidecar] GetPartBbox failed: " + ex.Message);
            }
            return null;
        }
    }
}
