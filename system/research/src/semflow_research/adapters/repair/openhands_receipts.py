"""Commit worker output on every exit, including partial work and cancellation."""

import io
from zipfile import ZIP_DEFLATED, ZipFile

from semflow_contracts.common import canonical_bytes, digest
from semflow_contracts.errors import ResearchError
from semflow_contracts.openhands import OpenHandsReceipt


def publish(context, directory, config, *, status, error_code=None):
    files = {}
    secret = (
        context.settings.OPENHANDS_API_KEY.get_secret_value()
        or context.settings.AI_API_KEY.get_secret_value()
    )
    for path in sorted(directory.rglob("*")):
        name = path.relative_to(directory).as_posix()
        if (
            path.is_symlink()
            or not path.is_file()
            or name.split("/")[0] in {"workspace", "worker-code"}
        ):
            continue
        raw = path.read_bytes()
        if secret:
            raw = raw.replace(secret.encode(), b"[REDACTED]")
        files[name] = context.artifacts.commit(
            raw,
            kind="log",
            schema_version="semflow.openhands-file/1",
            media_type="application/octet-stream",
        )
    workspace = directory / "workspace"
    if workspace.is_dir():
        buffer = io.BytesIO()
        with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
            for path in sorted(workspace.rglob("*")):
                if path.is_file() and not path.is_symlink():
                    archive.writestr(
                        path.relative_to(workspace).as_posix(), path.read_bytes()
                    )
        files["workspace.zip"] = context.artifacts.commit(
            buffer.getvalue(),
            kind="materials",
            schema_version="semflow.openhands-workspace/1",
            media_type="application/zip",
        )
    body = OpenHandsReceipt(
        execution_id=context.execution_id,
        policy_digest=digest(config),
        status=status,
        error_code=error_code,
        files=files,
    )
    reference = context.artifacts.commit(
        canonical_bytes(body),
        kind="validation_receipt",
        schema_version=body.schema_version,
    )
    return reference, tuple(files.values())


def read(artifacts, reference, *, execution_id):
    # WIRE-RECV:research.openhands_receipt — peer: publish / OpenHandsReceipt declaration.
    # AGENT: read all member bytes before projecting status or usage; a failed
    # worker's retained workspace does not authorize applying that candidate.
    if (
        reference.owner_execution_id != execution_id
        or reference.schema_version != "semflow.openhands-receipt/1"
    ):
        raise ResearchError("identity_mismatch", "OpenHands receipt identity differs")
    body = OpenHandsReceipt.model_validate_json(artifacts.read(reference))
    if body.execution_id != execution_id:
        raise ResearchError(
            "identity_mismatch", "OpenHands receipt has a foreign producer"
        )
    for member in body.files.values():
        artifacts.read(member)
    return body
