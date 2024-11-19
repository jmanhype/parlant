#!python

import os
from pathlib import Path
import re
import subprocess
import shutil
import time

_CHECKLIST = """
1. Start a server from the latest `develop`.
   - Navigate to the the parlant directory and run `just server` or `poetry run parlant-server`
2. Update `fern/openapi/parlant.openapi.json`.
   - From the root directory of this repo: `curl -o fern/openapi/parlant.openapi.json http://localhost:8000/openapi.json`
   - Alternatively, open the server and navigate to `/openapi.json`, download it, rename to `parlant.openapi.json` and move to the `fern/openapi.
"""

DIR_SCRIPT_ROOT = Path(".")
DIR_FERN = DIR_SCRIPT_ROOT / "fern"
DIR_SDKS = DIR_SCRIPT_ROOT / "sdks"
DIR_PROJECTS_WORKSPACE = Path("../..")


PATHDICT_SDK_REPO_TARGETS = dict(
    [
        (
            "python",
            DIR_PROJECTS_WORKSPACE / "parlant-client-python" / "src" / "parlant" / "client",
        ),
        (
            "typescript",
            DIR_PROJECTS_WORKSPACE / "parlant-client-typescript" / "src",
        ),
    ]
)


def replace_in_files(rootdir: Path, search: str, replace: str) -> None:
    rewrites: dict[str, str] = {}
    for subdir, _dirs, files in os.walk(rootdir):
        for file in files:
            file_path = os.path.join(subdir, file)

            with open(file_path, "r") as current_file:
                current_file_content = current_file.read()
                if "from parlant import" not in current_file_content:
                    continue

                current_file_content = re.sub(search, replace, current_file_content)
                rewrites[file_path] = current_file_content

    for path, content in rewrites.items():
        with open(path, "w") as current_file:
            current_file.write(content)


if __name__ == "__main__":
    print(_CHECKLIST)
    print("---")
    for sdk, repo in PATHDICT_SDK_REPO_TARGETS.items():
        if os.path.isdir(repo):
            continue

        raise Exception(f"Missing dir for {sdk}: {repo}")

    input("Press any key to continue...")
    print("\n")
    cwd = os.getcwd()
    if not os.path.isdir(cwd + "/fern"):
        if "mc-spitfyte" not in cwd:
            raise Exception(
                "fern directory not found, you should probably be in the mc-spitfyre repo root"
            )
        raise Exception("try `git reset --hard origin/master` or call for help")
    for sdk in PATHDICT_SDK_REPO_TARGETS:
        sdk_path = DIR_SDKS / sdk
        if not os.path.isdir(sdk_path):
            continue

        print(f"Deleting old {sdk} sdk")
        print(f"> rm -rf {sdk_path}")
        shutil.rmtree(sdk_path)

    print("Invoking fern generation")
    print("> fern generate --log-level=debug")
    exit_code, generate_output = subprocess.getstatusoutput("fern generate --log-level=debug")
    with open("fern.generate.log", "w") as fern_log:
        fern_log.write(generate_output)
    if exit_code != os.EX_OK:
        raise Exception(generate_output)

    print("Renaming `parlant` to `parlant.client` in python imports")
    replace_in_files(DIR_SDKS / "python", "from parlant import", "from parlant.client import")

    print("touching python typing")

    print(f"> touch {DIR_SDKS}/python/py.typed")
    open(DIR_SDKS / "python/py.typed", "w")

    for sdk, repo in PATHDICT_SDK_REPO_TARGETS.items():
        print(f"!DANGER! Deleting local `{repo}` directory and all of its contents!")
        time.sleep(3)
        print(f"> rm -rf {repo}")
        shutil.rmtree(repo)

    for sdk, repo in PATHDICT_SDK_REPO_TARGETS.items():
        print(f"copying newly generated {sdk} files to {repo}")
        print(f"> cp -rp {DIR_SDKS}/{sdk} {repo}")
        shutil.copytree(DIR_SDKS / sdk, repo)
