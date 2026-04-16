# Codex Telegram Bridge

Self-hosted Telegram bridge for **Codex CLI** on Windows.

## What v0.1 does

- Supports **Telegram only**
- Supports **Codex CLI only**
- Runs on your own laptop/desktop
- Lets you configure the bridge from a local browser UI
- Stores config locally

## Quick Start

### 1. Install

From PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install.ps1
```

### 2. Open the local UI

Go to:

```text
http://127.0.0.1:8765
```

### 3. Fill in setup

- `Telegram Bot Token`
- `Allowed User IDs`
- `Workspace Path`
- `Bot Name`
- Template preset

The app will auto-detect `codex.exe` when possible.

### 4. Start using the bot

Send a message to your Telegram bot from an allowed Telegram account.

## Commands

- `/start` - show bridge status
- `/status` - diagnostics
- `/template` - current template
- `/reset` - clear session history

## Security Notes

- Only allowed Telegram user IDs can use the bot.
- The selected workspace should be explicit and limited.
- The bridge runs Codex CLI on your machine, so treat it like a local automation tool.
- Keep your Telegram bot token private.

## Troubleshooting

### Codex not detected

- Confirm `codex.exe` is installed
- Try setting the explicit executable path in the UI
- Re-run diagnostics from `/status`

### Codex auth check fails

- Open Codex locally and confirm you're signed in
- Some Codex builds do not expose auth status consistently; the bridge will report that separately

### Telegram bot does not respond

- Verify the bot token
- Verify your Telegram user ID is in the allowed list
- Check the local UI diagnostics panel

## Current Scope

This release is intentionally narrow:

- Windows first
- Codex CLI only
- Telegram only
- local web UI instead of a full desktop installer
