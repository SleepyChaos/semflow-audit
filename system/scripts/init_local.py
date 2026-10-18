"""Create local credentials once; never print passwords or overwrite settings."""

import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[2]
path = root / ".env"
if path.exists():
    print(".env already exists; preserved")
else:
    password = secrets.token_hex(24)
    template = (root / "system/.env.example").read_text(encoding="utf-8")
    path.write_text(
        template.replace("POSTGRES_PASSWORD=\n", f"POSTGRES_PASSWORD={password}\n")
        .replace("YOUR_PASSWORD", password),
        encoding="utf-8",
        newline="\n",
    )
    path.chmod(0o600)
    print("Created .env with random local credentials")
