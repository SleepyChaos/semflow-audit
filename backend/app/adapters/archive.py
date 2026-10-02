import hashlib
import shutil
import stat
from collections import Counter
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

from app.core.audit_config import audit_settings
from app.domain.audit import AuditError

EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "javascript",
    ".tsx": "javascript",
}
IGNORED = {".git", "node_modules", ".venv", "__pycache__", "__MACOSX"}


def extract_snapshot(
    archive: Path, destination: Path, language: str
) -> tuple[str, dict]:
    destination.mkdir(parents=True, exist_ok=False)
    total = 0
    counts: Counter[str] = Counter()
    digest = hashlib.sha256()
    seen: set[str] = set()
    try:
        with ZipFile(archive) as bundle:
            members = bundle.infolist()
            if len(members) > audit_settings.FILE_LIMIT:
                raise AuditError("压缩包文件数量超出限制")
            for member in sorted(members, key=lambda item: item.filename):
                name = member.filename
                path = PurePosixPath(name)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or "\\" in name
                    or ":" in name
                ):
                    raise AuditError("压缩包包含不安全的文件路径")
                mode = member.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise AuditError("压缩包不允许符号链接")
                if member.is_dir() or any(part in IGNORED for part in path.parts):
                    continue
                if path.as_posix() in seen:
                    raise AuditError("压缩包包含重复文件路径")
                seen.add(path.as_posix())
                total += member.file_size
                if (
                    total > audit_settings.EXTRACT_LIMIT
                    or member.file_size > 10 * 1024 * 1024
                ):
                    raise AuditError("解压后体积超出限制")
                target = destination.joinpath(*path.parts)
                if not target.resolve().is_relative_to(destination.resolve()):
                    raise AuditError("压缩包路径超出工作区")
                target.parent.mkdir(parents=True, exist_ok=True)
                content = bundle.read(member)
                target.write_bytes(content)
                digest.update(name.encode() + b"\0" + hashlib.sha256(content).digest())
                counts[EXTENSIONS.get(target.suffix.lower(), "other")] += 1
        if not counts[language]:
            raise AuditError("压缩包中没有所选语言的源码")
        return digest.hexdigest(), {
            "files_by_language": dict(counts),
            "selected_language": language,
            "unscanned_languages": [
                key for key in counts if key not in {language, "other"}
            ],
            "extracted_bytes": total,
        }
    except (BadZipFile, OSError, RuntimeError, AuditError) as exc:
        shutil.rmtree(destination, ignore_errors=True)
        if isinstance(exc, AuditError):
            raise
        raise AuditError("压缩包损坏或无法解析") from exc
