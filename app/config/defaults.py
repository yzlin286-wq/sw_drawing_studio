import os
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml


def app_data_dir() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        root = Path(base)
    else:
        root = Path.home() / "AppData" / "Roaming"
    path = root / "sw_drawing_studio"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _repo_root() -> Path:
    env_root = os.environ.get("SW_DRAWING_STUDIO_BUNDLE_ROOT")
    if env_root:
        return Path(env_root).resolve()
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)).resolve()
    return Path(__file__).resolve().parent.parent.parent


def load_yaml(path: Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        return {}
    return data


def save_yaml(path: Path, data: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def _ensure_config(filename: str) -> Path:
    target = app_data_dir() / filename
    if not target.exists():
        example = _repo_root() / "config" / f"{filename}.example"
        if example.exists():
            shutil.copyfile(example, target)
    return target


def get_llm_config() -> dict[str, Any]:
    return load_yaml(_ensure_config("llm.yaml"))


def get_app_config() -> dict[str, Any]:
    data = load_yaml(_ensure_config("app.yaml"))
    default_drwdot = _repo_root() / "templates" / "gb_a4_landscape.DRWDOT"
    if not default_drwdot.exists():
        default_drwdot = _repo_root() / "templates" / "gb_a4_landscape.drwdot"
    tpl = data.get("drwdot_template")
    if not tpl:
        data["drwdot_template"] = str(default_drwdot)
    else:
        p = Path(tpl)
        if not p.is_absolute():
            data["drwdot_template"] = str((_repo_root() / p).resolve())
    return data
