from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class BridgeSecrets(BaseModel):
    telegram_bot_token: str = ""


class BridgeConfig(BaseModel):
    bot_name: str = "Codex Telegram Bridge"
    telegram_allowed_user_ids: list[str] = Field(default_factory=list)
    codex_cli_path: str = ""
    workspace_path: str = ""
    default_template: str = "assistant"
    translation_enabled: bool = False
    system_rules: str = ""
    response_style: str = ""
    response_format: str = ""
    working_style: str = ""
    allowed_guidance: str = ""
    blocked_guidance: str = ""
    timeout_seconds: int = 600
    max_history_messages: int = 8

    @field_validator("telegram_allowed_user_ids", mode="before")
    @classmethod
    def normalize_allowed_users(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()]

    @field_validator("workspace_path")
    @classmethod
    def normalize_workspace_path(cls, value: str) -> str:
        return str(Path(value).expanduser()) if value else ""


class TemplatePreset(BaseModel):
    key: str
    name: str
    system_rules: str
    response_style: str
    response_format: str
    policy_summary: str = ""
    runtime_rules: list[str] = Field(default_factory=list)
    workspace_context: Literal["optional", "prefer", "required"] = "optional"
    history_window: int = 8
    working_style: str
    allowed_guidance: str
    blocked_guidance: str


class ProviderCheck(BaseModel):
    ok: bool
    status: Literal["ok", "warning", "error"]
    message: str
    details: list[str] = Field(default_factory=list)


class SessionContext(BaseModel):
    session_id: str
    user_id: str
    chat_id: str
    template_key: str
    history: list[dict[str, str]] = Field(default_factory=list)


class RunResult(BaseModel):
    ok: bool
    output: str
    error: str = ""
    command: list[str] = Field(default_factory=list)
