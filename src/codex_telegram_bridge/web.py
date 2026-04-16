from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .bot import TelegramBridgeService
from .config_store import ConfigStore
from .models import BridgeConfig, BridgeSecrets
from .provider_base import AgentProvider
from .templates import TEMPLATE_PRESETS


class ConfigPayload(BaseModel):
    config: BridgeConfig
    secrets: BridgeSecrets


def build_app(config_store: ConfigStore, bot_service: TelegramBridgeService, provider_factory) -> FastAPI:
    app = FastAPI(title="Codex Telegram Bridge")
    static_dir = Path(__file__).resolve().parent / "static"

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/api/state")
    async def get_state() -> dict:
        config = config_store.load_config()
        secrets = config_store.load_secrets()
        provider: AgentProvider = provider_factory(config)
        install_check = await provider.check_installation()
        auth_check = await provider.check_auth()
        return {
            "config": config.model_dump(),
            "secrets": {"telegram_bot_token": secrets.telegram_bot_token},
            "templates": {key: value.model_dump() for key, value in TEMPLATE_PRESETS.items()},
            "diagnostics": {
                "install": install_check.model_dump(),
                "auth": auth_check.model_dump(),
            },
        }

    @app.post("/api/config")
    async def save_state(payload: ConfigPayload) -> dict:
        config_store.save_config(payload.config)
        config_store.save_secrets(payload.secrets)
        await bot_service.start_if_configured()
        return {"ok": True}

    @app.post("/api/restart-bot")
    async def restart_bot() -> dict:
        await bot_service.start_if_configured()
        return {"ok": True}

    @app.get("/api/templates")
    async def list_templates() -> dict:
        return {key: value.model_dump() for key, value in TEMPLATE_PRESETS.items()}

    @app.post("/api/test-workspace")
    async def test_workspace(payload: dict) -> dict:
        workspace = str(payload.get("workspace_path", "")).strip()
        if not workspace:
            raise HTTPException(status_code=400, detail="workspace_path is required")
        path = Path(workspace)
        return {
            "exists": path.exists(),
            "is_dir": path.is_dir(),
            "resolved": str(path.resolve()) if path.exists() else str(path),
        }

    return app
