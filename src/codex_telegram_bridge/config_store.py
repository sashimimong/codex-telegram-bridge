from __future__ import annotations

import json
from pathlib import Path

from .models import BridgeConfig, BridgeSecrets


class ConfigStore:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or (Path.cwd() / ".bridge_data")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.base_dir / "config.json"
        self.secrets_path = self.base_dir / "secrets.json"

    def load_config(self) -> BridgeConfig:
        if not self.config_path.exists():
            return BridgeConfig()
        return BridgeConfig.model_validate_json(self.config_path.read_text(encoding="utf-8"))

    def save_config(self, config: BridgeConfig) -> None:
        self.config_path.write_text(
            json.dumps(config.model_dump(), ensure_ascii=True, indent=2),
            encoding="utf-8",
        )

    def load_secrets(self) -> BridgeSecrets:
        if not self.secrets_path.exists():
            return BridgeSecrets()
        return BridgeSecrets.model_validate_json(self.secrets_path.read_text(encoding="utf-8"))

    def save_secrets(self, secrets: BridgeSecrets) -> None:
        self.secrets_path.write_text(
            json.dumps(secrets.model_dump(), ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
