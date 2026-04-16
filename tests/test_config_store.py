from pathlib import Path

from codex_telegram_bridge.config_store import ConfigStore
from codex_telegram_bridge.models import BridgeConfig, BridgeSecrets


def test_config_store_round_trip(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path)
    config = BridgeConfig(
        bot_name="Test Bot",
        telegram_allowed_user_ids=["1", "2"],
        workspace_path=str(tmp_path),
        default_template="coding",
    )
    secrets = BridgeSecrets(telegram_bot_token="abc123")

    store.save_config(config)
    store.save_secrets(secrets)

    loaded_config = store.load_config()
    loaded_secrets = store.load_secrets()

    assert loaded_config.bot_name == "Test Bot"
    assert loaded_config.telegram_allowed_user_ids == ["1", "2"]
    assert loaded_config.default_template == "coding"
    assert loaded_secrets.telegram_bot_token == "abc123"
