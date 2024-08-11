import subprocess

def init():
    subprocess.run(["git", "config", "core.hooksPath", ".githooks"], check=True)

if __name__ == "__main__":
    init()
