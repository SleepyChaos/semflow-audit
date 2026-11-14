"""Select lock forks for the actual interpreter without changing pinned versions."""

import pytest

from scripts.verify_research_install import locked_versions


def test_dependency_verifier_uses_resolution_markers_instead_of_last_version(tmp_path):
    lock = tmp_path / "uv.lock"
    lock.write_text("""[[package]]
name = "anyio"
version = "4.14.2"
resolution-markers = ["python_full_version < '99'"]
[[package]]
name = "anyio"
version = "4.15.1"
resolution-markers = ["python_full_version >= '99'"]
""")
    assert locked_versions(lock) == {"anyio": "4.14.2"}


def test_dependency_verifier_rejects_ambiguous_active_lock_versions(tmp_path):
    lock = tmp_path / "uv.lock"
    lock.write_text("""[[package]]
name = "anyio"
version = "4.14.2"
[[package]]
name = "anyio"
version = "4.15.1"
""")
    with pytest.raises(ValueError, match="Ambiguous lock versions"):
        locked_versions(lock)
