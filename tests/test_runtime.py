from pathlib import Path

from codex_telegram_bridge.config_store import ConfigStore
from codex_telegram_bridge.models import BridgeConfig, RunResult, SessionContext
from codex_telegram_bridge.runtime import BridgeRuntime


class DummyProvider:
    def __init__(self) -> None:
        self.prompt = ""

    async def run(self, prompt: str, workspace: str, session_context: SessionContext) -> RunResult:
        self.prompt = prompt
        return RunResult(ok=True, output="ok")


def test_runtime_translation_block_is_disabled_by_default(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path)
    store.save_config(BridgeConfig(workspace_path=str(tmp_path)))

    provider = DummyProvider()
    runtime = BridgeRuntime(store, lambda config: provider)

    prompt, _ = runtime._build_prompt(
        store.load_config(),
        runtime._get_state("chat-1"),
        "안녕하세요",
        "chat-1",
        "user-1",
    )

    assert "English translation for compatibility" not in prompt
    assert "Required Output Format:" in prompt
    assert "한줄 답변" in prompt
    assert "Template Runtime Rules:" in prompt
    assert "Workspace Context Policy: optional" in prompt


def test_runtime_translation_block_is_enabled_when_configured(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path)
    store.save_config(BridgeConfig(workspace_path=str(tmp_path), translation_enabled=True))

    provider = DummyProvider()
    runtime = BridgeRuntime(store, lambda config: provider)

    prompt, _ = runtime._build_prompt(
        store.load_config(),
        runtime._get_state("chat-1"),
        "안녕하세요",
        "chat-1",
        "user-1",
    )

    assert "English translation for compatibility" in prompt


def test_runtime_coding_template_requires_workspace_context(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path)
    store.save_config(BridgeConfig(workspace_path=str(tmp_path), default_template="coding"))

    provider = DummyProvider()
    runtime = BridgeRuntime(store, lambda config: provider)

    prompt, _ = runtime._build_prompt(
        store.load_config(),
        runtime._get_state("chat-1"),
        "Fix this bug",
        "chat-1",
        "user-1",
    )

    assert "Workspace Context Policy: required" in prompt
    assert "You must ground the answer in the workspace context before giving generic advice." in prompt
    assert "Do not omit the verification section." in prompt


def test_runtime_daily_template_uses_shorter_history_window(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path)
    store.save_config(BridgeConfig(workspace_path=str(tmp_path), default_template="daily", max_history_messages=8))

    provider = DummyProvider()
    runtime = BridgeRuntime(store, lambda config: provider)
    state = runtime._get_state("chat-1")
    state.history = [{"role": "user", "content": f"msg-{idx}"} for idx in range(10)]

    prompt, session_context = runtime._build_prompt(
        store.load_config(),
        state,
        "Recommend dinner",
        "chat-1",
        "user-1",
    )

    assert "Conversation History Window: 4" in prompt
    assert len(session_context.history) == 4
    assert session_context.history[0]["content"] == "msg-6"


def test_runtime_uses_custom_response_format_when_provided(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path)
    store.save_config(
        BridgeConfig(
            workspace_path=str(tmp_path),
            default_template="coding",
            response_format="1. 커스텀 요약\n2. 커스텀 액션",
        )
    )

    provider = DummyProvider()
    runtime = BridgeRuntime(store, lambda config: provider)

    prompt, _ = runtime._build_prompt(
        store.load_config(),
        runtime._get_state("chat-1"),
        "Fix this bug",
        "chat-1",
        "user-1",
    )

    assert "1. 커스텀 요약" in prompt
    assert "2. 커스텀 액션" in prompt
