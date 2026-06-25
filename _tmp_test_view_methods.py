"""Quick test: check what IView methods return for a drawing"""
import sys
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))


def main():
    import win32com.client as wc

    # Get SW
    sw = wc.GetActiveObject("SldWorks.Application")
    print(f"SW: {sw.RevisionNumber}")

    # Open drawing 002
    drw_path = str(REPO / "3D转2D测试图纸" / "LB26001-A-04-002.SLDDRW")
    print(f"\nOpening: {drw_path}")

    # Check if already open
    try:
        doc = sw.GetOpenDocumentByName(drw_path)
        if doc:
            print(f"  Already open: {doc.GetTitle()}")
        else:
            doc = None
    except:
        doc = None

    if doc is None:
        # Try OpenDoc6 with proper ref handling
        try:
            doc = sw.OpenDoc6(drw_path, 3, 1, "", 0, 0)
            if doc:
                print(f"  Opened: {doc.GetTitle()}")
            else:
                print(f"  OpenDoc6 returned None")
                return
        except Exception as e:
            print(f"  OpenDoc6 error: {e}")
            # Try OpenDoc5
            try:
                doc = sw.OpenDoc5(drw_path, 3, 1, "", 0)
                if doc:
                    print(f"  Opened (OpenDoc5): {doc.GetTitle()}")
                else:
                    return
            except Exception as e2:
                print(f"  OpenDoc5 error: {e2}")
                return

    # Get current sheet
    sheet = doc.GetCurrentSheet()
    print(f"\nSheet: {sheet.Name}")

    # Get views
    views = sheet.GetViews()
    print(f"Views count: {len(views) if views else 0}")

    if views:
        for i, view in enumerate(views):
            print(f"\n--- View {i}: {view.Name} (type={view.Type}) ---")

            # Try GetLines2
            try:
                lines = view.GetLines2()
                if lines:
                    print(f"  GetLines2: {len(lines)} values = {len(lines)//12} lines")
                    if len(lines) >= 12:
                        print(f"    First line: start=({lines[0]:.6f}, {lines[1]:.6f}, {lines[2]:.6f}) end=({lines[3]:.6f}, {lines[4]:.6f}, {lines[5]:.6f})")
                else:
                    print(f"  GetLines2: null/empty")
            except Exception as e:
                print(f"  GetLines2 error: {e}")

            # Try GetLines (without 2)
            try:
                lines1 = view.GetLines()
                if lines1:
                    print(f"  GetLines: {len(lines1)} values = {len(lines1)//12} lines")
                else:
                    print(f"  GetLines: null/empty")
            except Exception as e:
                print(f"  GetLines error: {e}")

            # Try GetVisibleEntities2 with edge
            try:
                comps = view.GetVisibleComponents()
                comp_count = len(comps) if comps else 0
                print(f"  GetVisibleComponents: {comp_count}")

                if comps and comp_count > 0:
                    for ci, comp in enumerate(comps[:2]):  # first 2 components
                        try:
                            edges = view.GetVisibleEntities2(comp, 1)  # 1 = edge
                            edge_count = len(edges) if edges else 0
                            print(f"    Comp[{ci}] GetVisibleEntities2(edge): {edge_count}")
                        except Exception as e:
                            print(f"    Comp[{ci}] GetVisibleEntities2(edge) error: {e}")

                        try:
                            verts = view.GetVisibleEntities2(comp, 3)  # 3 = vertex
                            vert_count = len(verts) if verts else 0
                            print(f"    Comp[{ci}] GetVisibleEntities2(vertex): {vert_count}")
                        except Exception as e:
                            print(f"    Comp[{ci}] GetVisibleEntities2(vertex) error: {e}")
            except Exception as e:
                print(f"  GetVisibleComponents error: {e}")

            # Try GetEdges
            try:
                edges = view.GetEdges()
                if edges:
                    print(f"  GetEdges: {len(edges)} edges")
                else:
                    print(f"  GetEdges: null/empty")
            except Exception as e:
                print(f"  GetEdges error: {e}")

            # Try GetCurves
            try:
                curves = view.GetCurves()
                if curves:
                    print(f"  GetCurves: {len(curves)} curves")
                else:
                    print(f"  GetCurves: null/empty")
            except Exception as e:
                print(f"  GetCurves error: {e}")

            # Try GetDisplayDimensions
            try:
                dims = view.GetDisplayDimensions()
                dim_count = len(dims) if dims else 0
                print(f"  GetDisplayDimensions: {dim_count}")
            except Exception as e:
                print(f"  GetDisplayDimensions error: {e}")

            # View scale and position
            try:
                print(f"  ScaleRatio: {view.ScaleRatio}")
                pos = view.Position
                if pos:
                    print(f"  Position: ({pos[0]:.6f}, {pos[1]:.6f})")
            except Exception as e:
                print(f"  Scale/Position error: {e}")

            # Try Outline
            try:
                outline = view.Outline
                if outline:
                    print(f"  Outline: {list(outline)}")
                else:
                    print(f"  Outline: null/empty")
            except Exception as e:
                print(f"  Outline error: {e}")

            if i >= 2:
                break

    # Also test opening a part copy
    print("\n\n=== Test OpenDoc6 for part copy ===")
    part_path = str(REPO / "3D转2D测试图纸" / "LB26001-A-04-002.SLDPRT")
    seed_path = str(REPO / "drw_output" / "runs" / "v21_test_seed" / "input_work" / "test_seed.SLDPRT")
    Path(seed_path).parent.mkdir(parents=True, exist_ok=True)

    import shutil
    shutil.copy2(part_path, seed_path)
    print(f"Copied to: {seed_path}")
    print(f"File exists: {Path(seed_path).exists()}")
    print(f"File size: {Path(seed_path).stat().st_size}")

    # Check if already open
    try:
        existing = sw.GetOpenDocumentByName(seed_path)
        if existing:
            print(f"Already open: {existing.GetTitle()}")
        else:
            print("Not open yet")
    except Exception as e:
        print(f"GetOpenDocumentByName error: {e}")

    # Try OpenDoc6
    try:
        part_doc = sw.OpenDoc6(seed_path, 1, 1, "", 0, 0)
        if part_doc:
            print(f"OpenDoc6 OK: {part_doc.GetTitle()}")
            # Get bounding box
            try:
                bbox = part_doc.GetBoundingBox(0, False)
                if bbox:
                    print(f"  BBox: {list(bbox)}")
            except Exception as e:
                print(f"  BBox error: {e}")
        else:
            print(f"OpenDoc6 returned None")
    except Exception as e:
        print(f"OpenDoc6 exception: {e}")

    # Try OpenDoc5
    try:
        part_doc = sw.OpenDoc5(seed_path, 1, 1, "", 0)
        if part_doc:
            print(f"OpenDoc5 OK: {part_doc.GetTitle()}")
        else:
            print(f"OpenDoc5 returned None")
    except Exception as e:
        print(f"OpenDoc5 exception: {e}")


if __name__ == "__main__":
    main()
