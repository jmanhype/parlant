from pathlib import Path
import subprocess
import sys

PACKAGE_NAMES = ("common", "sdk", "server")

status, output = subprocess.getstatusoutput("git rev-parse --show-toplevel")

if status != 0:
    print(output, file=sys.stderr)
    print("error: failed to get repo root", file=sys.stderr)
    exit(1)

REPO_ROOT = Path(output.strip())

for package_name in PACKAGE_NAMES:
    package_dir = REPO_ROOT / package_name

    print(f"Installing {package_dir}...")

    status, output = subprocess.getstatusoutput(f"poetry -C {package_dir} install")

    if status != 0:
        print(output, file=sys.stderr)
        print(f"error: failed to install package: {package_dir}", file=sys.stderr)
        exit(1)
