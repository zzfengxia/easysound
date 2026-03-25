from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from app.core.config import FFMPEG_PATH, FFPROBE_PATH

logger = logging.getLogger(__name__)


async def run_command(binary: Path, args: list[str]) -> tuple[str, str]:
    command_text = " ".join([str(binary), *args])
    logger.info("开始执行命令：%s", command_text)
    process = await asyncio.create_subprocess_exec(
        str(binary),
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    stdout_text = stdout.decode("utf-8", errors="ignore")
    stderr_text = stderr.decode("utf-8", errors="ignore")
    if process.returncode != 0:
        logger.error("命令执行失败，退出码=%s，命令=%s，错误=%s", process.returncode, command_text, stderr_text.strip())
        raise RuntimeError(stderr_text or f"命令执行失败：{binary}")
    logger.info("命令执行完成：%s", command_text)
    return stdout_text, stderr_text


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
