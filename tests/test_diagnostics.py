from pathlib import Path

from codex_telegram_bridge.diagnostics import analyze_workspace_path, mask_secret


def test_mask_secret_masks_middle() -> None:
    assert mask_secret("1234567890abcdef") == "1234********cdef"


def test_workspace_warning_for_empty_path() -> None:
    result = analyze_workspace_path("")
    assert result["status"] == "warning"
    assert result["warnings"]


def test_workspace_ok_for_git_directory(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    result = analyze_workspace_path(str(tmp_path))
    assert result["status"] == "ok"
    assert result["exists"] is True
