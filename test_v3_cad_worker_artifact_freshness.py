from __future__ import annotations

import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from app.workers.cad_job_worker import _copy_if_exists


def test_copy_if_exists_skips_legacy_artifact_older_than_job_start() -> None:
    with TemporaryDirectory() as tmp:
        src = Path(tmp) / "old.PNG"
        dst_dir = Path(tmp) / "run" / "drawing"
        src.write_bytes(b"stale-image")
        old_mtime = time.time() - 3600
        os.utime(src, (old_mtime, old_mtime))
        stale: list[dict] = []

        copied = _copy_if_exists(src, dst_dir, min_mtime=time.time(), stale_artifacts=stale)

        assert copied == ""
        assert not (dst_dir / src.name).exists()
        assert stale
        assert stale[0]["reason"] == "legacy_output_older_than_job_start"


def test_copy_if_exists_preserves_fresh_source_mtime() -> None:
    with TemporaryDirectory() as tmp:
        src = Path(tmp) / "fresh.PNG"
        dst_dir = Path(tmp) / "run" / "drawing"
        src.write_bytes(b"fresh-image")
        src_mtime = time.time()
        os.utime(src, (src_mtime, src_mtime))

        copied = _copy_if_exists(src, dst_dir, min_mtime=src_mtime - 10)

        dst = Path(copied)
        assert dst.exists()
        assert dst.read_bytes() == b"fresh-image"
        assert abs(dst.stat().st_mtime - src.stat().st_mtime) < 0.01


if __name__ == "__main__":
    test_copy_if_exists_skips_legacy_artifact_older_than_job_start()
    test_copy_if_exists_preserves_fresh_source_mtime()
    print("PASS test_v3_cad_worker_artifact_freshness")
