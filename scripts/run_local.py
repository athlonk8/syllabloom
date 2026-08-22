#!/usr/bin/env python3
"""Build and run Syllabloom from a single terminal command."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
VENV_DIR = PROJECT_ROOT / ".venv"


def _venv_python() -> Path:
    return VENV_DIR / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(command: list[str], *, cwd: Path) -> None:
    print("$", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def _require_command(name: str, guidance: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(guidance)
    return path


def ensure_python_dependencies() -> Path:
    if sys.version_info < (3, 11):
        raise RuntimeError("Python 3.11 or newer is required. Install it, then run this command again.")
    python = _venv_python()
    if not python.is_file():
        _run([sys.executable, "-m", "venv", str(VENV_DIR)], cwd=PROJECT_ROOT)
    requirements = BACKEND_DIR / "requirements.txt"
    marker = VENV_DIR / ".palo-requirements.sha256"
    digest = _digest(requirements)
    if not marker.is_file() or marker.read_text(encoding="utf-8") != digest:
        _run([str(python), "-m", "pip", "install", "--upgrade", "pip"], cwd=PROJECT_ROOT)
        _run([str(python), "-m", "pip", "install", "-r", str(requirements)], cwd=PROJECT_ROOT)
        marker.write_text(digest, encoding="utf-8")
    return python


def ensure_frontend() -> None:
    npm = _require_command("npm", "Node.js 20 or newer is required. Install Node.js, then run this command again.")
    lockfile = FRONTEND_DIR / "package-lock.json"
    marker = FRONTEND_DIR / ".palo-node-lock.sha256"
    digest = _digest(lockfile)
    if not (FRONTEND_DIR / "node_modules").is_dir() or not marker.is_file() or marker.read_text(encoding="utf-8") != digest:
        _run([npm, "ci"], cwd=FRONTEND_DIR)
        marker.write_text(digest, encoding="utf-8")
    _run([npm, "run", "build"], cwd=FRONTEND_DIR)


def wait_for_server(url: str, process: subprocess.Popen[object]) -> bool:
    for _ in range(60):
        if process.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=1) as response:
                if response.status == 200:
                    return True
        except OSError:
            time.sleep(0.5)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and run the local Syllabloom web app.")
    parser.add_argument("--port", type=int, default=8000, help="Local HTTP port (default: 8000).")
    parser.add_argument("--host", default="127.0.0.1", help="Local bind address (default: 127.0.0.1).")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically.")
    parser.add_argument("--reload", action="store_true", help="Enable backend reload for contributors.")
    parser.add_argument("--skip-install", action="store_true", help="Skip dependency installation checks.")
    args = parser.parse_args()

    try:
        python = _venv_python() if args.skip_install else ensure_python_dependencies()
        if not python.is_file():
            raise RuntimeError("Local Python environment is missing. Run again without --skip-install.")
        ensure_frontend()
        _run([str(python), "-m", "app.migrations"], cwd=BACKEND_DIR)
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Startup preparation failed: {exc}", file=sys.stderr)
        return 1

    url = f"http://{args.host}:{args.port}"
    environment = os.environ.copy()
    environment["SYLLABLOOM_FRONTEND_DIST"] = str(FRONTEND_DIR / "dist")
    command = [str(python), "-m", "uvicorn", "app.main:app", "--host", args.host, "--port", str(args.port)]
    if args.reload:
        command.append("--reload")
    print(f"Starting Syllabloom at {url}", flush=True)
    process = subprocess.Popen(command, cwd=BACKEND_DIR, env=environment)

    if not args.no_browser:
        def open_when_ready() -> None:
            if wait_for_server(url, process):
                webbrowser.open(url)
            else:
                print("The server stopped before it became ready.", file=sys.stderr)

        threading.Thread(target=open_when_ready, daemon=True).start()

    try:
        return process.wait()
    except KeyboardInterrupt:
        print("\nStopping Syllabloom…", flush=True)
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
