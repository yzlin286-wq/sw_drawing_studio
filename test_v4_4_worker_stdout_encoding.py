from __future__ import annotations

from pathlib import Path


WORKERS_DIR = Path(__file__).resolve().parent / "app" / "workers"


def _worker_sources() -> list[Path]:
    return sorted(path for path in WORKERS_DIR.glob("*.py") if path.name != "__init__.py")


def test_jsonl_workers_force_utf8_stdout() -> None:
    offenders: list[str] = []
    for path in _worker_sources():
        text = path.read_text(encoding="utf-8")
        if "ensure_ascii=False" not in text:
            continue
        if "sys.stdout.reconfigure(encoding=\"utf-8\"" not in text:
            offenders.append(path.name)

    assert offenders == [], f"workers with non-ASCII JSON stdout must force UTF-8: {offenders}"


def test_stdout_reconfigure_never_omits_encoding() -> None:
    offenders: list[str] = []
    for path in _worker_sources():
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if "sys.stdout.reconfigure(" in line and "encoding=\"utf-8\"" not in line:
                offenders.append(f"{path.name}: {line.strip()}")

    assert offenders == [], f"stdout reconfigure must include encoding='utf-8': {offenders}"


if __name__ == "__main__":
    test_jsonl_workers_force_utf8_stdout()
    test_stdout_reconfigure_never_omits_encoding()
    print("PASS test_v4_4_worker_stdout_encoding")
