Attribute VB_Name = "auto_annotate"
Option Explicit

' v1.6 Task 2: VBA sidecar 用于尺寸标注
' 用早期绑定调用 IDrawingDoc.InsertModelAnnotations3，避免 pywin32 COM 方法分发问题
' 调用方式：sw.RunMacro2(macro_path, "auto_annotate", "main", 1, 0)

Public Sub main()
    Dim swApp As Object
    Dim swModel As Object
    Dim swDrawing As Object
    Dim swExt As Object
    Dim vAnnotations As Variant
    Dim errCode As Long

    On Error GoTo ErrHandler

    Set swApp = Application.SldWorks
    Set swModel = swApp.ActiveDoc

    If swModel Is Nothing Then
        Call WriteResult("error", "No active document")
        Exit Sub
    End If

    If swModel.GetType <> 3 Then  ' swDocDRAWING = 3
        Call WriteResult("error", "Active document is not a drawing")
        Exit Sub
    End If

    Set swDrawing = swModel
    Set swExt = swModel.Extension

    ' InsertModelAnnotations3(Type, Options, AllViews, Process, IncludeChildren, IncludeFeatures, FeatTolType)
    ' Type=0 (swDrawingComponent), Options=32 (swImportDimensionsAll)
    ' AllViews=True, Process=True, IncludeChildren=False, IncludeFeatures=False
    ' FeatTolType=0 (swFeatureTolType_None)
    vAnnotations = swDrawing.InsertModelAnnotations3(0, 32, True, True, False, False, 0)

    If IsEmpty(vAnnotations) Then
        Call WriteResult("success_zero", "InsertModelAnnotations3 returned empty")
    Else
        Dim count As Long
        count = UBound(vAnnotations) - LBound(vAnnotations) + 1
        Call WriteResult("success", "Inserted " & count & " annotations")
    End If

    ' 强制重建
    swModel.ForceRebuild3 (False)

    Exit Sub

ErrHandler:
    Call WriteResult("error", "Err " & Err.Number & ": " & Err.Description)
End Sub

Private Sub WriteResult(status As String, msg As String)
    ' 写结果到 annotate_result.json（简化格式，由 Python 读取）
    Dim fso As Object
    Dim f As Object
    Dim jsonPath As String

    Set fso = CreateObject("Scripting.FileSystemObject")
    jsonPath = Environ("ANNOTATE_RESULT_PATH")
    If jsonPath = "" Then
        jsonPath = "C:\Users\Vision\Desktop\SW 相关\drw_output\v5\annotate_result.json"
    End If

    Set f = fso.CreateTextFile(jsonPath, True)
    f.WriteLine "{""status"": """ & status & """, ""msg"": """ & Replace(msg, """", "\""") & """}"
    f.Close
End Sub
