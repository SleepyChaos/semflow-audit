"""Hash frozen implementation inputs, excluding the runtime artifact tree."""

import hashlib
from pathlib import Path


def implementation_hashes(frozen: Path):
    return {
        str(p.relative_to(frozen)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in frozen.rglob("*")
        if p.is_file()
        and p.suffix in {".py", ".txt"}
        and p.relative_to(frozen).parts[0] != "artifacts"
    }
