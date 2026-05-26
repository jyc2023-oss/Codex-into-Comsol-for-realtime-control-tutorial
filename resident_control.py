from __future__ import annotations

import argparse
import shlex
from pathlib import Path

import mph


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Persistent COMSOL control shell (single long-lived connection)."
    )
    parser.add_argument("--host", default="localhost", help="COMSOL server host")
    parser.add_argument("--port", type=int, default=2036, help="COMSOL server port")
    parser.add_argument("--version", default="6.4", help="COMSOL version")
    parser.add_argument(
        "--model-index",
        type=int,
        default=0,
        help="Default target model index at startup",
    )
    return parser.parse_args()


def print_help() -> None:
    print(
        "\n".join(
            [
                "Commands:",
                "  help                           Show this help",
                "  models                         List models on server",
                "  use <index>                    Switch active model by index",
                "  params [keyword]               Show parameters (optionally filter by keyword)",
                "  set <name> <value>             Set parameter, e.g. set OD 17[mm]",
                "  build                          Run model.build()",
                "  solve                          Run model.solve()",
                "  save <path>                    Save model to a new path",
                "  eval <expr> [unit]             Evaluate expression, e.g. eval mf.normB",
                "  studies                        List studies",
                "  plots                          List plots",
                "  exit | quit                    Exit shell",
            ]
        )
    )


def select_model(client: mph.Client, index: int) -> mph.Model:
    models = client.models()
    if not models:
        raise RuntimeError("No models are currently open on server.")
    if index < 0 or index >= len(models):
        raise IndexError(f"model index {index} out of range (0..{len(models)-1})")
    return models[index]


def list_models(client: mph.Client) -> list[mph.Model]:
    models = client.models()
    if not models:
        print("[INFO] No models currently attached to server.")
        return models
    print("[INFO] Models:")
    for i, m in enumerate(models):
        print(f"  [{i}] {m.name()}")
    return models


def main() -> int:
    args = parse_args()
    client: mph.Client | None = None
    print(f"[INFO] Connecting to COMSOL server {args.host}:{args.port} (version={args.version})")
    try:
        try:
            client = mph.Client(version=args.version, host=args.host, port=args.port)
        except Exception as exc:
            text = str(exc)
            print(f"[ERROR] {exc}")
            if "Server is in use by another client" in text:
                print("[HINT] Current COMSOL server is single-client occupied.")
                print("[HINT] Restart server with multi-client mode: -multi on")
                print("[HINT] Then reconnect GUI and this shell to the same port.")
            return 2

        active_index = args.model_index
        active_model = select_model(client, active_index)
        print(f"[INFO] Connected. Active model: [{active_index}] {active_model.name()}")
        print("[INFO] Type 'help' for commands.")

        while True:
            try:
                line = input("comsol> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[INFO] Exiting.")
                return 0

            if not line:
                continue

            try:
                parts = shlex.split(line)
                cmd = parts[0].lower()

                if cmd in ("exit", "quit"):
                    print("[INFO] Bye.")
                    return 0

                if cmd == "help":
                    print_help()
                    continue

                if cmd == "models":
                    list_models(client)
                    continue

                if cmd == "use":
                    if len(parts) != 2:
                        print("[ERROR] Usage: use <index>")
                        continue
                    active_index = int(parts[1])
                    active_model = select_model(client, active_index)
                    print(f"[INFO] Active model: [{active_index}] {active_model.name()}")
                    continue

                if cmd == "params":
                    keyword = parts[1] if len(parts) > 1 else None
                    params = active_model.parameters()
                    keys = sorted(params.keys())
                    if keyword:
                        keys = [k for k in keys if keyword.lower() in k.lower()]
                    if not keys:
                        print("[INFO] No matching parameters.")
                        continue
                    for k in keys:
                        print(f"{k} = {params[k]}")
                    continue

                if cmd == "set":
                    if len(parts) < 3:
                        print("[ERROR] Usage: set <name> <value>")
                        continue
                    name = parts[1]
                    value = " ".join(parts[2:])
                    active_model.parameter(name, value)
                    print(f"[INFO] Set {name} = {value}")
                    continue

                if cmd == "build":
                    active_model.build()
                    print("[INFO] Build done.")
                    continue

                if cmd == "solve":
                    active_model.solve()
                    print("[INFO] Solve done.")
                    continue

                if cmd == "save":
                    if len(parts) != 2:
                        print("[ERROR] Usage: save <path>")
                        continue
                    save_path = Path(parts[1]).expanduser().resolve()
                    active_model.save(str(save_path))
                    print(f"[INFO] Saved to: {save_path}")
                    continue

                if cmd == "eval":
                    if len(parts) < 2:
                        print("[ERROR] Usage: eval <expr> [unit]")
                        continue
                    expr = parts[1]
                    unit = parts[2] if len(parts) >= 3 else None
                    value = active_model.evaluate(expr, unit) if unit else active_model.evaluate(expr)
                    print(f"[INFO] eval {expr} => {value}")
                    continue

                if cmd == "studies":
                    print(active_model.studies())
                    continue

                if cmd == "plots":
                    print(active_model.plots())
                    continue

                print(f"[ERROR] Unknown command: {cmd}")
            except Exception as exc:
                print(f"[ERROR] {exc}")
    finally:
        if client is not None:
            try:
                client.disconnect()
                print("[INFO] Disconnected from COMSOL server.")
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
