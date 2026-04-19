from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from ..models import BridgeConfig, ProviderCheck, RunResult, SessionContext
from ..provider_base import AgentProvider


class CodexCLIProvider(AgentProvider):
    def __init__(self, config: BridgeConfig) -> None:
        self.config = config
        self._running: dict[str, asyncio.subprocess.Process] = {}

    def resolve_executable(self) -> str:
        if self.config.codex_cli_path:
            return self.config.codex_cli_path
        codex_cmd = shutil.which("codex.cmd")
        candidates = [
            self._resolve_npm_bundled_exe(codex_cmd) if codex_cmd else None,
            codex_cmd,
            shutil.which("codex.exe"),
            shutil.which("codex"),
        ]
        valid_candidates = [candidate for candidate in candidates if candidate]
        preferred = [
            candidate
            for candidate in valid_candidates
            if "WindowsApps" not in str(Path(candidate))
        ]
        return (preferred or valid_candidates or [""])[0]

    def _resolve_npm_bundled_exe(self, codex_cmd: str) -> str:
        cmd_path = Path(codex_cmd)
        bundled = (
            cmd_path.parent
            / "node_modules"
            / "@openai"
            / "codex"
            / "node_modules"
            / "@openai"
            / "codex-win32-x64"
            / "vendor"
            / "x86_64-pc-windows-msvc"
            / "codex"
            / "codex.exe"
        )
        return str(bundled) if bundled.exists() else ""

    def build_run_command(self, prompt: str) -> list[str]:
        exe = self.resolve_executable()
        return self._build_command(exe, "exec")

    def _build_command(self, exe: str, *args: str) -> list[str]:
        # Global npm installs on Windows often expose Codex via codex.cmd.
        if exe.lower().endswith((".cmd", ".bat")):
            return ["cmd.exe", "/c", exe, *args]
        return [exe, *args]

    def _normalize_error(self, stderr: str, stdout: str, workspace: str) -> str:
        merged = "\n".join(part for part in (stderr, stdout) if part).strip()
        lower = merged.lower()
        if "not inside a trusted directory" in lower:
            return (
                "현재 작업 폴더가 Codex 신뢰 대상이 아니라 실행이 막혔습니다.\n"
                "작업 폴더를 git 저장소로 바꾸거나 신뢰된 폴더로 설정해주세요.\n"
                f"현재 작업 폴더: {workspace or '(not set)'}"
            )
        return stderr or stdout or "Codex CLI failed."

    def _clean_output(self, text: str) -> str:
        if not text:
            return text

        noise_markers = (
            "Reading additional input from stdin...",
            "startup remote plugin sync failed",
            "failed to warm featured plugin ids cache",
            "WARN codex_core::",
            "WARN codex_analytics::",
            "tokens used",
            "<html>",
            "</html>",
            "__cf_chl_opt",
            "Enable JavaScript and cookies to continue",
        )

        cleaned: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                if cleaned and cleaned[-1] != "":
                    cleaned.append("")
                continue
            if any(marker in stripped for marker in noise_markers):
                continue
            if stripped.startswith("2024-") and "WARN " in stripped:
                continue
            if stripped.startswith("2025-") and "WARN " in stripped:
                continue
            if stripped.startswith("2026-") and "WARN " in stripped:
                continue
            cleaned.append(line)

        result = "\n".join(cleaned).strip()
        return result or text.strip()

    async def _run_probe(self, command: list[str], cwd: str | None = None) -> tuple[int, str, str]:
        proc = await asyncio.create_subprocess_exec(
            *command,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        return proc.returncode, out.decode("utf-8", errors="replace"), err.decode("utf-8", errors="replace")

    async def check_installation(self) -> ProviderCheck:
        exe = self.resolve_executable()
        if not exe:
            return ProviderCheck(
                ok=False,
                status="error",
                message="Codex CLI was not found.",
                details=["Install Codex and/or set an explicit executable path."],
            )

        exe_path = Path(exe)
        if not exe_path.exists():
            return ProviderCheck(
                ok=False,
                status="error",
                message="Configured Codex CLI path does not exist.",
                details=[str(exe_path)],
            )

        try:
            code, out, err = await self._run_probe(self._build_command(exe, "--version"))
        except PermissionError:
            return ProviderCheck(
                ok=False,
                status="error",
                message="Codex CLI was found but could not be executed.",
                details=[str(exe_path), "Windows packaged installs may require a direct executable path."],
            )
        except FileNotFoundError:
            return ProviderCheck(
                ok=False,
                status="error",
                message="Codex CLI executable could not be launched.",
                details=[str(exe_path)],
            )

        if code == 0:
            details = [str(exe_path)]
            if out.strip():
                details.append(out.strip())
            return ProviderCheck(ok=True, status="ok", message="Codex CLI detected.", details=details)

        return ProviderCheck(
            ok=False,
            status="error",
            message="Codex CLI check failed.",
            details=[str(exe_path), err.strip() or out.strip() or f"Exit code: {code}"],
        )

    async def check_auth(self) -> ProviderCheck:
        exe = self.resolve_executable()
        if not exe:
            return ProviderCheck(ok=False, status="error", message="Codex CLI is not configured.")

        candidates = (
            self._build_command(exe, "auth", "status"),
            self._build_command(exe, "login", "status"),
            self._build_command(exe, "whoami"),
        )

        observed_errors: list[str] = []
        for command in candidates:
            try:
                code, out, err = await self._run_probe(command)
            except (PermissionError, FileNotFoundError) as exc:
                observed_errors.append(str(exc))
                continue

            merged = "\n".join(part for part in (out, err) if part).strip()
            lower = merged.lower()

            if code == 0:
                return ProviderCheck(
                    ok=True,
                    status="ok",
                    message="Codex auth looks available.",
                    details=[merged or "Auth probe succeeded."],
                )

            if any(token in lower for token in ("login", "sign in", "authenticate", "not logged")):
                return ProviderCheck(
                    ok=False,
                    status="warning",
                    message="Codex CLI appears installed but not logged in.",
                    details=[merged or f"Exit code: {code}"],
                )

            observed_errors.append(merged or f"{' '.join(command)} -> {code}")

        return ProviderCheck(
            ok=False,
            status="warning",
            message="Could not confirm Codex auth status automatically.",
            details=observed_errors or ["Open Codex locally and verify you are signed in."],
        )

    async def run(self, prompt: str, workspace: str, session_context: SessionContext) -> RunResult:
        exe = self.resolve_executable()
        if not exe:
            return RunResult(ok=False, output="", error="Codex CLI is not configured.")

        command = self.build_run_command(prompt)
        try:
            proc = await asyncio.create_subprocess_exec(
                *command,
                cwd=workspace or None,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except PermissionError:
            return RunResult(
                ok=False,
                output="",
                error="Codex CLI could not be launched from the current path. Try configuring the explicit executable path.",
                command=command,
            )
        except FileNotFoundError:
            return RunResult(ok=False, output="", error="Codex CLI executable was not found.", command=command)

        self._running[session_context.session_id] = proc
        try:
            out, err = await asyncio.wait_for(
                proc.communicate(prompt.encode("utf-8")),
                timeout=self.config.timeout_seconds,
            )
        except asyncio.TimeoutError:
            await self.cancel(session_context.session_id)
            return RunResult(ok=False, output="", error="Codex CLI timed out.", command=command)
        finally:
            self._running.pop(session_context.session_id, None)

        stdout = self._clean_output(out.decode("utf-8", errors="replace").strip())
        stderr = err.decode("utf-8", errors="replace").strip()

        if proc.returncode == 0 and stdout:
            return RunResult(ok=True, output=stdout, command=command)
        if proc.returncode == 0:
            return RunResult(ok=True, output="Codex completed successfully but returned no text.", command=command)
        return RunResult(
            ok=False,
            output=stdout,
            error=self._normalize_error(stderr, stdout, workspace),
            command=command,
        )

    async def cancel(self, session_id: str) -> None:
        proc = self._running.pop(session_id, None)
        if proc and proc.returncode is None:
            proc.kill()
            await proc.wait()
