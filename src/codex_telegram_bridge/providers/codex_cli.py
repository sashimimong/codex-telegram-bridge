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
        return shutil.which("codex") or ""

    def build_run_command(self, prompt: str) -> list[str]:
        exe = self.resolve_executable()
        return [exe, "exec", prompt]

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
            code, out, err = await self._run_probe([exe, "--version"])
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
            [exe, "auth", "status"],
            [exe, "login", "status"],
            [exe, "whoami"],
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
            out, err = await asyncio.wait_for(proc.communicate(), timeout=self.config.timeout_seconds)
        except asyncio.TimeoutError:
            await self.cancel(session_context.session_id)
            return RunResult(ok=False, output="", error="Codex CLI timed out.", command=command)
        finally:
            self._running.pop(session_context.session_id, None)

        stdout = out.decode("utf-8", errors="replace").strip()
        stderr = err.decode("utf-8", errors="replace").strip()

        if proc.returncode == 0 and stdout:
            return RunResult(ok=True, output=stdout, command=command)
        if proc.returncode == 0:
            return RunResult(ok=True, output="Codex completed successfully but returned no text.", command=command)
        return RunResult(ok=False, output=stdout, error=stderr or "Codex CLI failed.", command=command)

    async def cancel(self, session_id: str) -> None:
        proc = self._running.pop(session_id, None)
        if proc and proc.returncode is None:
            proc.kill()
            await proc.wait()
