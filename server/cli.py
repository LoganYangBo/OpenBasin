"""``openbasin`` command-line entrypoint.

Subcommands:
    serve              run the server (default)
    reload             tell a running server to reload pipelines
    gen-key            generate a base64 AES-256 device key
    validate           validate the pipelines in config's pipelines_dir
"""

from __future__ import annotations

import argparse
import base64
import secrets
import sys

from server.config import load_config


def _serve(args: argparse.Namespace) -> int:
    from server import __main__ as runner

    runner.main()
    return 0


def _gen_key(args: argparse.Namespace) -> int:
    print(base64.b64encode(secrets.token_bytes(32)).decode())
    return 0


def _validate(args: argparse.Namespace) -> int:
    from server.pipeline import load_pipelines

    config = load_config(args.config)
    pipelines = load_pipelines(config.server.pipelines_dir)
    if not pipelines:
        print("No valid pipelines found.")
        return 1
    for p in pipelines:
        print(f"  ✓ {p.name}  (trigger: {p.trigger.signal_type}, actions: {len(p.actions)})")
    print(f"{len(pipelines)} pipeline(s) valid.")
    return 0


def _reload(args: argparse.Namespace) -> int:
    import httpx

    config = load_config(args.config)
    token = args.token or (config.devices[0].token if config.devices else "")
    url = args.url or f"http://localhost:{config.server.port}"
    resp = httpx.post(f"{url.rstrip('/')}/v1/reload", headers={"X-Device-Token": token})
    resp.raise_for_status()
    print(resp.json())
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="openbasin")
    parser.add_argument("--config", default="config.yaml", help="path to config.yaml")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("serve", help="run the server").set_defaults(func=_serve)
    sub.add_parser("gen-key", help="generate an AES-256 device key").set_defaults(func=_gen_key)
    sub.add_parser("validate", help="validate pipelines").set_defaults(func=_validate)

    rel = sub.add_parser("reload", help="reload pipelines on a running server")
    rel.add_argument("--url", default="")
    rel.add_argument("--token", default="")
    rel.set_defaults(func=_reload)

    args = parser.parse_args()
    func = getattr(args, "func", _serve)
    sys.exit(func(args))


if __name__ == "__main__":
    main()
