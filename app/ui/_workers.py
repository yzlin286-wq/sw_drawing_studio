"""Deprecated UI worker module.

Long-running UI actions must use JobRuntimeFacade/QProcess workers. This module
is kept only so accidental legacy imports fail loudly instead of reintroducing
in-process background execution in the UI process.
"""
from __future__ import annotations


def __getattr__(name: str):
    raise AttributeError(
        f"app.ui._workers.{name} is deprecated; submit long-running work "
        "through JobRuntimeFacade and QProcess workers."
    )
