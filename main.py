"""
Chronos-windows – minimal prototype

Features:
  1. PowerShell execution   (!ps ...)
  2. Screenshot             (!screenshot / !ss)
  3. Simple mouse           (!mouse click / move x y)

Only users in ALLOWED_USER_IDS can use it.
Commands that change the system require a ✅ reaction.
"""

from __future__ import annotations

import asyncio
import io
import os
import subprocess
import time
from pathlib import Path

import discord
from dotenv import load_dotenv
import mss
from PIL import Image
import pyautogui

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
CHANNEL_ID = int(os.getenv("COMMAND_CHANNEL_ID", "0") or 0)
ALLOWED = {
    int(x.strip())
    for x in os.getenv("ALLOWED_USER_IDS", "").split(",")
    if x.strip().isdigit()
}

PREFIX = "!"
APPROVAL_TIMEOUT = 45  # seconds

if not TOKEN or not CHANNEL_ID:
    raise SystemExit("Set DISCORD_TOKEN and COMMAND_CHANNEL_ID in .env")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_allowed(user_id: int) -> bool:
    return not ALLOWED or user_id in ALLOWED


async def run_powershell(command: str, timeout: int = 60) -> tuple[int, str, str]:
    """Run a PowerShell command and return (returncode, stdout, stderr)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return 1, "", f"Timed out after {timeout}s"

        stdout = (stdout_b or b"").decode("utf-8", errors="replace").strip()
        stderr = (stderr_b or b"").decode("utf-8", errors="replace").strip()
        return proc.returncode or 0, stdout, stderr
    except Exception as e:
        return 1, "", str(e)


def take_screenshot() -> bytes:
    """Capture the primary monitor and return PNG bytes."""
    with mss.mss() as sct:
        # monitor 1 = primary
        mon = sct.monitors[1]
        shot = sct.grab(mon)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()


def mouse_action(spec: str) -> str:
    """
    Simple mouse helper.
    Examples:
      click
      click right
      move 400 300
    """
    parts = spec.strip().split()
    if not parts:
        return "Usage: !mouse click [left|right|middle]  or  !mouse move X Y"

    action = parts[0].lower()

    if action in ("click", "left", "right", "middle"):
        button = "left"
        if action in ("right", "middle"):
            button = action
        elif len(parts) > 1:
            button = parts[1].lower()
            if button not in ("left", "right", "middle"):
                button = "left"

        pyautogui.click(button=button)
        return f"Clicked {button}"

    if action in ("move", "moveto"):
        if len(parts) < 3:
            return "Usage: !mouse move X Y"
        try:
            x, y = int(parts[1]), int(parts[2])
        except ValueError:
            return "X and Y must be integers"
        pyautogui.moveTo(x, y)
        return f"Moved to {x},{y}"

    return f"Unknown mouse action: {action}"


def truncate(text: str, limit: int = 1900) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n… (truncated)"

# ---------------------------------------------------------------------------
# Discord client
# ---------------------------------------------------------------------------

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print(f"Logged in as {client.user} (ID: {client.user.id})")
    print(f"Watching channel: {CHANNEL_ID}")
    print(f"Allowed users: {ALLOWED or 'everyone (empty list)'}")
    print("Ready.")


@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if message.channel.id != CHANNEL_ID:
        return
    if not is_allowed(message.author.id):
        return

    content = message.content.strip()
    if not content.startswith(PREFIX):
        return

    body = content[len(PREFIX) :].strip()
    if not body:
        return

    lower = body.lower()

    # ---- help / ping (no approval needed) ----
    if lower in ("help", "h"):
        await message.reply(
            "**Chronos-windows**\n"
            "`!ps <command>` – run PowerShell\n"
            "`!screenshot` / `!ss` – take screenshot\n"
            "`!mouse click [left|right]` – mouse click\n"
            "`!mouse move X Y` – move mouse\n"
            "`!ping` – latency\n"
            "\nPowerShell and mouse require ✅ approval.",
            mention_author=False,
        )
        return

    if lower == "ping":
        latency = round(client.latency * 1000)
        await message.reply(f"Pong – {latency} ms", mention_author=False)
        return

    # ---- screenshot (no approval) ----
    if lower in ("screenshot", "ss", "screen"):
        try:
            png = await asyncio.to_thread(take_screenshot)
            file = discord.File(io.BytesIO(png), filename="screenshot.png")
            await message.reply(file=file, mention_author=False)
        except Exception as e:
            await message.reply(f"Screenshot failed: `{e}`", mention_author=False)
        return

    # ---- commands that need approval ----
    needs_approval = False
    action = None
    arg = ""

    if lower.startswith("ps ") or lower.startswith("powershell "):
        needs_approval = True
        action = "ps"
        arg = body.split(maxsplit=1)[1] if " " in body else ""
    elif lower.startswith("mouse "):
        needs_approval = True
        action = "mouse"
        arg = body.split(maxsplit=1)[1] if " " in body else ""

    if not needs_approval:
        await message.reply("Unknown command. Use `!help`", mention_author=False)
        return

    if not arg:
        await message.reply("Missing argument. Use `!help`", mention_author=False)
        return

    # Ask for approval
    try:
        await message.add_reaction("✅")
        await message.add_reaction("❌")
    except discord.HTTPException:
        pass

    def check(reaction: discord.Reaction, user: discord.User):
        return (
            reaction.message.id == message.id
            and str(reaction.emoji) in ("✅", "❌")
            and not user.bot
            and is_allowed(user.id)
        )

    try:
        reaction, user = await client.wait_for(
            "reaction_add", timeout=APPROVAL_TIMEOUT, check=check
        )
    except asyncio.TimeoutError:
        await message.reply("Timed out – no approval.", mention_author=False)
        return

    if str(reaction.emoji) == "❌":
        await message.reply("Denied.", mention_author=False)
        return

    # ---- execute ----
    if action == "ps":
        await message.reply(f"Running PowerShell…", mention_author=False)
        code, out, err = await run_powershell(arg)

        parts = []
        if out:
            parts.append(f"**stdout**\n```\n{truncate(out)}\n```")
        if err:
            parts.append(f"**stderr**\n```\n{truncate(err)}\n```")
        if not parts:
            parts.append("(no output)")

        text = f"Exit code: `{code}`\n" + "\n".join(parts)
        await message.reply(truncate(text, 2000), mention_author=False)

    elif action == "mouse":
        try:
            result = await asyncio.to_thread(mouse_action, arg)
            await message.reply(result, mention_author=False)
        except Exception as e:
            await message.reply(f"Mouse failed: `{e}`", mention_author=False)


def main():
    client.run(TOKEN)


if __name__ == "__main__":
    main()
