from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pathlib import Path

import uvicorn

from .bot import TelegramBridgeService
from .config_store import ConfigStore
from .models import BridgeConfig
from .providers.codex_cli import CodexCLIProvider
from .runtime import BridgeRuntime
from .web import build_app


def build_paths(data_dir: str | None) -> Path:
    if data_dir:
        return Path(data_dir).expanduser()
    return Path.cwd() / ".bridge_data"


def provider_factory(config: BridgeConfig) -> CodexCLIProvider:
    return CodexCLIProvider(config)


async def run_server(host: str, port: int, data_dir: str | None) -> None:
    base_dir = build_paths(data_dir)
    config_store = ConfigStore(base_dir)
    runtime = BridgeRuntime(config_store=config_store, provider_factory=provider_factory)
    bot_service = TelegramBridgeService(config_store=config_store, runtime=runtime, provider_factory=provider_factory)
    await bot_service.start_if_configured()
    app = build_app(config_store=config_store, bot_service=bot_service, provider_factory=provider_factory)
    server = uvicorn.Server(
        uvicorn.Config(
            app=app,
            host=host,
            port=port,
            log_level="info",
        )
    )
    try:
        await server.serve()
    finally:
        await bot_service.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Codex Telegram Bridge")
    parser.add_argument("serve", nargs="?", default="serve")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", default=os.getenv("CTB_DATA_DIR"))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(run_server(args.host, args.port, args.data_dir))


if __name__ == "__main__":
    main()
