"""Identity of the installed algorithm source, usable by either caller."""

import hashlib
from pathlib import Path


def code_digest():
    root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix in {".py", ".txt", ".mjs", ".cjs"}:
            digest.update(
                path.relative_to(root).as_posix().encode()
                + b"\0"
                + hashlib.sha256(path.read_bytes()).digest()
            )
    return digest.hexdigest()
