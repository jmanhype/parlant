import os
from pathlib import Path
import subprocess
import sys

PACKAGE_NAMES = ("common", "sdk", "server")

status, output = subprocess.getstatusoutput("git rev-parse --show-toplevel")

if status != 0:
    print(output, file=sys.stderr)
    print("error: failed to get repo root", file=sys.stderr)
    exit(1)

REPO_ROOT = Path(output.strip()).absolute()

for package_name in PACKAGE_NAMES:
    os.chdir(REPO_ROOT)

    package_dir = REPO_ROOT / package_name

    print(f"Running MyPy on {package_dir}...")

    os.chdir(package_dir)

    status, output = subprocess.getstatusoutput("poetry run mypy")

    if status != 0:
        print(output, file=sys.stderr)
        print(f"error: MyPy check failed on package: {package_dir}", file=sys.stderr)
        exit(1)