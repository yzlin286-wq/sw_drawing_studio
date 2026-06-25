using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;

namespace SwReferenceMetricsSidecar
{
    internal class Program
    {
        private const string SwProgId = "SldWorks.Application";

        static int Main(string[] args)
        {
            var opts = ParseArgs(args);
            string drawingPath = GetArg(opts, "--drawing", "");
            string outPath = GetArg(opts, "--out", "");

            var result = NewResult(drawingPath);
            try
            {
                if (string.IsNullOrEmpty(drawingPath) || !File.Exists(drawingPath))
                {
                    result["status"] = "error";
                    result["reason"] = "drawing_not_found";
                    WriteJson(outPath, result);
                    return 2;
                }

                drawingPath = Path.GetFullPath(drawingPath);
                result["path"] = drawingPath;
                result["file_size_bytes"] = new FileInfo(drawingPath).Length;

                dynamic swApp = ConnectSolidWorks(result);
                if (swApp == null)
                {
                    result["status"] = "error";
                    result["reason"] = "solidworks_not_available";
                    WriteJson(outPath, result);
                    return 3;
                }

                dynamic doc = OpenDrawing(swApp, drawingPath, result);
                if (doc == null)
                {
                    result["status"] = "error";
                    if (string.IsNullOrEmpty(Convert.ToString(result["reason"])))
                    {
                        result["reason"] = "open_drawing_failed";
                    }
                    WriteJson(outPath, result);
                    return 4;
                }

                try
                {
                    ExtractMetrics(doc, result);
                    result["success"] = true;
                    result["status"] = "ok";
                    result["reason"] = "";
                }
                finally
                {
                    try
                    {
                        string title = Convert.ToString(CallOrGet(doc, "GetTitle"));
                        if (!string.IsNullOrEmpty(title))
                        {
                            swApp.CloseDoc(title);
                        }
                    }
                    catch { }
                }
            }
            catch (Exception ex)
            {
                result["status"] = "exception";
                result["reason"] = ex.Message;
                result["success"] = false;
            }

            WriteJson(outPath, result);
            return (bool)result["success"] ? 0 : 1;
        }

        private static Dictionary<string, object> NewResult(string drawingPath)
        {
            return new Dictionary<string, object>
            {
                { "schema", "sw_drawing_studio.reference_metrics.v1" },
                { "source", "csharp_sidecar" },
                { "generated_at", DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") },
                { "path", drawingPath },
                { "exists", File.Exists(drawingPath) },
                { "success", false },
                { "status", "init" },
                { "reason", "" },
                { "connection_method", "" },
                { "sw_revision", "" },
                { "open_errors", null },
                { "open_warnings", null },
                { "sheet", new Dictionary<string, object>() },
                { "view_count", 0 },
                { "view_types", new Dictionary<string, object>() },
                { "view_names", new List<object>() },
                { "view_outlines", new List<object>() },
                { "display_dim_count", 0 },
                { "annotation_count", 0 },
                { "file_size_bytes", File.Exists(drawingPath) ? new FileInfo(drawingPath).Length : 0 },
                { "warnings", new List<object>() },
            };
        }

        private static dynamic ConnectSolidWorks(Dictionary<string, object> result)
        {
            try
            {
                object active = Marshal.GetActiveObject(SwProgId);
                if (active != null)
                {
                    result["connection_method"] = "get_active_object";
                    dynamic sw = active;
                    try { result["sw_revision"] = Convert.ToString(CallOrGet(active, "RevisionNumber")); } catch { }
                    return sw;
                }
            }
            catch { }

            try
            {
                Type swType = Type.GetTypeFromProgID(SwProgId);
                if (swType == null) return null;
                object created = Activator.CreateInstance(swType);
                if (created == null) return null;
                result["connection_method"] = "dispatch";
                dynamic sw = created;
                try { result["sw_revision"] = Convert.ToString(CallOrGet(created, "RevisionNumber")); } catch { }
                return sw;
            }
            catch
            {
                return null;
            }
        }

        private static dynamic OpenDrawing(dynamic swApp, string drawingPath, Dictionary<string, object> result)
        {
            dynamic doc = null;
            try
            {
                doc = swApp.GetOpenDocumentByName(drawingPath);
                if (doc != null)
                {
                    result["open_errors"] = 0;
                    result["open_warnings"] = 0;
                    return doc;
                }
            }
            catch { }

            try
            {
                object[] args = new object[] { drawingPath, 3, 3, "", 0, 0 };
                bool[] refs = new bool[] { false, false, false, false, true, true };
                // swDocDRAWING=3, swOpenDocOptions_Silent=1 + swOpenDocOptions_ReadOnly=2.
                doc = ComInvoke(swApp, "OpenDoc6", args, refs);
                result["open_errors"] = args[4];
                result["open_warnings"] = args[5];
                if (doc != null) return doc;
                result["reason"] = "OpenDoc6 returned null";
            }
            catch (Exception ex)
            {
                result["reason"] = "OpenDoc6 exception: " + ex.Message;
            }

            try
            {
                object[] args = new object[] { drawingPath, true, 0, 0 };
                bool[] refs = new bool[] { false, false, false, true };
                doc = ComInvoke(swApp, "ActivateDoc3", args, refs);
                if (doc != null)
                {
                    result["open_errors"] = args[3];
                    if (result["open_warnings"] == null) result["open_warnings"] = 0;
                }
                return doc;
            }
            catch (Exception ex)
            {
                result["reason"] = "ActivateDoc3 exception: " + ex.Message;
                return null;
            }
        }

        private static void ExtractMetrics(dynamic doc, Dictionary<string, object> result)
        {
            var warnings = (List<object>)result["warnings"];
            dynamic sheet = null;
            try
            {
                sheet = CallOrGet(doc, "GetCurrentSheet");
                if (sheet != null)
                {
                    var sheetData = new Dictionary<string, object>();
                    sheetData["name"] = Convert.ToString(CallOrGet(sheet, "Name"));
                    object size = CallOrGet(sheet, "GetSize");
                    sheetData["paper_size"] = ToSimpleList(size);
                    object props = CallOrGet(sheet, "GetProperties2");
                    sheetData["properties"] = ToSimpleList(props);
                    result["sheet"] = sheetData;
                }
            }
            catch (Exception ex)
            {
                warnings.Add("sheet_metrics_failed:" + ex.Message);
            }

            List<object> views = CollectViews(doc, sheet, warnings);
            var uniqueKeys = new HashSet<string>();
            var viewNames = new List<object>();
            var viewOutlines = new List<object>();
            var viewTypes = new Dictionary<string, object>();
            int displayDimCount = 0;

            foreach (object view in views)
            {
                string name = Convert.ToString(CallOrGet(view, "Name"));
                string type = Convert.ToString(CallOrGet(view, "Type"));
                List<object> outline = ToSimpleList(CallOrGet(view, "GetOutline"));
                if (outline.Count == 0)
                {
                    outline = ToSimpleList(CallOrGet(view, "Outline"));
                }
                if (outline.Count == 0 && string.IsNullOrEmpty(type))
                {
                    continue;
                }
                string key = name + "|" + type + "|" + FormatJsonValue(outline);
                if (uniqueKeys.Contains(key)) continue;
                uniqueKeys.Add(key);

                viewNames.Add(name);
                if (!viewTypes.ContainsKey(type)) viewTypes[type] = 0;
                viewTypes[type] = Convert.ToInt32(viewTypes[type]) + 1;
                displayDimCount += CountDisplayDimensions(view);
                if (outline.Count > 0)
                {
                    viewOutlines.Add(new Dictionary<string, object>
                    {
                        { "name", name },
                        { "type", type },
                        { "outline", outline },
                    });
                }
            }

            result["view_count"] = viewNames.Count;
            result["view_names"] = viewNames;
            result["view_types"] = viewTypes;
            result["view_outlines"] = viewOutlines;
            result["display_dim_count"] = displayDimCount;
            result["annotation_count"] = CountArray(CallOrGet(doc, "GetAnnotations"));
        }

        private static List<object> CollectViews(dynamic doc, dynamic sheet, List<object> warnings)
        {
            var views = new List<object>();
            try
            {
                object sheetViews = sheet != null ? CallOrGet(sheet, "GetViews") : null;
                AddRange(views, sheetViews);
                if (views.Count > 0) return views;
            }
            catch (Exception ex)
            {
                warnings.Add("sheet_getviews_failed:" + ex.Message);
            }

            try
            {
                object modelViews = CallOrGet(doc, "GetViews");
                foreach (object sheetView in ToObjectList(modelViews))
                {
                    AppendViewChain(views, sheetView, true);
                }
                if (views.Count > 0) return views;
            }
            catch (Exception ex)
            {
                warnings.Add("doc_getviews_failed:" + ex.Message);
            }

            try
            {
                object firstView = CallOrGet(doc, "GetFirstView");
                AppendViewChain(views, firstView, true);
                if (views.Count > 0) return views;
            }
            catch (Exception ex)
            {
                warnings.Add("doc_getfirstview_failed:" + ex.Message);
            }

            return views;
        }

        private static void AppendViewChain(List<object> views, object start, bool includeStart)
        {
            object view = includeStart ? start : CallOrGet(start, "GetNextView");
            int seen = 0;
            while (view != null && seen < 1000)
            {
                views.Add(view);
                seen++;
                view = CallOrGet(view, "GetNextView");
            }
        }

        private static int CountDisplayDimensions(object view)
        {
            int count = CountArray(CallOrGet(view, "GetDisplayDimensions"));
            if (count > 0) return count;
            try
            {
                object dim = CallOrGet(view, "GetFirstDisplayDimension");
                int seen = 0;
                while (dim != null && seen < 10000)
                {
                    count++;
                    seen++;
                    dim = CallOrGet(view, "GetNextDisplayDimension", dim);
                }
            }
            catch { }
            return count;
        }

        private static object CallOrGet(object obj, string name, params object[] args)
        {
            if (obj == null) return null;
            try
            {
                BindingFlags flags = args != null && args.Length > 0
                    ? BindingFlags.InvokeMethod
                    : BindingFlags.InvokeMethod;
                return obj.GetType().InvokeMember(name, flags, null, obj, args ?? new object[0]);
            }
            catch { }
            try
            {
                return obj.GetType().InvokeMember(name, BindingFlags.GetProperty, null, obj, null);
            }
            catch { }
            try
            {
                return obj.GetType().InvokeMember(name, BindingFlags.GetField, null, obj, null);
            }
            catch { }
            return null;
        }

        private static object ComInvoke(object obj, string methodName, object[] args, bool[] refFlags)
        {
            if (obj == null) return null;
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

        private static void AddRange(List<object> target, object value)
        {
            foreach (object item in ToObjectList(value))
            {
                target.Add(item);
            }
        }

        private static List<object> ToObjectList(object value)
        {
            var list = new List<object>();
            if (value == null) return list;
            if (value is string)
            {
                list.Add(value);
                return list;
            }
            if (value is Array)
            {
                Array arr = (Array)value;
                foreach (object item in arr) list.Add(item);
                return list;
            }
            if (value is IEnumerable)
            {
                IEnumerable enumerable = (IEnumerable)value;
                foreach (object item in enumerable) list.Add(item);
                return list;
            }
            list.Add(value);
            return list;
        }

        private static List<object> ToSimpleList(object value)
        {
            var raw = ToObjectList(value);
            var simple = new List<object>();
            foreach (object item in raw)
            {
                simple.Add(ToSimpleValue(item));
            }
            return simple;
        }

        private static object ToSimpleValue(object value)
        {
            if (value == null) return null;
            if (value is bool || value is int || value is long || value is double || value is float || value is decimal || value is string)
            {
                return value;
            }
            try
            {
                return Convert.ToDouble(value, CultureInfo.InvariantCulture);
            }
            catch { }
            return Convert.ToString(value);
        }

        private static int CountArray(object value)
        {
            if (value == null) return 0;
            if (value is Array) return ((Array)value).Length;
            if (value is ICollection) return ((ICollection)value).Count;
            if (value is IEnumerable)
            {
                IEnumerable enumerable = (IEnumerable)value;
                int count = 0;
                foreach (object _ in enumerable) count++;
                return count;
            }
            return 0;
        }

        private static Dictionary<string, string> ParseArgs(string[] args)
        {
            var d = new Dictionary<string, string>();
            for (int i = 0; i < args.Length - 1; i++)
            {
                if (args[i].StartsWith("--"))
                {
                    d[args[i]] = args[i + 1];
                }
            }
            return d;
        }

        private static string GetArg(Dictionary<string, string> args, string key, string fallback)
        {
            string value;
            return args.TryGetValue(key, out value) ? value : fallback;
        }

        private static void WriteJson(string outPath, Dictionary<string, object> payload)
        {
            if (string.IsNullOrEmpty(outPath))
            {
                outPath = Path.Combine(Environment.CurrentDirectory, "reference_metrics_sidecar.json");
            }
            string dir = Path.GetDirectoryName(outPath);
            if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
            File.WriteAllText(outPath, FormatJsonValue(payload), Encoding.UTF8);
            Console.WriteLine(FormatJsonValue(new Dictionary<string, object>
            {
                { "success", payload["success"] },
                { "status", payload["status"] },
                { "out", outPath },
                { "view_count", payload["view_count"] },
                { "display_dim_count", payload["display_dim_count"] },
            }));
        }

        private static string FormatJsonValue(object val)
        {
            if (val == null) return "null";
            if (val is bool) return ((bool)val) ? "true" : "false";
            if (val is int || val is long) return Convert.ToString(val, CultureInfo.InvariantCulture);
            if (val is double || val is float || val is decimal)
            {
                return Convert.ToDouble(val, CultureInfo.InvariantCulture).ToString("R", CultureInfo.InvariantCulture);
            }
            if (val is string) return "\"" + EscapeJson((string)val) + "\"";
            if (val is Dictionary<string, object>)
            {
                Dictionary<string, object> dict = (Dictionary<string, object>)val;
                var sb = new StringBuilder();
                sb.Append("{");
                bool first = true;
                foreach (var kv in dict)
                {
                    if (!first) sb.Append(",");
                    first = false;
                    sb.Append("\"").Append(EscapeJson(kv.Key)).Append("\":").Append(FormatJsonValue(kv.Value));
                }
                sb.Append("}");
                return sb.ToString();
            }
            if (val is IDictionary)
            {
                IDictionary nonGenericDict = (IDictionary)val;
                var sb = new StringBuilder();
                sb.Append("{");
                bool first = true;
                foreach (DictionaryEntry entry in nonGenericDict)
                {
                    if (!first) sb.Append(",");
                    first = false;
                    sb.Append("\"").Append(EscapeJson(Convert.ToString(entry.Key))).Append("\":").Append(FormatJsonValue(entry.Value));
                }
                sb.Append("}");
                return sb.ToString();
            }
            if (val is IEnumerable && !(val is string))
            {
                IEnumerable enumerable = (IEnumerable)val;
                var sb = new StringBuilder();
                sb.Append("[");
                bool first = true;
                foreach (object item in enumerable)
                {
                    if (!first) sb.Append(",");
                    first = false;
                    sb.Append(FormatJsonValue(item));
                }
                sb.Append("]");
                return sb.ToString();
            }
            return "\"" + EscapeJson(Convert.ToString(val)) + "\"";
        }

        private static string EscapeJson(string s)
        {
            if (string.IsNullOrEmpty(s)) return "";
            return s.Replace("\\", "\\\\")
                .Replace("\"", "\\\"")
                .Replace("\r", "\\r")
                .Replace("\n", "\\n")
                .Replace("\t", "\\t");
        }
    }
}
