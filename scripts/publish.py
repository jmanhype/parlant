#!/usr/bin/python3
import sys
import subprocess
import toml  # type: ignore
from utils import die, for_each_package, Package, get_packages


def get_server_version() -> str:
    server_package = next(p for p in get_packages() if p.name == "server")
    project_file = server_package.path / "pyproject.toml"
    pyproject = toml.load(project_file)
    version = str(pyproject["tool"]["poetry"]["version"])
    return version


def publish_docker() -> None:
    version = get_server_version()

    build_process = subprocess.Popen(
        args=["docker", "build", "-t", version, ".", "-f", "Dockerfile.server"],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    status = build_process.wait()

    if status != 0:
        die("error: docker build failed")


def publish_package(package: Package) -> None:
    if not package.uses_poetry or not package.publish:
        print(f"Skipping {package.path}...")
        return

    status, output = package.run_cmd("poetry build")

    if status != 0:
        print(output, file=sys.stderr)
        die(f"error: package '{package.path}': build failed")

    status, output = package.run_cmd("poetry publish")

    if status != 0:
        print(output, file=sys.stderr)
        die(f"error: package '{package.path}': publish failed")


if __name__ == "__main__":
    publish_docker()
    for_each_package(publish_package)
