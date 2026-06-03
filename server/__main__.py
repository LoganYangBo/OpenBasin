"""``python -m server`` — run the OpenBasin server with uvicorn."""

from __future__ import annotations

import logging

import uvicorn

from server.api import create_app
from server.config import load_config


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = load_config()
    app = create_app(config)
    uvicorn.run(app, host=config.server.host, port=config.server.port)


if __name__ == "__main__":
    main()
