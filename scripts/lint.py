import sys
from functools import partial

from utils import Package, die, for_each_package


def run_cmd_or_die(
    cmd: str,
    description: str,
    package: Package,
) -> None:
    print(f"Running {cmd} on {package.name}...")

    status, output = package.run_cmd(cmd)

    if status != 0:
        print(output, file=sys.stderr)
        die(f"error: package '{package.path}': {description}")


def lint_package(mypy: bool, ruff: bool, package: Package) -> None:
    if mypy:
        run_cmd_or_die("mypy", "Please fix MyPy lint errors", package)
    if ruff:
        run_cmd_or_die("ruff check", "Please fix Ruff lint errors", package)
        run_cmd_or_die("ruff format --check", "Please format files with Ruff", package)


if __name__ == "__main__":
    mypy = "--mypy" in sys.argv
    ruff = "--ruff" in sys.argv

    for_each_package(partial(lint_package, mypy, ruff))
