from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable


PIPELINE_SCRIPTS: dict[str, Path] = {
    "drw_qc_loop_v6": Path(".trae/specs/build-v6-and-validate-exe-ui/drw_qc_loop_v6.py"),
    "drw_generate_v6": Path(".trae/specs/build-v6-and-validate-exe-ui/drw_generate_v6.py"),
    "drw_qc_loop_v5": Path(".trae/specs/enforce-drawing-quality/drw_qc_loop.py"),
    "drw_generate_v5": Path(".trae/specs/enforce-drawing-quality/drw_generate_v5.py"),
    "drw_quality_check": Path(".trae/specs/enforce-drawing-quality/drw_quality_check.py"),
}


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    env_root = os.environ.get("SW_DRAWING_STUDIO_BUNDLE_ROOT")
    if env_root:
        return Path(env_root).resolve()
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)).resolve()
    return Path(__file__).resolve().parent.parent.parent


def runtime_root() -> Path:
    env_root = os.environ.get("SW_DRAWING_STUDIO_RUNTIME_ROOT")
    if env_root:
        return Path(env_root).resolve()
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def resource_path(relative: str | Path) -> Path:
    return bundle_root() / Path(relative)


def runtime_path(relative: str | Path) -> Path:
    return runtime_root() / Path(relative)


def pipeline_script_path(script_key: str) -> Path:
    try:
        rel = PIPELINE_SCRIPTS[script_key]
    except KeyError as exc:
        raise ValueError(f"Unknown pipeline script: {script_key}") from exc
    return resource_path(rel)


def pipeline_key_for_path(path: str | Path) -> str | None:
    resolved = Path(path).resolve()
    for key, rel in PIPELINE_SCRIPTS.items():
        try:
            if resolved == resource_path(rel).resolve():
                return key
        except OSError:
            continue
    return None


def pipeline_command(script_key: str, args: Iterable[str | Path] = ()) -> list[str]:
    str_args = [str(arg) for arg in args]
    if is_frozen():
        return [str(sys.executable), "--pipeline-script", script_key, *str_args]
    return [str(sys.executable), "-X", "utf8", "-u", str(pipeline_script_path(script_key)), *str_args]


def worker_command(worker_type: str, script_path: str | Path, args: Iterable[str | Path] = ()) -> tuple[str, list[str]]:
    str_args = [str(arg) for arg in args]
    if is_frozen():
        return str(sys.executable), ["--worker", worker_type, *str_args]
    return str(sys.executable), [str(script_path), *str_args]


def child_process_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["SW_DRAWING_STUDIO_BUNDLE_ROOT"] = str(bundle_root())
    env["SW_DRAWING_STUDIO_RUNTIME_ROOT"] = str(runtime_root())
    env["PYTHONPATH"] = str(bundle_root()) + os.pathsep + env.get("PYTHONPATH", "")
    return env
