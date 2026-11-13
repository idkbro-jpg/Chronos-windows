# Chronos-windows

Minimal Windows version of Chronos.

**Only these features:**
1. PowerShell command execution
2. Screenshot
3. Simple mouse control (click / move)

No complex approval system, no lock, no LUKS, no roles, no aliases.
Just a whitelist of Discord user IDs + basic reaction approval for commands.

---

## Quick start

1. Clone / download this repo
2. Create a virtual environment and install dependencies:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3. Copy `.env.example` → `.env` and fill in:

```env
DISCORD_TOKEN=your_bot_token_here
COMMAND_CHANNEL_ID=123456789012345678
ALLOWED_USER_IDS=123456789012345678,987654321098765432
```

4. Run it:

```powershell
python main.py
```

---

## Commands

| Command | Description |
|---------|-------------|
| `!ps <command>` | Run PowerShell command |
| `!screenshot` / `!ss` | Take a screenshot and send it |
| `!mouse click` | Left click |
| `!mouse click right` | Right click |
| `!mouse move 500 300` | Move mouse to x y |
| `!help` | Show help |
| `!ping` | Latency check |

Only users listed in `ALLOWED_USER_IDS` can use the bot.

Dangerous commands (PowerShell / mouse) still require a ✅ reaction before they run.

---

## Building a single .exe (optional)

```powershell
pip install pyinstaller
pyinstaller --onefile --console main.py
```

The `.exe` will be in the `dist` folder. Put your `.env` next to it.

---

## Important notes for VMs / RDP

- **Screenshot and mouse need an interactive desktop session.**  
  If you RDP into the VM and then disconnect, Windows may stop rendering the desktop → screenshot/mouse can fail or produce black images.

- Keep the RDP window open (or use a tool that keeps the session alive) while testing mouse/screenshot.

- PowerShell commands work fine even without a visible desktop.

---

## Dependencies

All pure-Python / have Windows wheels:

- discord.py
- python-dotenv
- mss
- Pillow
- pyautogui

No extra system packages needed.
