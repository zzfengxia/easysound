from __future__ import annotations

from app.services.process_utils import run_ffprobe_json


async def probe_audio(file_path):
    parsed = await run_ffprobe_json(file_path)
    audio_stream = next((stream for stream in parsed.get("streams", []) if stream.get("codec_type") == "audio"), {})
    return {
        "durationSeconds": float(parsed.get("format", {}).get("duration", 0) or 0),
        "sampleRate": int(audio_stream.get("sample_rate", 0) or 0),
        "channels": int(audio_stream.get("channels", 0) or 0),
        "codec": audio_stream.get("codec_name", "unknown"),
        "formatName": parsed.get("format", {}).get("format_name", "unknown"),
        "bitRate": int(parsed.get("format", {}).get("bit_rate", 0) or 0),
    }
