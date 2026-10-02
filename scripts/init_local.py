"""Create local credentials once; never print passwords or overwrite settings."""

from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
path = root / ".env"
if path.exists():
    print(".env already exists; preserved")
else:
    password = secrets.token_hex(24)
    path.write_text(
        "PROJECT_NAME=AI Code Audit\nFASTAPI_ENV=development\n"
        f"SECRET_KEY={secrets.token_urlsafe(48)}\nPOSTGRES_PASSWORD={password}\n"
        f"DATABASE_URL=postgresql+psycopg://audit:{password}@127.0.0.1:55439/audit\n"
        "FRONTEND_HOST=http://localhost:5173\nFIRST_SUPERUSER=admin@example.com\n"
        f"FIRST_SUPERUSER_PASSWORD={secrets.token_urlsafe(24)}\n"
        "REDIS_URL=redis://127.0.0.1:6389/0\n"
    )
    path.chmod(0o600)
    print("Created .env with random local credentials")
