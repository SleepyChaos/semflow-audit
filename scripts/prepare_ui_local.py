"""Configure only the independent UI checkout; never print private values."""
from pathlib import Path
import re
import socket
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]


def build_local_config(text: str, root: Path, postgres_port: int, redis_port: int) -> str:
    if root.resolve().name != "semflow-audit-ui":
        raise ValueError("This initializer only supports the independent UI checkout.")
    values = {}
    for line in text.splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    database = urlsplit(values.get("DATABASE_URL", ""))
    if "@" not in database.netloc:
        raise ValueError("A local database credential must already be configured.")
    credentials = database.netloc.rsplit("@", 1)[0]
    updates = {
        "DATABASE_URL": urlunsplit((database.scheme, f"{credentials}@127.0.0.1:{postgres_port}", "/audit", "", "")),
        "REDIS_URL": f"redis://127.0.0.1:{redis_port}/0",
        "FRONTEND_HOST": "http://127.0.0.1:5174",
        "ARTIFACT_ROOT": (root / "artifacts").as_posix(),
        "CODEQL_PACK_PATH": (root / "artifacts/packs").as_posix(),
        "CODEQL_BIN": (root / ".tools/codeql/codeql.exe").as_posix(),
        "UI_DB_PORT": str(postgres_port),
        "UI_REDIS_PORT": str(redis_port),
        "UI_CONFIGURED": "1",
    }
    python_bin = values.get("CODEQL_PYTHON_BIN", "")
    if "semflow-audit/" in python_bin.replace("\\", "/"):
        updates["CODEQL_PYTHON_BIN"] = (root / ".venv/Scripts/python.exe").as_posix()
    for key, value in updates.items():
        pattern = re.compile(r"^" + re.escape(key) + r"=.*$", re.MULTILINE)
        if pattern.search(text):
            text = pattern.sub(lambda _: f"{key}={value}", text)
        else:
            text = text.rstrip() + f"\n{key}={value}\n"
    return text.rstrip() + "\n"


def choose_port(preferred: int) -> int:
    for port in range(preferred, preferred + 60):
        with socket.socket() as server:
            try:
                server.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No available port in the configured range.")


def main():
    env_path = ROOT / ".env"
    original = env_path.read_text(encoding="utf-8-sig")
    if re.search(r"^UI_CONFIGURED=1$", original, re.MULTILINE):
        print("Independent runtime configuration already exists.")
        return
    pg, redis = choose_port(15440), choose_port(16380)
    result = build_local_config(original, ROOT, pg, redis)
    env_path.write_text(result, encoding="utf-8")
    print(f"Configured independent runtime: frontend 5174, API 8001, database {pg}, Redis {redis}.")


if __name__ == "__main__":
    main()
