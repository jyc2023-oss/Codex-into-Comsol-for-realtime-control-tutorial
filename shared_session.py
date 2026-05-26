from __future__ import annotations

import argparse
import getpass
from pathlib import Path

import mph


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Connect to a running COMSOL Server shared session and operate on the active model."
    )
    parser.add_argument("--host", default="localhost", help="COMSOL server host")
    parser.add_argument("--port", type=int, default=2036, help="COMSOL server port")
    parser.add_argument("--version", default="6.4", help="COMSOL version, e.g. 6.4")
    parser.add_argument("--user", help="Server login user (optional)")
    parser.add_argument("--password", help="Server login password (optional)")
    parser.add_argument(
        "--model-index",
        type=int,
        default=0,
        help="Index in client.models() list to target (default: 0)",
    )
    parser.add_argument(
        "--set-param",
        metavar=("NAME", "VALUE"),
        nargs=2,
        help='Set model parameter, e.g. --set-param r "3[mm]"',
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Run model.build() after parameter update",
    )
    parser.add_argument(
        "--solve",
        action="store_true",
        help="Run model.solve() after build/update",
    )
    parser.add_argument(
        "--save-as",
        type=Path,
        help="Optional save path. Prefer GUI save for shared-session workflow.",
    )
    parser.add_argument(
        "--remove-after-save",
        action="store_true",
        help="Remove model from server after save to reduce lock risks.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client: mph.Client | None = None

    try:
        print(f"[INFO] Connecting to COMSOL server {args.host}:{args.port} (version={args.version})")
        if args.user:
            password = args.password
            if password is None:
                password = getpass.getpass("COMSOL password: ")
            client = mph.Client(version=args.version, host=None)
            client.java.connect(args.host, args.port, False, args.user, password)
            client.host = args.host
            client.port = args.port
        else:
            # Prefer mph default connect flow, which can reuse locally stored
            # COMSOL login info created by server login modes like "-login auto".
            client = mph.Client(version=args.version, host=args.host, port=args.port)
        models = client.models()

        if not models:
            print("[ERROR] No models are currently open on server.")
            print("        Open a model in COMSOL GUI first, then rerun this script.")
            return 2

        if args.model_index < 0 or args.model_index >= len(models):
            print(f"[ERROR] model-index {args.model_index} out of range (0..{len(models)-1}).")
            return 2

        print("[INFO] Models currently attached to server:")
        for i, m in enumerate(models):
            print(f"  [{i}] {m.name()}")

        model = models[args.model_index]
        print(f"[INFO] Target model: {model.name()}")

        if args.set_param:
            name, value = args.set_param
            model.parameter(name, value)
            print(f"[INFO] Set parameter {name} = {value}")

        if args.build:
            model.build()
            print("[INFO] Geometry/build completed.")

        if args.solve:
            model.solve()
            print("[INFO] Solve completed.")

        if args.save_as:
            save_path = args.save_as.expanduser().resolve()
            model.save(str(save_path))
            print(f"[INFO] Saved model to: {save_path}")
            if args.remove_after_save:
                client.remove(model)
                print("[INFO] Removed model from server after save.")

        print("[INFO] Done.")
        return 0
    finally:
        if client is not None:
            try:
                client.disconnect()
                print("[INFO] Disconnected from COMSOL server.")
            except Exception:
                pass


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] {exc}")
        print("[HINT] If server requires login, retry with: --user <name> --password <pwd>")
        raise
