from __future__ import annotations

import traceback
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class _WorkerSignals(QObject):
    finished = Signal(object, object)


class LLMWorker(QRunnable):
    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.signals = _WorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        result: Any = None
        err: BaseException | None = None
        try:
            result = self._fn(*self._args, **self._kwargs)
        except BaseException as exc:
            err = exc
            try:
                traceback.print_exc()
            except Exception:
                pass
        finally:
            try:
                self.signals.finished.emit(result, err)
            except Exception:
                pass


class RunnerWorker(QRunnable):
    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.signals = _WorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        result: Any = None
        err: BaseException | None = None
        try:
            result = self._fn(*self._args, **self._kwargs)
        except BaseException as exc:
            err = exc
            try:
                traceback.print_exc()
            except Exception:
                pass
        finally:
            try:
                self.signals.finished.emit(result, err)
            except Exception:
                pass
