"""One-command setup: create .venv (Python 3.11), install requirements, create config.

Usage:
    python setup_env.py              # create .venv if missing, install deps, create config
    python setup_env.py --recreate   # wipe and rebuild .venv (e.g. it was made with Python 3.13)

The pinned pandas / numpy / scikit-learn versions have no wheels for Python 3.13,
so the virtual environment must be built with Python 3.11. On Windows the
`py -3.11` launcher is used to find it if this script runs under another version.
"""

import os
import platform
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(ROOT, ".venv")
CONFIG_PATH = os.path.join(ROOT, "config", "config.yaml")
CONFIG_EXAMPLE = os.path.join(ROOT, "config", "config.yaml.example")
REQUIRED = (3, 11)


def is_windows() -> bool:
    return platform.system().lower().startswith("win")


def venv_python() -> str:
    if is_windows():
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    return os.path.join(VENV_DIR, "bin", "python")


def venv_version() -> tuple | None:
    """Return (major, minor) of the existing .venv interpreter, or None."""
    cfg = os.path.join(VENV_DIR, "pyvenv.cfg")
    if not os.path.exists(cfg):
        return None
    with open(cfg, encoding="utf-8") as f:
        for line in f:
            key, _, value = line.partition("=")
            if key.strip() in ("version", "version_info"):
                parts = value.strip().split(".")
                return int(parts[0]), int(parts[1])
    return None


def base_python_command() -> list:
    """Find a Python 3.11 interpreter to build the venv with."""
    if sys.version_info[:2] == REQUIRED:
        return [sys.executable]
    if is_windows() and shutil.which("py"):
        probe = subprocess.run(["py", "-3.11", "-c", "import sys"], capture_output=True)
        if probe.returncode == 0:
            return ["py", "-3.11"]
    for name in ("python3.11", "python3.11.exe"):
        path = shutil.which(name)
        if path:
            return [path]
    sys.exit(
        "Python 3.11 was not found. Install it (https://www.python.org/downloads/) "
        "and re-run this script; the pinned dependencies do not support 3.13."
    )


def ensure_venv(recreate: bool) -> None:
    version = venv_version()
    if version is not None and version != REQUIRED and not recreate:
        sys.exit(
            f".venv exists but was built with Python {version[0]}.{version[1]}; "
            "re-run with --recreate to rebuild it with Python 3.11."
        )
    if version == REQUIRED and not recreate:
        print(f"[1/4] Using existing .venv (Python {version[0]}.{version[1]})")
        return
    cmd = base_python_command() + ["-m", "venv"]
    if recreate and os.path.exists(VENV_DIR):
        cmd.append("--clear")
    cmd.append(VENV_DIR)
    print(f"[1/4] Creating .venv with: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=ROOT, check=True)


def install_requirements() -> None:
    py = venv_python()
    print("[2/4] Installing dependencies from requirements.txt ...")
    subprocess.run([py, "-m", "pip", "install", "--upgrade", "pip"], cwd=ROOT, check=True)
    subprocess.run([py, "-m", "pip", "install", "-r", "requirements.txt"], cwd=ROOT, check=True)


def ensure_config() -> None:
    if os.path.exists(CONFIG_PATH):
        print("[3/4] config/config.yaml already exists (left unchanged)")
        return
    shutil.copyfile(CONFIG_EXAMPLE, CONFIG_PATH)
    print("[3/4] Created config/config.yaml from config/config.yaml.example")


def main() -> None:
    recreate = "--recreate" in sys.argv[1:]
    ensure_venv(recreate)
    install_requirements()
    ensure_config()
    print("[4/4] Setup complete.")
    print("      Dataset: put DataCoSupplyChainDataset.csv in data/raw/ (see README).")
    print("      Start the app: python start_app.py")
    if os.path.isdir(os.path.join(ROOT, "venv")):
        print("      Note: an old 'venv' folder exists and is no longer used; you can delete it.")


if __name__ == "__main__":
    main()
