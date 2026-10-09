"""Source categories and scheduling hints; filenames never prove business contracts."""

from pathlib import Path

TEMPLATES = {
    ".ejs",
    ".html",
    ".htm",
    ".jinja",
    ".jinja2",
    ".j2",
    ".pug",
    ".hbs",
    ".handlebars",
    ".vue",
    ".svelte",
}
CONFIG = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".xml"}
BLOCKED_PARTS = {".git", ".venv", "venv", "node_modules", "__pycache__"}
LOCKFILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "uv.lock",
}


def readable_name(file: str) -> bool:
    parts = Path(file).parts
    return not any(
        p.startswith(".env") or ".env" in Path(p).suffixes or p in BLOCKED_PARTS
        for p in parts
    )


def inspectable(file: str, language: str, expanded: bool = True) -> bool:
    path = Path(file)
    code = {".py"} if language == "python" else {".js", ".jsx", ".ts", ".tsx"}
    suffixes = code | TEMPLATES | CONFIG if expanded else code
    return readable_name(file) and path.suffix.lower() in suffixes


def category(file: str) -> str:
    path = Path(file.lower())
    parts = set(path.parts)
    if (
        path.name in LOCKFILES
        or path.name.endswith((".min.js", ".min.css"))
        or parts & {"vendor", "third_party", "third-party", "dist", "build"}
        or path.name == "activate_this.py"
    ):
        return "third_party_or_generated"
    if path.suffix in TEMPLATES:
        return "template"
    if parts & {"routes", "route", "controllers", "api"} or path.stem in {
        "app",
        "server",
        "main",
        "index",
    }:
        return "entrypoint"
    if any(term in path.stem for term in ("auth", "passport", "permission", "session")):
        return "authentication"
    if path.suffix in CONFIG or parts & {"config", "configuration"}:
        return "configuration"
    if parts & {"core", "services", "handlers", "models"} or "handler" in path.stem:
        return "business"
    return "source"


def priority(file: str) -> int:
    return {
        "entrypoint": 0,
        "authentication": 0,
        "business": 1,
        "template": 2,
        "configuration": 3,
        "source": 4,
        "third_party_or_generated": 9,
    }[category(file)]


def inspection_tasks(role: str, semantic: bool = False) -> list[dict]:
    tasks = {
        "authentication": "Trace entrypoint authentication and public/sensitive route boundaries; upstream guards need source evidence.",
        "authorization": "Distinguish logged-in from role/permission checks on sensitive operations; verify the intended contract.",
        "object_ownership": "Trace request object IDs to reads/writes and compare with user/tenant identity, including guard call sites.",
        "input_injection": "Trace untrusted input to actual bound operations; verify validation/sanitization and custom wrappers.",
        "output_encoding": "Trace data to HTML/template/DOM output and verify context-specific escaping, including template expressions.",
        "state_integrity": "Inspect state changes, CSRF/session/reset-token controls and state transition safety.",
        "secrets_config": "Inspect committed secrets, credential handling, debug flags and security-relevant configuration.",
        "audit_abuse": "Inspect login/rate limiting and security-event logging; check upstream controls before alleging absence.",
    }
    selected = {
        "configuration": ["secrets_config", "state_integrity", "audit_abuse"],
        "template": [
            "output_encoding",
            "input_injection",
            "state_integrity",
            "authorization",
        ],
        "third_party_or_generated": ["input_injection", "output_encoding"],
    }.get(role, list(tasks))
    if semantic:
        tasks["rate_limiting"] = (
            "Inspect attempt limits/lockout on actual authentication endpoints, including app-level middleware. Separate from logging."
        )
        tasks["security_logging"] = (
            "Inspect whether authentication successes/failures are recorded as security events, distinguish flash/UI messages from event logs. Separate from throttling."
        )
        selected = [key for key in selected if key != "audit_abuse"] + (
            ["rate_limiting", "security_logging"] if "audit_abuse" in selected else []
        )
        tasks["state_integrity"] += (
            " Check state-changing GET routes (logout, update), not only POST forms."
        )
        tasks["authentication"] += (
            " Enumerate every sensitive route separately; do not bundle missing guards under an injection finding."
        )
    return [{"id": key, "instruction": tasks[key]} for key in selected]
