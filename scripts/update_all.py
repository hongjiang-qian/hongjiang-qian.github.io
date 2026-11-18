import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(name: str):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / name)],
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main():
    run("update_conferences.py")
    run("update_funding.py")
    run("generate_pages.py")


if __name__ == "__main__":
    main()
