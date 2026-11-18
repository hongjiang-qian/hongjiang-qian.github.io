"""Update conference/funding data and regenerate the two public pages."""
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def run(script: str) -> None:
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / script)], cwd=str(ROOT))
    if result.returncode != 0:
        raise SystemExit(result.returncode)

def main() -> None:
    run("update_conferences.py")
    run("update_funding.py")
    run("generate_pages.py")

if __name__ == "__main__":
    main()
