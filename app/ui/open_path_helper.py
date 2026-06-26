from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


def open_local_path(path: str | Path) -> bool:
    """Open a local file or directory through Qt instead of spawning explorer."""
    try:
        return bool(QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path)))))
    except Exception:
        return False
