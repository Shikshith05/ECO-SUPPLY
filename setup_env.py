"""Create the local venv and install project dependencies."""

import os
import platform
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(ROOT, "venv")


def is_windows() -> bool:
    return platform.system().lower().startswith("win")


def main() -> None:
    print("[1/4] Checking for an existing virtual environment...")
    if os.path.exists(VENV_DIR):
        print(f"Virtual environment found at {VENV_DIR}")
    else:
        print("Virtual environment not found. Creating venv/ ...")
        subprocess.run([sys.executable, "-m", "venv", "venv"], cwd=ROOT, check=True)
        print("Virtual environment created.")

    pip_path = os.path.join(VENV_DIR, "Scripts", "pip") if is_windows() else os.path.join(VENV_DIR, "bin", "pip")
    print("[2/4] Installing dependencies from requirements.txt...")
    subprocess.run([pip_path, "install", "-r", "requirements.txt"], cwd=ROOT, check=True)

    print("[3/4] Dependency installation completed.")
    print("[4/4] Setup complete. Now run: python start_app.py")


if __name__ == "__main__":
    main()
