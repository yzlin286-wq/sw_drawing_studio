from __future__ import annotations

import sys
import types
from pathlib import Path
from tempfile import TemporaryDirectory

from app.services import solidworks_resource_audit as audit


class _FakePythonCom(types.ModuleType):
    def __init__(self) -> None:
        super().__init__("pythoncom")
        self.calls: list[str] = []

    def CoInitialize(self) -> None:
        self.calls.append("CoInitialize")

    def CoUninitialize(self) -> None:
        self.calls.append("CoUninitialize")


class _FakeModel:
    def __init__(self, title: str, path: str) -> None:
        self._title = title
        self._path = path

    def GetTitle(self) -> str:
        return self._title

    def GetPathName(self) -> str:
        return self._path

    def GetType(self) -> int:
        return 3


class _FakeSolidWorks:
    def __init__(self, model: _FakeModel) -> None:
        self.model = model
        self.close_calls: list[str] = []

    def GetOpenDocumentByName(self, name: str):
        if self.model is None:
            return None
        if name in {self.model.GetPathName(), self.model.GetTitle(), Path(self.model.GetPathName()).name}:
            return self.model
        return None

    def GetDocuments(self):
        return [] if self.model is None else [self.model]

    def CloseDoc(self, title: str) -> None:
        self.close_calls.append(title)
        self.model = None


def test_cleanup_job_owned_documents_initializes_com_and_closes_docs() -> None:
    with TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        job_id = "job-clean"
        model = _FakeModel("part-a.SLDPRT", str(run_dir / "part-a.SLDPRT"))
        sw = _FakeSolidWorks(model)
        fake_pythoncom = _FakePythonCom()
        fake_win32com = types.ModuleType("win32com")
        fake_client = types.ModuleType("win32com.client")
        fake_client.GetActiveObject = lambda progid: sw
        fake_win32com.client = fake_client

        old_pythoncom = sys.modules.get("pythoncom")
        old_win32com = sys.modules.get("win32com")
        old_win32com_client = sys.modules.get("win32com.client")
        old_holds_lock = audit.current_job_holds_lock
        try:
            sys.modules["pythoncom"] = fake_pythoncom
            sys.modules["win32com"] = fake_win32com
            sys.modules["win32com.client"] = fake_client
            audit.current_job_holds_lock = lambda current_job_id: current_job_id == job_id
            audit.append_document_registry_event(
                audit.document_registry_path(run_dir),
                "solidworks_doc_opened",
                job_id=job_id,
                role="copied_part",
                path=model.GetPathName(),
                title=model.GetTitle(),
                doc_type="part",
                stage="initial_part_open",
                owned_by_job=True,
            )

            result = audit.cleanup_job_owned_documents(run_dir, job_id)

            assert result["pass"] is True
            assert result["status"] == "pass"
            assert sw.close_calls == ["part-a.SLDPRT"]
            assert fake_pythoncom.calls == ["CoInitialize", "CoUninitialize"]
            summary = result["registry_summary"]
            assert summary["open_job_owned_document_count"] == 0
            assert summary["close_failure_count"] == 0
            assert summary["closed_count"] == 1
        finally:
            audit.current_job_holds_lock = old_holds_lock
            _restore_module("pythoncom", old_pythoncom)
            _restore_module("win32com", old_win32com)
            _restore_module("win32com.client", old_win32com_client)


def _restore_module(name: str, value) -> None:
    if value is None:
        sys.modules.pop(name, None)
    else:
        sys.modules[name] = value


if __name__ == "__main__":
    test_cleanup_job_owned_documents_initializes_com_and_closes_docs()
    print("PASS test_v4_4_solidworks_resource_audit")
