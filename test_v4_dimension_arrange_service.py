import json
from pathlib import Path
from tempfile import TemporaryDirectory

from app.services.dimension_arrange_service import arrange_dimensions


class FakeDimension:
    FullName = "D1@Sketch"


class FakeDisplayDimension:
    def __init__(self, position, arrow_position=None):
        self.TextPosition = list(position)
        self.ArrowHeadPosition = list(arrow_position or position)

    def GetDimension2(self, _index):
        return FakeDimension()


def _xy(value):
    value = getattr(value, "value", value)
    return tuple(float(item) for item in list(value)[:2])


class FakeView:
    def __init__(self, name, outline, dims):
        self.Name = name
        self._outline = outline
        self._dims = dims

    def GetOutline(self):
        return self._outline

    def GetDisplayDimensions(self):
        return self._dims

    def GetFirstAnnotation3(self):
        return None


class FakeSheet:
    def __init__(self, views):
        self._views = views

    def GetViews(self):
        return self._views


class FakeDoc:
    def __init__(self, sheet):
        self._sheet = sheet

    def GetCurrentSheet(self):
        return self._sheet


class FakeAnnotation:
    def __init__(self, position):
        self._position = list(position)
        self._next = None

    def GetType(self):
        return 1

    def GetPosition(self):
        return self._position

    @property
    def TextPosition(self):
        raise AttributeError("annotation has no TextPosition")

    @TextPosition.setter
    def TextPosition(self, _value):
        raise AttributeError("annotation has no TextPosition")

    def SetPosition2(self, x, y, _z):
        self._position = [float(x), float(y), 0.0]

    def GetNext3(self):
        return self._next


class FakeAnnotationView(FakeView):
    def __init__(self, name, outline, annotations):
        super().__init__(name, outline, [])
        self._annotations = annotations
        for left, right in zip(self._annotations, self._annotations[1:]):
            left._next = right

    def GetFirstAnnotation3(self):
        return self._annotations[0] if self._annotations else None


def test_arrange_dimensions_moves_dense_text_out_of_titlebar_and_notes_boxes() -> None:
    dims = [
        FakeDisplayDimension((0.220, 0.020)),
        FakeDisplayDimension((0.221, 0.021)),
        FakeDisplayDimension((0.222, 0.022)),
    ]
    view = FakeView("Front", (0.150, 0.075, 0.220, 0.120), dims)
    doc = FakeDoc(FakeSheet([view]))
    layout_plan = {
        "sheet_size": {"width": 0.297, "height": 0.210},
        "titlebar_box_norm": [0.68, 0.0, 1.0, 0.18],
        "notes_box_norm": [0.58, 0.18, 0.98, 0.35],
    }

    with TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        result = arrange_dimensions(
            object(),
            doc,
            run_dir=run_dir,
            run_id="dimension-arrange-test",
            layout_plan=layout_plan,
        )
        report = json.loads(run_dir.joinpath("qc", "dimension_arrange.json").read_text(encoding="utf-8"))

    assert result.success is True
    assert result.total_dimensions == 3
    assert result.adjusted_dimensions >= 1
    assert result.avoid_collision_before == 3
    assert result.avoid_collision_after < result.avoid_collision_before
    assert report["success"] is True
    assert report["avoid_collision_after"] == result.avoid_collision_after
    assert dims[0].TextPosition != [0.220, 0.020]


def test_arrange_dimensions_collects_displaydim_annotations_when_api_list_is_empty() -> None:
    annotations = [
        FakeAnnotation((0.220, 0.020)),
        FakeAnnotation((0.221, 0.021)),
    ]
    view = FakeAnnotationView("Front", (0.150, 0.075, 0.220, 0.120), annotations)
    doc = FakeDoc(FakeSheet([view]))
    layout_plan = {
        "sheet_size": {"width": 0.297, "height": 0.210},
        "titlebar_box_norm": [0.68, 0.0, 1.0, 0.18],
        "notes_box_norm": [0.58, 0.18, 0.98, 0.35],
    }

    result = arrange_dimensions(
        object(),
        doc,
        run_dir=None,
        run_id="annotation-chain-test",
        layout_plan=layout_plan,
    )

    assert result.success is True
    assert result.total_dimensions == 2
    assert result.adjusted_dimensions >= 1
    assert any(
        ann.GetPosition()[:2] != original
        for ann, original in zip(annotations, ([0.220, 0.020], [0.221, 0.021]))
    )


def test_arrange_dimensions_uses_long_thin_reference_lanes() -> None:
    dims = [
        FakeDisplayDimension((0.080, 0.169)),
        FakeDisplayDimension((0.081, 0.169)),
        FakeDisplayDimension((0.082, 0.169)),
        FakeDisplayDimension((0.083, 0.169)),
    ]
    view = FakeView("Front", (0.0483, 0.1621, 0.1717, 0.1770), dims)
    doc = FakeDoc(FakeSheet([view]))
    layout_plan = {
        "part_class": "long_thin",
        "sheet_size": {"width": 0.297, "height": 0.210},
        "titlebar_box_norm": [0.68, 0.0, 1.0, 0.18],
        "notes_box_norm": [0.58, 0.18, 0.98, 0.35],
        "views": [
            {
                "slot": "front",
                "box_norm": [0.1627, 0.7719, 0.5781, 0.8429],
                "center_norm": [0.3704, 0.8074],
            }
        ],
    }

    result = arrange_dimensions(
        object(),
        doc,
        run_dir=None,
        run_id="long-thin-lane-test",
        layout_plan=layout_plan,
    )

    new_positions = [_xy(dim.TextPosition) for dim in dims]
    spread_x = max(pos[0] for pos in new_positions) - min(pos[0] for pos in new_positions)
    assert result.success is True
    assert result.adjusted_dimensions == 4
    assert spread_x > 0.050
    assert result.overlap_after == 0


def test_arrange_dimensions_pushes_long_thin_top_view_to_protected_lane() -> None:
    dims = [
        FakeDisplayDimension((0.090, 0.140)),
        FakeDisplayDimension((0.104, 0.140)),
        FakeDisplayDimension((0.118, 0.140)),
    ]
    top_outline = (0.0483, 0.1177, 0.1717, 0.1321)
    view = FakeView("Top", top_outline, dims)
    doc = FakeDoc(FakeSheet([view]))
    layout_plan = {
        "part_class": "long_thin",
        "sheet_size": {"width": 0.297, "height": 0.210},
        "titlebar_box_norm": [0.68, 0.0, 1.0, 0.18],
        "notes_box_norm": [0.58, 0.18, 0.98, 0.35],
        "views": [
            {
                "slot": "top",
                "box_norm": [0.1627, 0.5605, 0.5781, 0.6291],
                "center_norm": [0.3704, 0.5948],
            }
        ],
    }

    result = arrange_dimensions(
        object(),
        doc,
        run_dir=None,
        run_id="long-thin-top-protected-lane",
        layout_plan=layout_plan,
    )

    new_positions = [_xy(dim.TextPosition) for dim in dims]
    assert result.success is True
    assert result.adjusted_dimensions == 3
    assert min(pos[1] for pos in new_positions) >= top_outline[3] + 0.017
    assert result.overlap_after == 0


def test_arrange_dimensions_keeps_dense_top_dimensions_in_local_lanes() -> None:
    dims = [
        FakeDisplayDimension((0.090, 0.140)),
        FakeDisplayDimension((0.104, 0.140)),
        FakeDisplayDimension((0.118, 0.140)),
        FakeDisplayDimension((0.132, 0.140)),
        FakeDisplayDimension((0.096, 0.108)),
        FakeDisplayDimension((0.112, 0.108)),
        FakeDisplayDimension((0.128, 0.108)),
    ]
    top_outline = (0.0483, 0.1177, 0.1717, 0.1321)
    view = FakeView("Top", top_outline, dims)
    doc = FakeDoc(FakeSheet([view]))
    layout_plan = {
        "part_class": "long_thin",
        "sheet_size": {"width": 0.297, "height": 0.210},
        "titlebar_box_norm": [0.68, 0.0, 1.0, 0.18],
        "notes_box_norm": [0.58, 0.18, 0.98, 0.35],
        "views": [
            {
                "slot": "top",
                "box_norm": [0.1627, 0.5605, 0.5781, 0.6291],
                "center_norm": [0.3704, 0.5948],
            }
        ],
    }

    with TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        result = arrange_dimensions(
            object(),
            doc,
            run_dir=run_dir,
            run_id="long-thin-top-local-lane",
            layout_plan=layout_plan,
        )
        report = json.loads(run_dir.joinpath("qc", "dimension_arrange.json").read_text(encoding="utf-8"))

    callout_dims = [item for item in report["dimensions"] if item.get("lane_role") == "right_callout"]
    lower_linear_dims = [
        item for item in report["dimensions"]
        if item.get("lane_role") == "standard" and item["original_position"][1] < top_outline[1]
    ]
    local_positions = [tuple(item["new_position"]) for item in report["dimensions"]]
    assert result.success is True
    assert result.callout_lane_applied is False
    assert result.callout_lane_count == 0
    assert report["callout_lane_count"] == result.callout_lane_count
    assert callout_dims == []
    assert max(pos[0] for pos in local_positions) <= top_outline[2] + 0.018
    assert lower_linear_dims
    assert max(item["new_position"][1] for item in lower_linear_dims) <= top_outline[1] - 0.017
    assert result.overlap_after == 0


def test_arrange_dimensions_reports_reference_lane_geometry_issues() -> None:
    dims = [
        FakeDisplayDimension((0.205, 0.158), arrow_position=(0.112, 0.123)),
    ]
    top_outline = (0.0483, 0.1177, 0.1717, 0.1321)
    view = FakeView("Top", top_outline, dims)
    doc = FakeDoc(FakeSheet([view]))
    layout_plan = {
        "part_class": "long_thin",
        "sheet_size": {"width": 0.297, "height": 0.210},
        "titlebar_box_norm": [0.68, 0.0, 1.0, 0.18],
        "views": [
            {
                "slot": "top",
                "box_norm": [0.1627, 0.5605, 0.5781, 0.6291],
                "center_norm": [0.3704, 0.5948],
            }
        ],
    }

    with TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        result = arrange_dimensions(
            object(),
            doc,
            run_dir=run_dir,
            run_id="reference-lane-geometry-issue",
            layout_plan=layout_plan,
        )
        report = json.loads(run_dir.joinpath("qc", "dimension_arrange.json").read_text(encoding="utf-8"))

    assert result.success is True
    assert result.line_crossing_before == 0
    assert result.reference_lane_geometry_issue_count_before >= 1
    assert report["reference_lane_geometry_issue_count_before"] >= 1
    assert "reference_lane_geometry_issue_count_after" in report
    assert "reference_lane_geometry_issues" in report


def test_arrange_dimensions_allows_compact_top_side_lane_policy() -> None:
    compact_dim = FakeDisplayDimension((0.040, 0.124), arrow_position=(0.050, 0.124))
    far_dim = FakeDisplayDimension((0.010, 0.124), arrow_position=(0.050, 0.124))
    top_outline = (0.0483, 0.1177, 0.1717, 0.1321)
    layout_plan = {
        "part_class": "long_thin",
        "sheet_size": {"width": 0.297, "height": 0.210},
        "views": [
            {
                "slot": "top",
                "box_norm": [0.1627, 0.5605, 0.5781, 0.6291],
                "center_norm": [0.3704, 0.5948],
            }
        ],
        "reference_dimension_lane_policy": {
            "allow_compact_top_view_side_lanes": True,
            "top_view_side_lane_max_gap_m": 0.018,
        },
    }

    compact_result = arrange_dimensions(
        object(),
        FakeDoc(FakeSheet([FakeView("Top", top_outline, [compact_dim])])),
        run_dir=None,
        run_id="compact-top-side-lane",
        layout_plan=layout_plan,
    )
    far_result = arrange_dimensions(
        object(),
        FakeDoc(FakeSheet([FakeView("Top", top_outline, [far_dim])])),
        run_dir=None,
        run_id="far-top-side-lane",
        layout_plan=layout_plan,
    )

    assert compact_result.reference_lane_geometry_issue_count_before == 0
    assert far_result.reference_lane_geometry_issue_count_before >= 1


if __name__ == "__main__":
    test_arrange_dimensions_moves_dense_text_out_of_titlebar_and_notes_boxes()
    test_arrange_dimensions_collects_displaydim_annotations_when_api_list_is_empty()
    test_arrange_dimensions_uses_long_thin_reference_lanes()
    test_arrange_dimensions_pushes_long_thin_top_view_to_protected_lane()
    test_arrange_dimensions_keeps_dense_top_dimensions_in_local_lanes()
    test_arrange_dimensions_reports_reference_lane_geometry_issues()
    test_arrange_dimensions_allows_compact_top_side_lane_policy()
    print("PASS test_v4_dimension_arrange_service")
