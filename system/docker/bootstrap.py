"""Ordered repeatable database bootstrap. Failures keep application services down."""

import subprocess


def main():
    for command in [
        ["alembic", "upgrade", "head"],
        ["python", "-m", "app.initial_data"],
        ["python", "-m", "app.jobs.bootstrap"],
        ["python", "/app/system/docker/seed_knowledge.py"],
    ]:
        print("Bootstrap: " + " ".join(command), flush=True)
        subprocess.run(command, check=True)
    print("SemFlow database and RAG bootstrap complete", flush=True)


if __name__ == "__main__":
    main()
