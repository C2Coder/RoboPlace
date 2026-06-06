from __future__ import annotations

import os
from pathlib import Path


def load_env_file(env_path: str = ".env") -> None:
    path = Path(env_path)
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
            value = value[1:-1]

        if key:
            os.environ.setdefault(key, value)


def load_project_env(anchor_file: str) -> None:
    root = Path(anchor_file).resolve().parent.parent
    load_env_file(str(root / ".env"))
