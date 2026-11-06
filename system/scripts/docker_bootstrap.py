"""Initialize persistent schemas before the API and worker start."""

import subprocess
import sys


def main() -> None:
    commands = (
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        [sys.executable, "-m", "app.initial_data"],
        [sys.executable, "-m", "app.jobs.bootstrap"],
    )
    for command in commands:
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
