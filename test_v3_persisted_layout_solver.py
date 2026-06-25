import app.services.persisted_layout_solver as solver
from app.services.persisted_layout_solver import _apply_target_centers_to_views, _save_close_reopen


class FakeView:
    def __init__(self, name: str):
        self.Name = name
        self._position = (0.0, 0.0)
        self.removed_alignment = False

    @property
    def Position(self):
        return self._position

    @Position.setter
    def Position(self, value):
        if hasattr(value, "value"):
            value = value.value
        self._position = tuple(value)

    def RemoveAlignment(self):
        self.removed_alignment = True


class FakeExtension:
    def __init__(self, owner):
        self.owner = owner

    def SaveAs(self, path, *args):
        self.owner.saved_paths.append(path)
        return True


class FakeDoc:
    def __init__(self, title: str, path: str):
        self.title = title
        self.path = path
        self.saved_paths = []
        self.Extension = FakeExtension(self)

    def GetTitle(self):
        return self.title

    def GetPathName(self):
        return self.path


class FakeSw:
    def __init__(self, active_doc, reopened_doc):
        self.ActiveDoc = active_doc
        self.reopened_doc = reopened_doc
        self.closed_titles = []
        self.opened_paths = []

    def CloseDoc(self, title):
        self.closed_titles.append(title)

    def SetUserPreferenceIntegerValue(self, *_args):
        return True

    def OpenDoc6(self, path, *_args):
        self.opened_paths.append(path)
        return self.reopened_doc


def test_apply_target_centers_to_views_sets_positions_in_order() -> None:
    views = [FakeView("工程图视图1"), FakeView("工程图视图2"), FakeView("工程图视图3")]
    centers = {
        "front": (0.11, 0.16955),
        "top": (0.11, 0.1249),
        "right": (0.2156, 0.16955),
    }

    applied = _apply_target_centers_to_views(views, centers)

    assert applied == centers
    assert _pos(views[0]) == (0.11, 0.16955)
    assert _pos(views[1]) == (0.11, 0.1249)
    assert _pos(views[2]) == (0.2156, 0.16955)
    assert all(view.removed_alignment for view in views)


def test_save_close_reopen_uses_provided_drawing_doc_not_active_doc() -> None:
    original_sleep = solver.time.sleep
    solver.time.sleep = lambda *_args, **_kwargs: None
    try:
        active_part = FakeDoc("LB26001-A-04-006.SLDPRT", r"C:\work\LB26001-A-04-006.SLDPRT")
        drawing = FakeDoc("LB26001-A-04-006_v5", r"C:\work\LB26001-A-04-006_v5.SLDDRW")
        reopened = FakeDoc("LB26001-A-04-006_v5", r"C:\work\LB26001-A-04-006_v5.SLDDRW")
        sw = FakeSw(active_part, reopened)

        result = _save_close_reopen(sw, r"C:\work\LB26001-A-04-006_v5.SLDDRW", doc=drawing)

        assert result is reopened
        assert drawing.saved_paths == [r"C:\work\LB26001-A-04-006_v5.SLDDRW"]
        assert active_part.saved_paths == []
        assert sw.closed_titles == ["LB26001-A-04-006_v5"]
        assert sw.opened_paths == [r"C:\work\LB26001-A-04-006_v5.SLDDRW"]
    finally:
        solver.time.sleep = original_sleep


def _pos(view: FakeView) -> tuple[float, float]:
    values = list(view.Position)
    return (round(float(values[0]), 5), round(float(values[1]), 5))


if __name__ == "__main__":
    test_apply_target_centers_to_views_sets_positions_in_order()
    test_save_close_reopen_uses_provided_drawing_doc_not_active_doc()
    print("PASS test_v3_persisted_layout_solver")
