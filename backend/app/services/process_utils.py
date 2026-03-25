from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

from app.core.config import FFMPEG_PATH, FFPROBE_PATH


async def run_command(binary: Path, args: list[str]) -> tuple[str, str]:
    process = await asyncio.create_subprocess_exec(
        str(binary),
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(stderr.decode("utf-8", errors="ignore") or f"Command failed: {binary}")
    return stdout.decode("utf-8", errors="ignore"), stderr.decode("utf-8", errors="ignore")


async def run_ffmpeg(args: list[str]) -> tuple[str, str]:
    return await run_command(FFMPEG_PATH, ["-y", *args])


async def run_ffprobe_json(file_path: Path) -> dict:
    stdout, _ = await run_command(
        FFPROBE_PATH,
        [
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(file_path),
        ],
    )
    return json.loads(stdout)
