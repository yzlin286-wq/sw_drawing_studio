import importlib.util
from pathlib import Path


def _load_quality_check_module():
    path = Path(".trae/specs/enforce-drawing-quality/drw_quality_check.py")
    spec = importlib.util.spec_from_file_location("drw_quality_check_for_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class _FakeNote:
    def __init__(self, text: str):
        self._text = text

    def GetText(self):
        return self._text


class _FakeAnnotation:
    def GetText(self):
        return ""

    def GetSpecificAnnotation(self):
        return _FakeNote("技术要求：\n1. 未注公差按 GB/T 1804-m。\n2. 其余 Ra3.2。\n3. 基准 A。")


def test_note_text_falls_back_to_specific_annotation() -> None:
    module = _load_quality_check_module()

    text = module._extract_note_text(_FakeAnnotation())

    assert "技术要求" in text
    assert "Ra3.2" in text
    assert "基准 A" in text


if __name__ == "__main__":
    test_note_text_falls_back_to_specific_annotation()
    print("PASS test_v3_quality_check_note_text")
