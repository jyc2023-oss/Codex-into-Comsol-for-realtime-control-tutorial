from __future__ import annotations

import argparse
import socket
import time


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Lightweight COMSOL shared-session health check."
    )
    parser.add_argument("--host", default="localhost", help="COMSOL server host")
    parser.add_argument("--port", type=int, default=2036, help="COMSOL server port")
    parser.add_argument("--version", default="6.4", help="COMSOL version")
    parser.add_argument(
        "--max-connect-seconds",
        type=float,
        default=15.0,
        help="Maximum allowed mph.Client connect latency before marking unhealthy.",
    )
    parser.add_argument(
        "--tcp-timeout-seconds",
        type=float,
        default=2.0,
        help="Socket timeout used for quick TCP reachability probe.",
    )
    return parser.parse_args()


def tcp_reachable(host: str, port: int, timeout_seconds: float) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout_seconds)
    try:
        sock.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def main() -> int:
    args = parse_args()

    if not tcp_reachable(args.host, args.port, args.tcp_timeout_seconds):
        print(f"[FAIL] TCP {args.host}:{args.port} unreachable.")
        return 2

    try:
        import mph  # local import so import failures are reported cleanly
    except Exception as exc:
        print(f"[FAIL] mph import failed: {exc}")
        return 3

    client = None
    t0 = time.perf_counter()
    try:
        client = mph.Client(version=args.version, host=args.host, port=args.port)
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        print(f"[FAIL] mph.Client connect failed after {elapsed:.2f}s: {exc}")
        return 4

    connect_elapsed = time.perf_counter() - t0
    try:
        models_t0 = time.perf_counter()
        model_count = len(client.models())
        models_elapsed = time.perf_counter() - models_t0
    except Exception as exc:
        print(f"[FAIL] client.models() failed: {exc}")
        try:
            client.disconnect()
        except Exception:
            pass
        return 5

    try:
        disconnect_t0 = time.perf_counter()
        client.disconnect()
        disconnect_elapsed = time.perf_counter() - disconnect_t0
    except Exception as exc:
        print(f"[FAIL] disconnect failed: {exc}")
        return 6

    if connect_elapsed > args.max_connect_seconds:
        print(
            f"[FAIL] API connect too slow: {connect_elapsed:.2f}s > {args.max_connect_seconds:.2f}s "
            f"(models={model_count}, models_call={models_elapsed:.2f}s, disconnect={disconnect_elapsed:.2f}s)"
        )
        return 7

    print(
        f"[OK] API healthy: connect={connect_elapsed:.2f}s, models={models_elapsed:.2f}s, "
        f"disconnect={disconnect_elapsed:.2f}s, open_models={model_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
