"""Keep the existing materials API while the kernel owns the actual source map."""

import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.adapters.artifacts import ArtifactStore
from app.services.context_materials import digest


def save_scout_materials(stage, project):
    # Peer: routes.stages.stage_materials / scout_continuation.frozen_map.
    # AGENT: this is an explicitly translated platform view; preserve opaque
    # window IDs and map identity. The immutable research result is never edited.
    directory = ArtifactStore().directory(str(stage.id))
    receipt = {"identity": digest({"project": project, "inputs": stage.inputs})}
    for name, value in (
        ("scout-map.json", project),
        ("scout-map-receipt.json", receipt),
    ):
        with NamedTemporaryFile(dir=directory, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(value, ensure_ascii=False).encode())
        temporary.replace(directory / name)


def save_review_materials(stage, pool):
    """The old materials API reads a translated view of the immutable core pool."""
    directory = ArtifactStore().directory(str(stage.id))
    with NamedTemporaryFile(dir=directory, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(json.dumps(pool, ensure_ascii=False).encode())
    temporary.replace(directory / "review-pool.json")
