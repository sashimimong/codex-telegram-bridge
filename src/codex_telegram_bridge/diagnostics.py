from __future__ import annotations

from pathlib import Path


def mask_secret(value: str, *, keep_start: int = 4, keep_end: int = 4) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if len(value) <= keep_start + keep_end:
        return "*" * len(value)
    return f"{value[:keep_start]}{'*' * 8}{value[-keep_end:]}"


def analyze_workspace_path(workspace_path: str) -> dict:
    workspace = str(workspace_path or "").strip()
    if not workspace:
        return {
            "exists": False,
            "is_dir": False,
            "resolved": "",
            "status": "warning",
            "message": "작업 폴더가 아직 설정되지 않았습니다.",
            "warnings": ["프로젝트 루트 폴더를 지정해 두면 Codex가 더 정확하게 동작합니다."],
        }

    path = Path(workspace).expanduser()
    exists = path.exists()
    is_dir = path.is_dir()
    resolved = str(path.resolve()) if exists else str(path)
    warnings: list[str] = []

    if exists and is_dir:
        if path.parent == path:
            warnings.append("드라이브 루트나 최상위 폴더는 너무 넓습니다. 실제 프로젝트 폴더를 지정하세요.")
        if path.name.lower() in {"users", "documents", "desktop", "downloads"}:
            warnings.append("개인 전체 폴더보다 실제 프로젝트 폴더를 지정하는 편이 더 안전합니다.")
        if not (path / ".git").exists():
            warnings.append("git 저장소가 아니어서 변경 범위 판단이 덜 안정적일 수 있습니다.")

    if not exists:
        status = "error"
        message = "입력한 작업 폴더가 존재하지 않습니다."
    elif not is_dir:
        status = "error"
        message = "작업 폴더 경로가 파일을 가리키고 있습니다. 폴더를 지정하세요."
    elif warnings:
        status = "warning"
        message = "작업 폴더를 사용할 수는 있지만 확인이 필요한 항목이 있습니다."
    else:
        status = "ok"
        message = "작업 폴더가 정상적으로 보입니다."

    return {
        "exists": exists,
        "is_dir": is_dir,
        "resolved": resolved,
        "status": status,
        "message": message,
        "warnings": warnings,
    }
