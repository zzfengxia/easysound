from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from pathlib import Path

from app.core.config import FFMPEG_PATH, FFPROBE_PATH

logger = logging.getLogger(__name__)


def _run_command_sync(binary: Path, args: list[str]) -> tuple[str, str]:
    completed = subprocess.run(
        [str(binary), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=False,
    )
    if completed.returncode != 0:
        logger.error(
            "命令执行失败，退出码=%s，命令=%s，错误=%s",
            completed.returncode,
            " ".join([str(binary), *args]),
            completed.stderr.strip(),
        )
        raise RuntimeError(completed.stderr or f"命令执行失败：{binary}")
    return completed.stdout, completed.stderr


async def run_command(binary: Path, args: list[str]) -> tuple[str, str]:
    command_text = " ".join([str(binary), *args])
    logger.info("开始执行命令：%s", command_text)
    stdout_text, stderr_text = await asyncio.to_thread(_run_command_sync, binary, args)
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
