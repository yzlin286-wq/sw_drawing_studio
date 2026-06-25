using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;

namespace SwDrawingStudioAddin
{
    /// <summary>
    /// v2.1 Task 3: PMI Seed Engine
    ///
    /// 原则: 不修改原始 SLDPRT，只允许修改 run_dir/input_work 副本
    ///
    /// 流程:
    ///   1. 复制原始 part 到 run_dir/input_work/<base>_seed.SLDPRT
    ///   2. 打开副本
    ///   3. 获取零件 BoundingBox (overall_length / width / height)
    ///   4. 在副本中通过 Extension.InsertDimension3 添加 3D 标注尺寸
    ///      (或通过 Annotation API 添加 PMI)
    ///   5. 保存副本
    ///   6. 返回副本路径 + 尺寸信息
    ///
    /// 后续 GenerateDimensionsV3 策略 4 会调用 InsertModelAnnotations
    /// 将副本中的 PMI 导入到 drawing
    /// </summary>
    public class PmiSeedEngine
    {
        private object _swApp;

        public PmiSeedEngine(object swApp)
        {
            _swApp = swApp;
        }

        /// <summary>
        /// 在 part 副本中创建 PMI Seed
        /// </summary>
        public Dictionary<string, object> SeedPart(
            string originalPartPath,
            string runId,
            string runDir)
        {
            var result = new Dictionary<string, object>();
            result["engine_version"] = "v3.2";
            result["timestamp"] = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
            result["original_part_path"] = originalPartPath;

            try
            {
                // v3.2 策略变更：使用 SaveAs3 创建副本（生成新内部 ID）
                // File.Copy 会复制内部 ID，导致 OpenDoc6 error 65536
                //
                // 流程:
                //   1. 打开原始 part
                //   2. 在内存中创建草图尺寸（不保存原始）
                //   3. SaveAs3 到副本路径（生成新内部 ID）
                //   4. 关闭副本
                //   5. 重新打开副本（此时有新 ID，不会冲突）
                //   6. 验证尺寸存在

                // 1. 打开原始 part
                dynamic partDoc = OpenDoc(originalPartPath, 1, 1, result);
                if (partDoc == null)
                {
                    result["success"] = false;
                    result["reason"] = "OpenDoc6 原始 part 返回 null";
                    return result;
                }
                result["original_opened"] = true;

                // 2. 获取 BoundingBox
                var bbox = GetBoundingBox(partDoc);
                result["bbox"] = bbox;

                double length = bbox["max_x"] - bbox["min_x"];
                double width = bbox["max_y"] - bbox["min_y"];
                double height = bbox["max_z"] - bbox["min_z"];
                result["overall_length"] = Math.Round(length * 1000, 2);
                result["overall_width"] = Math.Round(width * 1000, 2);
                result["overall_height"] = Math.Round(height * 1000, 2);

                // 3. 在内存中创建 PMI / 3D 尺寸（不保存原始 part）
                int seedDimCount = 0;
                var seedDetails = new List<object>();

                // 策略 A: 通过 Extension.InsertDimension3 添加 3D 尺寸
                int dimA = TryInsertDimension3(partDoc, bbox);
                if (dimA > 0)
                {
                    seedDimCount += dimA;
                    seedDetails.Add(new Dictionary<string, object> {
                        {"strategy", "insert_dimension3"}, {"count", dimA}
                    });
                }

                // 策略 B: 通过 Annotation API 添加 PMI 文本
                int dimB = TryAddAnnotationDimensions(partDoc, bbox);
                if (dimB > 0)
                {
                    seedDimCount += dimB;
                    seedDetails.Add(new Dictionary<string, object> {
                        {"strategy", "annotation_pmi"}, {"count", dimB}
                    });
                }

                // 策略 C: 通过 FeatureManager 在草图添加驱动尺寸
                int dimC = TryAddSketchDrivingDimension(partDoc, bbox);
                if (dimC > 0)
                {
                    seedDimCount += dimC;
                    seedDetails.Add(new Dictionary<string, object> {
                        {"strategy", "sketch_driving_dim"}, {"count", dimC}
                    });
                }

                // 策略 D: v2.1 新增 - 创建新草图 + 画线 + AddDimension5
                int dimD = TryCreateSketchWithDimension(partDoc, bbox, result);
                if (dimD > 0)
                {
                    seedDimCount += dimD;
                    seedDetails.Add(new Dictionary<string, object> {
                        {"strategy", "create_sketch_dim"}, {"count", dimD}
                    });
                }

                result["seed_dim_count_before_saveas"] = seedDimCount;
                result["seed_details"] = seedDetails;

                // 4. SaveAs3 到副本路径（生成新内部 ID）
                string seedPath = GetSeedPath(originalPartPath, runId, runDir);
                result["seed_part_path"] = seedPath;

                bool saved = false;
                try
                {
                    // SaveAs3(Name, Version, Options, Errors, Warnings)
                    // swSaveAsCurrentVersion = 0, swSaveAsOptions_Silent = 1
                    object[] saveArgs = new object[] { seedPath, 0, 1, 0, 0 };
                    bool[] saveRefs = new bool[] { false, false, false, true, true };
                    object saveRet = ComInvoke(partDoc, "SaveAs3", saveArgs, saveRefs);
                    saved = saveRet != null && (bool)saveRet;
                    int saveErrors = Convert.ToInt32(saveArgs[3]);
                    int saveWarnings = Convert.ToInt32(saveArgs[4]);
                    result["saveas3_errors"] = saveErrors;
                    result["saveas3_warnings"] = saveWarnings;
                }
                catch (Exception ex)
                {
                    result["saveas3_error"] = ex.Message;
                    // fallback: SaveAs4
                    try
                    {
                        object[] saveArgs = new object[] { seedPath, 0, 1, 0, 0 };
                        bool[] saveRefs = new bool[] { false, false, false, true, true };
                        object saveRet = ComInvoke(partDoc, "SaveAs4", saveArgs, saveRefs);
                        saved = saveRet != null && (bool)saveRet;
                    }
                    catch (Exception ex2)
                    {
                        result["saveas4_error"] = ex2.Message;
                    }
                }
                result["saved"] = saved;

                // 5. 关闭文档（不保存原始 part 的修改）
                try
                {
                    // CloseDoc 关闭当前文档（已 SaveAs3 为副本，所以关闭的是副本）
                    ComCall(_swApp, "CloseDoc", seedPath);
                    result["doc_closed"] = true;
                }
                catch (Exception ex)
                {
                    result["close_error"] = ex.Message;
                }

                // 6. 重新打开副本（此时有新内部 ID，不会冲突）
                dynamic seedDoc = null;
                if (saved)
                {
                    seedDoc = OpenDoc(seedPath, 1, 1, result);
                    result["seed_reopened"] = seedDoc != null;
                }

                result["seed_dim_count"] = seedDimCount;
                result["success"] = seedDimCount > 0 && saved;
                result["reason"] = seedDimCount > 0
                    ? (saved ? "PMI Seed 成功创建 " + seedDimCount + " 个尺寸并 SaveAs3 到副本" : "PMI Seed 创建了尺寸但 SaveAs3 失败")
                    : "PMI Seed 未创建尺寸（SW2025 API 限制：InsertDimension3/Annotation 需要选中几何）";
            }
            catch (Exception ex)
            {
                result["success"] = false;
                result["reason"] = "PmiSeedEngine 异常: " + ex.Message;
            }

            return result;
        }

        /// <summary>
        /// v3.2: 获取 seed part 路径（使用 C:\Temp\SwAddin\seed_parts\ 避免中文路径）
        /// </summary>
        private string GetSeedPath(string originalPartPath, string runId, string runDir)
        {
            string baseName = Path.GetFileNameWithoutExtension(originalPartPath);
            // 使用 runId 作为后缀确保唯一性
            string seedName = baseName + "_seed_" + runId + ".SLDPRT";

            // 优先使用无中文路径
            string tempDir = @"C:\Temp\SwAddin\seed_parts";
            Directory.CreateDirectory(tempDir);
            string tempSeedPath = Path.Combine(tempDir, seedName);
            return tempSeedPath;
        }

        /// <summary>
        /// 复制 part 到 input_work
        /// v2.1: 同时复制到 C:\Temp\SwAddin\seed_parts\ 作为 fallback（避免中文路径）
        /// </summary>
        private string CopyPartToInputWork(string originalPartPath, string runId, string runDir)
        {
            try
            {
                if (string.IsNullOrEmpty(runDir))
                {
                    runDir = Path.GetDirectoryName(originalPartPath);
                }

                // 主路径: run_dir/input_work
                string inputWorkDir = Path.Combine(runDir, "input_work");
                Directory.CreateDirectory(inputWorkDir);

                string baseName = Path.GetFileNameWithoutExtension(originalPartPath);
                string seedName = baseName + "_seed.SLDPRT";
                string seedPath = Path.Combine(inputWorkDir, seedName);

                File.Copy(originalPartPath, seedPath, true);

                // Fallback 路径: C:\Temp\SwAddin\seed_parts\ (无中文字符)
                string tempDir = @"C:\Temp\SwAddin\seed_parts";
                Directory.CreateDirectory(tempDir);
                string tempSeedPath = Path.Combine(tempDir, seedName);
                try
                {
                    File.Copy(originalPartPath, tempSeedPath, true);
                    // 返回 temp 路径作为主路径（避免中文路径导致 OpenDoc6 失败）
                    return tempSeedPath;
                }
                catch { }

                return seedPath;
            }
            catch (Exception)
            {
                return "";
            }
        }

        /// <summary>
        /// 获取零件 BoundingBox
        /// </summary>
        private Dictionary<string, object> GetBoundingBox(dynamic partDoc)
        {
            var bbox = new Dictionary<string, object>();
            bbox["min_x"] = 0.0; bbox["min_y"] = 0.0; bbox["min_z"] = 0.0;
            bbox["max_x"] = 0.0; bbox["max_y"] = 0.0; bbox["max_z"] = 0.0;

            try
            {
                // GetBoundingBox (axis=0, ...)
                object[] args = new object[] { 0, false };
                bool[] refs = new bool[] { false, false };
                object result = ComInvoke(partDoc, "GetBoundingBox", args, refs);
                if (result is Array)
                {
                    Array arr = (Array)result;
                    if (arr.Length >= 6)
                    {
                        bbox["min_x"] = Convert.ToDouble(arr.GetValue(0));
                        bbox["min_y"] = Convert.ToDouble(arr.GetValue(1));
                        bbox["min_z"] = Convert.ToDouble(arr.GetValue(2));
                        bbox["max_x"] = Convert.ToDouble(arr.GetValue(3));
                        bbox["max_y"] = Convert.ToDouble(arr.GetValue(4));
                        bbox["max_z"] = Convert.ToDouble(arr.GetValue(5));
                    }
                }
            }
            catch { }

            return bbox;
        }

        /// <summary>
        /// 策略 A: 通过 Extension.InsertDimension3 添加 3D 尺寸
        /// </summary>
        private int TryInsertDimension3(dynamic partDoc, Dictionary<string, object> bbox)
        {
            int created = 0;
            try
            {
                // Extension.InsertDimension3 需要:
                // X, Y, Z, DimensionType, Orientation, FlipArrow, TextHeight, ...
                // 但需要先选中几何，SW2025 下无法直接通过坐标选中模型边

                // 尝试通过 Extension.InsertDimension2
                dynamic extension = ComGet(partDoc, "Extension");
                if (extension == null) return 0;

                // InsertDimension2(X, Y, Z, DimensionType, Orientation)
                // DimensionType: 0=horizontal, 1=vertical, 2=linear
                try
                {
                    double cx = (Convert.ToDouble(bbox["min_x"]) + Convert.ToDouble(bbox["max_x"])) / 2.0;
                    double cy = (Convert.ToDouble(bbox["min_y"]) + Convert.ToDouble(bbox["max_y"])) / 2.0;
                    double cz = (Convert.ToDouble(bbox["min_z"]) + Convert.ToDouble(bbox["max_z"])) / 2.0;

                    // 尝试在模型空间添加尺寸（需要预选中几何）
                    // SW2025 限制：无预选中几何时 InsertDimension 返回 null
                    object dim = ComCall(extension, "InsertDimension2",
                        cx, cy + 0.05, cz, 0, 0);
                    if (dim != null) created++;
                }
                catch { }
            }
            catch { }
            return created;
        }

        /// <summary>
        /// 策略 B: 通过 Annotation API 添加 PMI 文本
        /// </summary>
        private int TryAddAnnotationDimensions(dynamic partDoc, Dictionary<string, object> bbox)
        {
            int created = 0;
            try
            {
                // InsertNote / AddAnnotation
                double length = Convert.ToDouble(bbox["max_x"]) - Convert.ToDouble(bbox["min_x"]);
                double width = Convert.ToDouble(bbox["max_y"]) - Convert.ToDouble(bbox["min_y"]);
                double height = Convert.ToDouble(bbox["max_z"]) - Convert.ToDouble(bbox["min_z"]);

                // 通过 InsertNote 添加 PMI 文本标注
                // Format: "L=<length>mm W=<width>mm H=<height>mm"
                string noteText = "L=" + Math.Round(length * 1000, 2) + "mm W=" + Math.Round(width * 1000, 2) + "mm H=" + Math.Round(height * 1000, 2) + "mm";

                try
                {
                    // InsertNote (Text) - 在模型中添加注释
                    object note = ComCall(partDoc, "InsertNote", noteText);
                    if (note != null) created++;
                }
                catch { }

                // 也尝试通过 Extension.AddAnnotation
                try
                {
                    dynamic extension = ComGet(partDoc, "Extension");
                    if (extension != null)
                    {
                        // 通过 Extension 添加 annotation
                        object ann = ComCall(extension, "AddAnnotation");
                        if (ann != null) created++;
                    }
                }
                catch { }
            }
            catch { }
            return created;
        }

        /// <summary>
        /// 策略 C: 通过草图添加驱动尺寸
        /// 在 Front 基准面上创建草图，添加长度尺寸
        /// </summary>
        private int TryAddSketchDrivingDimension(dynamic partDoc, Dictionary<string, object> bbox)
        {
            int created = 0;
            try
            {
                // 进入草图编辑模式（需要先选中基准面）
                // SW2025 限制：通过 COM 自动化选中基准面较复杂

                // 尝试通过 FeatureManager 获取已有草图
                dynamic firstFeat = ComCall(partDoc, "FirstFeature");
                while (firstFeat != null)
                {
                    try
                    {
                        int featType = 0;
                        try { featType = (int)ComGet(firstFeat, "GetType2"); } catch { }

                        // swFeatTypeSketch = 1
                        if (featType == 1)
                        {
                            // 进入草图编辑
                            try
                            {
                                ComCall(firstFeat, "Select2", false, 0);
                                ComCall(partDoc, "EditSketch");
                                break;
                            }
                            catch { }
                        }
                    }
                    catch { }

                    try { firstFeat = ComCall(firstFeat, "GetNextFeature"); }
                    catch { break; }
                }

                // 如果进入了草图，尝试添加驱动尺寸
                // 通过 AddDimension5 (X, Y, Z)
                try
                {
                    double cx = (Convert.ToDouble(bbox["min_x"]) + Convert.ToDouble(bbox["max_x"])) / 2.0;
                    double cy = (Convert.ToDouble(bbox["min_y"]) + Convert.ToDouble(bbox["max_y"])) / 2.0;

                    object dim = ComCall(partDoc, "AddDimension5", cx, cy + 0.02, 0, 0, 0, false);
                    if (dim != null) created++;
                }
                catch { }

                // 退出草图
                try { ComCall(partDoc, "EditSketch"); } catch { }
            }
            catch { }
            return created;
        }

        /// <summary>
        /// 策略 D: v2.1 新增 - 创建新草图 + 画线 + AddDimension5
        ///
        /// 流程:
        ///   1. 选中 Front/Top/Right 基准面
        ///   2. InsertSketch2 进入草图
        ///   3. SketchManager.CreateLine 画一条线
        ///   4. AddDimension5 添加驱动尺寸
        ///   5. InsertSketch2 退出草图
        /// </summary>
        private int TryCreateSketchWithDimension(dynamic partDoc, Dictionary<string, object> bbox, Dictionary<string, object> result)
        {
            int created = 0;
            var strategyLog = new List<object>();

            try
            {
                double length = Convert.ToDouble(bbox["max_x"]) - Convert.ToDouble(bbox["min_x"]);
                double width = Convert.ToDouble(bbox["max_y"]) - Convert.ToDouble(bbox["min_y"]);
                double height = Convert.ToDouble(bbox["max_z"]) - Convert.ToDouble(bbox["min_z"]);

                // 使用 BoundingBox 尺寸（单位：米，SW 内部单位）
                // 取一个合理的线段长度（避免 0）
                double lineLen = Math.Max(length, 0.01);
                if (lineLen < 0.001) lineLen = 0.05; // fallback 50mm

                dynamic ext = ComGet(partDoc, "Extension");
                if (ext == null)
                {
                    strategyLog.Add(new Dictionary<string, object> { {"step", "get_extension"}, {"error", "Extension 为 null"} });
                    result["strategy_d_log"] = strategyLog;
                    return 0;
                }

                // 尝试选中基准面（Front/Top/Right，中英文都试）
                string[] planeNames = { "Front Plane", "前视基准面", "Top Plane", "上视基准面", "Right Plane", "右视基准面" };
                string[] planeTypes = { "PLANE", "DATUMPLANE" };
                bool selOk = false;
                string selPlaneName = "";

                foreach (string planeName in planeNames)
                {
                    foreach (string planeType in planeTypes)
                    {
                        try
                        {
                            object selRet = ComCall(ext, "SelectByID2",
                                planeName, planeType, 0, 0, 0, false, 0, null, 0);
                            if (selRet != null && (bool)selRet)
                            {
                                selOk = true;
                                selPlaneName = planeName;
                                break;
                            }
                        }
                        catch { }
                    }
                    if (selOk) break;
                }

                // 如果按名称选中失败，尝试通过 FeatureManager 获取第一个基准面
                if (!selOk)
                {
                    try
                    {
                        dynamic feat = ComCall(partDoc, "FirstFeature");
                        while (feat != null)
                        {
                            try
                            {
                                int featType = 0;
                                try { featType = (int)ComGet(feat, "GetType2"); } catch { }
                                // swFeatTypeRefPlane = 35
                                if (featType == 35)
                                {
                                    object selRet = ComCall(feat, "Select2", false, 0);
                                    if (selRet != null && (bool)selRet)
                                    {
                                        selOk = true;
                                        selPlaneName = "feature_refplane";
                                        break;
                                    }
                                }
                            }
                            catch { }
                            try { feat = ComCall(feat, "GetNextFeature"); }
                            catch { break; }
                        }
                    }
                    catch { }
                }

                strategyLog.Add(new Dictionary<string, object> {
                    {"step", "select_plane"},
                    {"success", selOk},
                    {"plane_name", selPlaneName}
                });

                if (!selOk)
                {
                    result["strategy_d_log"] = strategyLog;
                    return 0;
                }

                // 进入草图
                try
                {
                    ComCall(partDoc, "InsertSketch2", true);
                    strategyLog.Add(new Dictionary<string, object> { {"step", "insert_sketch"}, {"success", true} });
                }
                catch (Exception ex)
                {
                    strategyLog.Add(new Dictionary<string, object> { {"step", "insert_sketch"}, {"error", ex.Message} });
                    result["strategy_d_log"] = strategyLog;
                    return 0;
                }

                // 获取 SketchManager
                dynamic sketchMgr = null;
                try { sketchMgr = ComGet(partDoc, "SketchManager"); } catch { }
                if (sketchMgr == null)
                {
                    strategyLog.Add(new Dictionary<string, object> { {"step", "get_sketch_manager"}, {"error", "SketchManager 为 null"} });
                    try { ComCall(partDoc, "InsertSketch2", true); } catch { } // 退出草图
                    result["strategy_d_log"] = strategyLog;
                    return 0;
                }

                // 画一条水平线（代表 overall length）
                object lineObj = null;
                try
                {
                    // CreateLine(startX, startY, startZ, endX, endY, endZ)
                    lineObj = ComCall(sketchMgr, "CreateLine", 0, 0, 0, lineLen, 0, 0);
                    strategyLog.Add(new Dictionary<string, object> {
                        {"step", "create_line"},
                        {"success", lineObj != null},
                        {"line_len_m", lineLen}
                    });
                }
                catch (Exception ex)
                {
                    strategyLog.Add(new Dictionary<string, object> { {"step", "create_line"}, {"error", ex.Message} });
                }

                if (lineObj == null)
                {
                    try { ComCall(partDoc, "InsertSketch2", true); } catch { } // 退出草图
                    result["strategy_d_log"] = strategyLog;
                    return 0;
                }

                // CreateLine 后线段应自动选中，尝试 AddDimension5
                // AddDimension5(X, Y, Z, DimensionType, Orientation, FlipArrow, TextHeight, ArrowSide, WitnessGap, ...)
                try
                {
                    // 清除选择后重新选中线段（确保选中）
                    try { ComCall(partDoc, "ClearSelection"); } catch { }

                    // 重新选中线段：通过 SketchManager 创建的线段可以用 SelectByID2 选中
                    // type="SKETCHSEGMENT"，坐标用线段中点
                    double midX = lineLen / 2.0;
                    try
                    {
                        object selRet = ComCall(ext, "SelectByID2",
                            "", "SKETCHSEGMENT", midX, 0, 0, false, 0, null, 0);
                        strategyLog.Add(new Dictionary<string, object> {
                            {"step", "select_line"},
                            {"method", "SelectByID2_SKETCHSEGMENT"},
                            {"success", selRet != null && (bool)selRet}
                        });
                    }
                    catch (Exception ex)
                    {
                        strategyLog.Add(new Dictionary<string, object> {
                            {"step", "select_line"},
                            {"method", "SelectByID2_SKETCHSEGMENT"},
                            {"error", ex.Message}
                        });
                    }

                    // 尝试 AddDimension5
                    object dim = ComCall(partDoc, "AddDimension5",
                        midX, 0.01, 0, 0, 0, false, 0.005, 0, 0);
                    if (dim != null)
                    {
                        created++;
                        strategyLog.Add(new Dictionary<string, object> {
                            {"step", "add_dimension5"},
                            {"success", true},
                            {"dim_type", "horizontal_length"}
                        });
                    }
                    else
                    {
                        strategyLog.Add(new Dictionary<string, object> {
                            {"step", "add_dimension5"},
                            {"success", false},
                            {"reason", "返回 null"}
                        });
                    }
                }
                catch (Exception ex)
                {
                    strategyLog.Add(new Dictionary<string, object> {
                        {"step", "add_dimension5"},
                        {"error", ex.Message}
                    });
                }

                // 退出草图
                try { ComCall(partDoc, "InsertSketch2", true); } catch { }
                strategyLog.Add(new Dictionary<string, object> { {"step", "exit_sketch"}, {"success", true} });

                result["strategy_d_log"] = strategyLog;
            }
            catch (Exception ex)
            {
                strategyLog.Add(new Dictionary<string, object> { {"step", "exception"}, {"error", ex.Message} });
                result["strategy_d_log"] = strategyLog;
            }
            return created;
        }

        #region COM helpers

        private dynamic OpenDoc(string path, int docType, int options, Dictionary<string, object> result = null)
        {
            try
            {
                // 先检查文档是否已打开
                try
                {
                    dynamic existingDoc = ComCall(_swApp, "GetOpenDocumentByName", path);
                    if (existingDoc != null)
                    {
                        if (result != null) result["open_method"] = "already_open";
                        return existingDoc;
                    }
                }
                catch { }

                // 尝试 OpenDoc6
                try
                {
                    object[] args = new object[] { path, docType, options, "", 0, 0 };
                    bool[] refs = new bool[] { false, false, false, false, true, true };
                    dynamic doc = ComInvoke(_swApp, "OpenDoc6", args, refs);
                    if (doc != null)
                    {
                        if (result != null) result["open_method"] = "opendoc6";
                        return doc;
                    }
                    // 读取 Errors 和 Warnings
                    int errors = args[4] != null ? Convert.ToInt32(args[4]) : -1;
                    int warnings = args[5] != null ? Convert.ToInt32(args[5]) : -1;
                    if (result != null)
                    {
                        result["opendoc6_error"] = "returned null";
                        result["opendoc6_errors_code"] = errors;
                        result["opendoc6_warnings_code"] = warnings;
                    }
                }
                catch (Exception ex)
                {
                    if (result != null) result["opendoc6_error"] = ex.Message;
                }

                // fallback: OpenDoc5
                try
                {
                    object[] args5 = new object[] { path, docType, options, "", 0 };
                    bool[] refs5 = new bool[] { false, false, false, false, true };
                    dynamic doc5 = ComInvoke(_swApp, "OpenDoc5", args5, refs5);
                    if (doc5 != null)
                    {
                        if (result != null) result["open_method"] = "opendoc5";
                        return doc5;
                    }
                    if (result != null) result["opendoc5_error"] = "returned null";
                }
                catch (Exception ex)
                {
                    if (result != null) result["opendoc5_error"] = ex.Message;
                }

                // fallback: OpenDoc (basic)
                try
                {
                    dynamic doc3 = ComCall(_swApp, "OpenDoc", path, docType, options);
                    if (doc3 != null)
                    {
                        if (result != null) result["open_method"] = "opendoc";
                        return doc3;
                    }
                }
                catch (Exception ex)
                {
                    if (result != null) result["opendoc_error"] = ex.Message;
                }
            }
            catch (Exception ex)
            {
                if (result != null) result["open_exception"] = ex.Message;
            }
            return null;
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

        #endregion
    }
}
