' SolidWorks VBA 宏：自动剖视图
' 当 v5 原生 CreateSectionViewAt5 失败时调用
Dim swApp As Object
Dim swModel As Object
Dim swDraw As Object
Dim swView As Object
Dim swSheet As Object

Sub main()
    Set swApp = Application.SldWorks
    Set swModel = swApp.ActiveDoc
    If swModel Is Nothing Then
        Debug.Print "[auto_section] no active doc"
        Exit Sub
    End If
    Set swDraw = swModel
    Set swSheet = swDraw.GetCurrentSheet()
    
    ' 找前视图
    Set swView = swDraw.GetFirstView()
    Dim front As Object
    Set front = Nothing
    Do While Not swView Is Nothing
        If InStr(swView.Name, "前视") > 0 Or InStr(swView.Name, "Front") > 0 Then
            Set front = swView
            Exit Do
        End If
        Set swView = swView.GetNextView
    Loop
    If front Is Nothing Then
        ' 用第一个非 sheet 视图
        Set swView = swDraw.GetFirstView()
        Set swView = swView.GetNextView ' 跳过 sheet
        If Not swView Is Nothing Then Set front = swView
    End If
    If front Is Nothing Then
        Debug.Print "[auto_section] no front view"
        Exit Sub
    End If
    
    ' 取视图中心
    Dim outline As Variant
    outline = front.GetOutline
    Dim cx As Double, cy As Double
    cx = (outline(0) + outline(2)) / 2#
    cy = (outline(1) + outline(3)) / 2#
    
    ' 在 sheet sketch 画水平线作为切割线
    swDraw.EditSheet
    swDraw.SetEditMode 0
    swModel.SketchManager.InsertSketch True
    swModel.SketchManager.CreateLine outline(0) - 0.005, cy, 0, outline(2) + 0.005, cy, 0
    swModel.SketchManager.InsertSketch True
    
    ' 调 CreateSectionViewAt5
    Dim res As Boolean
    On Error Resume Next
    res = swDraw.CreateSectionViewAt5(cx + 0.05, cy - 0.05, 0, "A", 0, Nothing, False)
    Debug.Print "[auto_section] CreateSectionViewAt5 result=" & res
    On Error GoTo 0
End Sub
