Attribute VB_Name = "auto_section"
' ============================================================
' auto_section.bas
' Purpose: In the active SolidWorks DrawingDoc, find the first
'          non-sheet view (skip type=1), draw a horizontal cut
'          line through it, and create Section View "A".
'
' How to import:
'   1. Open SolidWorks and load the target drawing.
'   2. Tools -> Macro -> New (save as auto_section.swp anywhere)
'      OR Tools -> Macro -> Edit, then in the VBA IDE:
'        File -> Import File... -> select auto_section.bas
'   3. Run the macro 'main'.
' ============================================================

Option Explicit

Sub main()
    Dim swApp As Object
    Dim model As Object
    Dim drw As Object
    Dim sheet As Object
    Dim view As Object
    Dim outline As Variant
    Dim xmin As Double, ymin As Double, xmax As Double, ymax As Double
    Dim cy As Double, sx As Double, sy As Double
    Dim line As Object
    Dim sketchMgr As Object
    Dim selMgr As Object
    Dim secView As Object
    Dim boolStatus As Boolean

    On Error GoTo Fail

    Set swApp = Application.SldWorks
    Set model = swApp.ActiveDoc

    If model Is Nothing Then
        Debug.Print "SECTION_FAIL: no active doc"
        Exit Sub
    End If

    If model.GetType <> 3 Then
        Debug.Print "SECTION_FAIL: active doc is not a drawing"
        Exit Sub
    End If

    Set drw = model

    ' Make sure we are editing the sheet, not a view
    drw.EditSheet

    ' Find first non-sheet view (skip type=1 which is the sheet itself)
    Set view = drw.GetFirstView
    Do While Not view Is Nothing
        If view.Type <> 1 Then
            Exit Do
        End If
        Set view = view.GetNextView
    Loop

    If view Is Nothing Then
        Debug.Print "SECTION_FAIL: no drawing view found"
        Exit Sub
    End If

    ' Get outline (xmin, ymin, xmax, ymax) in sheet coordinates
    outline = view.GetOutline
    xmin = outline(0)
    ymin = outline(1)
    xmax = outline(2)
    ymax = outline(3)

    cy = (ymin + ymax) / 2#
    sx = (xmin + xmax) / 2#
    sy = ymin - 0.04

    ' Draw a horizontal cut line across the view
    Set sketchMgr = model.SketchManager
    Set line = sketchMgr.CreateLine(xmin - 0.005, cy, 0#, xmax + 0.005, cy, 0#)

    If line Is Nothing Then
        Debug.Print "SECTION_FAIL: CreateLine returned Nothing"
        Exit Sub
    End If

    ' Select the line
    boolStatus = line.Select4(False, Nothing)

    ' Create section view A
    Set secView = model.CreateSectionViewAt5(sx, sy, 0#, "A", 6, Empty, 0)

    If secView Is Nothing Then
        Debug.Print "SECTION_FAIL: CreateSectionViewAt5 returned Nothing"
        Exit Sub
    End If

    Debug.Print "SECTION_OK"
    Exit Sub

Fail:
    Debug.Print "SECTION_FAIL: " & Err.Description
End Sub
