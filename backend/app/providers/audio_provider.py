from __future__ import annotations

from pathlib import Path

from app.core.scene_presets import get_scene_preset
from app.services.process_utils import run_ffmpeg


class FfmpegAudioProvider:
    async def normalize_input(self, source_path: Path, output_path: Path) -> Path:
        await run_ffmpeg(["-i", str(source_path), "-vn", "-ac", "2", "-ar", "48000", "-c:a", "pcm_s16le", str(output_path)])
        return output_path

    async def cleanup_noise(self, source_path: Path, output_path: Path) -> Path:
        cleanup_chain = ",".join([
            "silenceremove=start_periods=1:start_duration=0.25:start_threshold=-38dB",
            "highpass=f=90",
            "lowpass=f=13500",
            "afftdn=nf=-32:nt=w",
            "agate=threshold=0.018:ratio=10:attack=5:release=250:makeup=1",
            "adeclick",
            "deesser=i=0.35:m=0.5:f=0.5:s=o",
            "dynaudnorm=f=120:g=5",
        ])
        await run_ffmpeg(["-i", str(source_path), "-af", cleanup_chain, str(output_path)])
        return output_path

    async def approximate_separate(self, source_path: Path, vocal_path: Path, instrumental_path: Path) -> dict:
        await run_ffmpeg([
            "-i",
            str(source_path),
            "-filter_complex",
            ";".join([
                "[0:a]pan=mono|c0=0.5*c0+0.5*c1,volume=1.2[a_vocal]",
                "[0:a]pan=stereo|c0=c0-c1|c1=c1-c0,volume=0.75[a_backing]",
            ]),
            "-map",
            "[a_vocal]",
            "-c:a",
            "pcm_s16le",
            str(vocal_path),
            "-map",
            "[a_backing]",
            "-c:a",
            "pcm_s16le",
            str(instrumental_path),
        ])
        return {
            "vocalPath": vocal_path,
            "instrumentalPath": instrumental_path,
            "note": "Used a local mid/side heuristic separation. Replace this provider with an ML/API stem splitter for production quality.",
        }

    async def polish_voice(self, source_path: Path, output_path: Path) -> Path:
        polish_chain = ",".join([
            "acompressor=threshold=-18dB:ratio=2.2:attack=15:release=120:makeup=2",
            "equalizer=f=180:t=q:w=1.0:g=-1.5",
            "equalizer=f=3500:t=q:w=1.0:g=2.2",
            "aexciter=amount=1.1:drive=6.5:blend=0.18",
            "aecho=0.82:0.55:35|70:0.10|0.06",
        ])
        await run_ffmpeg(["-i", str(source_path), "-af", polish_chain, str(output_path)])
        return output_path

    async def apply_scene_preset(self, source_path: Path, preset_id: str, output_path: Path) -> dict:
        preset = get_scene_preset(preset_id)
        filter_chain = ",".join([*preset["chain"], "alimiter=limit=0.93"])
        await run_ffmpeg(["-i", str(source_path), "-af", filter_chain, str(output_path)])
        return {"outputPath": output_path, "preset": preset}

    async def remix(self, processed_vocal_path: Path, backing_path: Path, output_path: Path) -> Path:
        await run_ffmpeg([
            "-i",
            str(processed_vocal_path),
            "-i",
            str(backing_path),
            "-filter_complex",
            "[0:a]volume=1.15[v];[1:a]volume=0.78[b];[v][b]amix=inputs=2:weights=1 1:normalize=0,alimiter=limit=0.95[out]",
            "-map",
            "[out]",
            str(output_path),
        ])
        return output_path

    async def export_final(self, source_path: Path, output_path: Path) -> Path:
        await run_ffmpeg(["-i", str(source_path), "-c:a", "libmp3lame", "-b:a", "192k", str(output_path)])
        return output_path
