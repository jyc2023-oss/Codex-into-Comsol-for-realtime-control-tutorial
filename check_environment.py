

from __future__ import annotations

import platform
import socket
import sys
import unicodedata
from pathlib import Path


COMSOL_CANDIDATES = [
    Path(r"D:\COMSOL\bin\win64\comsolmphserver.exe"),
    Path(r"D:\COMSOL\Multiphysics\bin\win64\comsolmphserver.exe"),
]


def check_python() -> bool:
    ok = sys.version_info >= (3, 10)
    print(f"[{'OK' if ok else 'FAIL'}] Python version: {platform.python_version()} (>=3.10 required)")
    print(f"     Executable: {sys.executable}")
    return ok


def check_mph() -> bool:
    try:
        import mph  # noqa: F401
    except Exception as exc:
        print(f"[FAIL] mph import: {exc}")
        return False
    print("[OK] mph import succeeded")
    return True


def check_comsol_exe() -> bool:
    existing = [p for p in COMSOL_CANDIDATES if p.exists()]
    if not existing:
        print("[FAIL] comsolmphserver.exe not found in expected paths:")
        for p in COMSOL_CANDIDATES:
            print(f"     - {p}")
        return False
    print(f"[OK] COMSOL server executable found: {existing[0]}")
    return True


def _probe_tcp(host: str, port: int, timeout: float) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def check_port(port: int = 2036) -> bool:
    # Some COMSOL launches bind on IPv6 first. Try both targets to avoid false negatives.
    for host in ("127.0.0.1", "localhost"):
        if _probe_tcp(host, port, 1.5):
            print(f"[OK] TCP {host}:{port} reachable")
            return True
    print(f"[WARN] TCP 127.0.0.1:{port} and localhost:{port} are not reachable (server may not be running).")
    return False


def check_ascii_runtime_path() -> bool:
    text = sys.executable
    is_ascii = all(ord(ch) < 128 for ch in text)
    if is_ascii:
        print("[OK] Python executable path is ASCII-only (recommended for JPype/COMSOL).")
        return True
    normalized = unicodedata.normalize("NFKC", text)
    print("[WARN] Python executable path contains non-ASCII characters:")
    print(f"     {normalized}")
    print("     If you hit JPype/COMSOL DLL errors, move venv to an ASCII-only path.")
    return False


def main() -> int:
    print("[INFO] Checking shared-session prerequisites...")
    ok_python = check_python()
    ok_mph = check_mph()
    ok_comsol = check_comsol_exe()
    check_ascii_runtime_path()
    check_port()

    if ok_python and ok_mph and ok_comsol:
        print("[INFO] Core requirements are satisfied.")
        return 0
    print("[INFO] Core requirements are NOT fully satisfied.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
