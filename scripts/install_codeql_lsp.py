"""Install a pinned QLCoder author client with locked npm dependencies."""

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "a33ea82bba156dc8352a0ecd85baff34cbb950ed"
TARGET = ROOT / "artifacts/codeql-lsp-mcp"


def main():
    if not TARGET.exists():
        subprocess.run(
            [
                "git",
                "clone",
                "https://github.com/neuralprogram/codeql-lsp-mcp",
                str(TARGET),
            ],
            check=True,
        )
    subprocess.run(["git", "checkout", "--detach", COMMIT], cwd=TARGET, check=True)
    for name in ("package.json", "package-lock.json"):
        shutil.copyfile(ROOT / "scripts/tools/codeql-lsp" / name, TARGET / name)
    subprocess.run(["npm", "ci", "--ignore-scripts"], cwd=TARGET, check=True)
    # Author's node resolution setting fails against locked protocol package exports.
    subprocess.run(
        ["./node_modules/.bin/tsc", "--moduleResolution", "bundler"],
        cwd=TARGET,
        check=True,
    )


if __name__ == "__main__":
    main()
