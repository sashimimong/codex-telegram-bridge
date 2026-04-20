import shutil

from codex_telegram_bridge.models import BridgeConfig
from codex_telegram_bridge.providers.codex_cli import CodexCLIProvider


def test_build_run_command_uses_exec() -> None:
    config = BridgeConfig(codex_cli_path=r"C:\Tools\codex.exe")
    provider = CodexCLIProvider(config)

    command = provider.build_run_command("hello world")

    assert command[0] == r"C:\Tools\codex.exe"
    assert command[1] == "exec"
    assert len(command) == 2


def test_resolve_executable_prefers_configured_path() -> None:
    config = BridgeConfig(codex_cli_path=r"C:\Custom\codex.exe")
    provider = CodexCLIProvider(config)

    assert provider.resolve_executable() == r"C:\Custom\codex.exe"


def test_resolve_executable_prefers_non_windowsapps_install(monkeypatch) -> None:
    def fake_which(name: str) -> str | None:
        mapping = {
            "codex.cmd": r"C:\nvm4w\nodejs\codex.cmd",
            "codex.exe": r"C:\Program Files\WindowsApps\OpenAI.Codex\codex.exe",
            "codex": r"C:\Program Files\WindowsApps\OpenAI.Codex\codex",
        }
        return mapping.get(name)

    monkeypatch.setattr(shutil, "which", fake_which)

    provider = CodexCLIProvider(BridgeConfig())
    monkeypatch.setattr(
        provider,
        "_resolve_npm_bundled_exe",
        lambda codex_cmd: r"C:\nvm4w\nodejs\node_modules\@openai\codex\node_modules\@openai\codex-win32-x64\vendor\x86_64-pc-windows-msvc\codex\codex.exe",
    )

    assert provider.resolve_executable().endswith(r"codex\codex.exe")


def test_build_run_command_wraps_cmd_install() -> None:
    config = BridgeConfig(codex_cli_path=r"C:\nvm4w\nodejs\codex.cmd")
    provider = CodexCLIProvider(config)

    command = provider.build_run_command("hello world")

    assert command[:3] == ["cmd.exe", "/c", r"C:\nvm4w\nodejs\codex.cmd"]
    assert command[3:] == ["exec"]
