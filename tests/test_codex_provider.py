from codex_telegram_bridge.models import BridgeConfig
from codex_telegram_bridge.providers.codex_cli import CodexCLIProvider


def test_build_run_command_uses_exec() -> None:
    config = BridgeConfig(codex_cli_path=r"C:\Tools\codex.exe")
    provider = CodexCLIProvider(config)

    command = provider.build_run_command("hello world")

    assert command[0] == r"C:\Tools\codex.exe"
    assert command[1] == "exec"
    assert command[2] == "hello world"


def test_resolve_executable_prefers_configured_path() -> None:
    config = BridgeConfig(codex_cli_path=r"C:\Custom\codex.exe")
    provider = CodexCLIProvider(config)

    assert provider.resolve_executable() == r"C:\Custom\codex.exe"
