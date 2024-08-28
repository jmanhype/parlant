#!/usr/bin/python3
import sys
from utils import die, for_each_package, Package


def publish_package(package: Package) -> None:
    if not package.uses_poetry or not package.publish:
        print(f"Skipping {package.path}...")
        return

    status, output = package.run_cmd("poetry publish --build")

    if status != 0:
        print(output, file=sys.stderr)
        die(f"error: package '{package.path}': publish failed")


if __name__ == "__main__":
    for_each_package(publish_package)
