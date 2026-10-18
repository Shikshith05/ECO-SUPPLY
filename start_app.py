"""Unified launcher for the epoch Flask app (uses the .venv created by setup_env.py)."""

import os
import platform
import subprocess
import time
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(ROOT, ".venv")


def is_windows() -> bool:
    return platform.system().lower().startswith("win")


def python_executable() -> str:
    return os.path.join(VENV_DIR, "Scripts", "python.exe") if is_windows() else os.path.join(VENV_DIR, "bin", "python")


def main() -> None:
    py = python_executable()
    if not os.path.exists(py):
        print("No .venv found. Run: python setup_env.py")
        return

    print("Starting Flask backend...")
    proc = subprocess.Popen([py, "backend/app.py"], cwd=ROOT)
    try:
        time.sleep(1.5)
        print("Epoch is running at http://localhost:5000")
        webbrowser.open("http://localhost:5000")
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("Server stopped.")


if __name__ == "__main__":
    main()
