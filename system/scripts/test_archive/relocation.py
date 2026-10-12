"""Resolve historical receipt locations after repository-only directory changes."""

import json
from pathlib import PurePosixPath


def file_map(root):
    path = root / "design/repository-file-map.json"
    if not path.is_file():
        return {}
    return {
        row["old_path"]: row["path"] for row in json.loads(path.read_text())["files"]
    }


def resolve(root, relative, locations):
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Historical receipt path must stay inside the repository")
    original = root / relative
    if original.is_file():
        return original
    relocated = PurePosixPath(locations.get(relative, relative))
    if relocated.is_absolute() or ".." in relocated.parts:
        raise ValueError("Relocated receipt path must stay inside the repository")
    return root / relocated
