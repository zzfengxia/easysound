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
            "silenceremove=start_periods=1:start_duration=0.18:start_threshold=-34dB:stop_periods=1:stop_duration=0.28:stop_threshold=-36dB",
            "highpass=f=90",
            "lowpass=f=13500",
            "afftdn=nf=-36:nt=w",
            "agate=threshold=0.022:ratio=14:attack=4:release=220:makeup=0.6",
            "adeclick",
            "deesser=i=0.35:m=0.5:f=0.5:s=o",
            "dynaudnorm=f=120:g=4:p=0.8:m=10",
        ])
        await run_ffmpeg(["-i", str(source_path), "-af", cleanup_chain, str(output_path)])
        return output_path

    async def approximate_separate(self, source_path: Path, vocal_path: Path, instrumental_path: Path) -> dict:
        await run_ffmpeg([
            "-i",
            str(source_path),
            "-filter_complex",
            ";".join([
                "[0:a]pan=mono|c0=0.5*c0+0.5*c1,volume=1.0[a_vocal]",
                "[0:a]pan=stereo|c0=c0-c1|c1=c1-c0,volume=1.0[a_backing]",
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

    async def soften_voice(self, source_path: Path, output_path: Path, amount: int = 55) -> Path:
        normalized = max(0.0, min(1.0, amount / 100.0))
        deesser_intensity = 0.12 + normalized * 0.24
        presence_cut = 0.5 + normalized * 2.6
        air_cut = 0.3 + normalized * 2.0
        compressor_ratio = 1.1 + normalized * 1.0
        makeup_gain = 0.4 + normalized * 1.0
        soften_chain = ",".join([
            f"deesser=i={deesser_intensity:.2f}:m=0.45:f=0.45:s=o",
            f"equalizer=f=5200:t=q:w=1.0:g=-{presence_cut:.2f}",
            f"equalizer=f=8600:t=q:w=1.2:g=-{air_cut:.2f}",
            f"acompressor=threshold=-20dB:ratio={compressor_ratio:.2f}:attack=10:release=140:makeup={makeup_gain:.2f}",
            "alimiter=limit=0.97",
        ])
        await run_ffmpeg(["-i", str(source_path), "-af", soften_chain, str(output_path)])
        return output_path

    async def polish_voice(self, source_path: Path, output_path: Path, light_reverb_amount: int = 45) -> Path:
        normalized = max(0.0, min(1.0, light_reverb_amount / 100.0))
        compress_ratio = 1.6 + normalized * 0.9
        makeup_gain = 1.1 + normalized * 1.2
        presence_boost = 0.7 + normalized * 1.3
        exciter_amount = 0.45 + normalized * 0.75
        exciter_blend = 0.08 + normalized * 0.10
        reverb_decay = 0.38 + normalized * 0.34
        reverb_mix_one = 0.04 + normalized * 0.12
        reverb_mix_two = 0.02 + normalized * 0.08
        reverb_mix_three = 0.01 + normalized * 0.05
        polish_chain = ",".join([
            f"acompressor=threshold=-18dB:ratio={compress_ratio:.2f}:attack=15:release=140:makeup={makeup_gain:.2f}",
            "equalizer=f=180:t=q:w=1.0:g=-1.2",
            f"equalizer=f=3200:t=q:w=1.0:g={presence_boost:.2f}",
            f"aexciter=amount={exciter_amount:.2f}:drive=5.5:blend={exciter_blend:.2f}",
            f"aecho=0.84:{reverb_decay:.2f}:42|84|126:{reverb_mix_one:.2f}|{reverb_mix_two:.2f}|{reverb_mix_three:.2f}",
        ])
        await run_ffmpeg(["-i", str(source_path), "-af", polish_chain, str(output_path)])
        return output_path

    async def apply_scene_preset(self, source_path: Path, preset_id: str, output_path: Path) -> dict:
        preset = get_scene_preset(preset_id)
        filter_chain = ",".join([*preset["chain"], "alimiter=limit=0.93"])
        await run_ffmpeg(["-i", str(source_path), "-af", filter_chain, str(output_path)])
        return {"outputPath": output_path, "preset": preset}

    def map_mix_amounts(self, vocal_mix_amount: int, backing_mix_amount: int) -> dict:
        def to_gain(value: int, base: float, spread: float) -> float:
            normalized = max(0.0, min(1.0, value / 100.0))
            centered = (normalized - 0.5) * 2.0
            curved = centered * abs(centered)
            return max(0.15, base + curved * spread)

        vocal_gain = to_gain(vocal_mix_amount, base=1.08, spread=0.72)
        backing_gain = to_gain(backing_mix_amount, base=0.86, spread=0.62)
        return {
            "vocalGain": round(vocal_gain, 3),
            "backingGain": round(backing_gain, 3),
        }

    async def remix(self, processed_vocal_path: Path, backing_path: Path, output_path: Path, *, vocal_mix_amount: int, backing_mix_amount: int) -> dict:
        mapped = self.map_mix_amounts(vocal_mix_amount, backing_mix_amount)
        await run_ffmpeg([
            "-i",
            str(processed_vocal_path),
            "-i",
            str(backing_path),
            "-filter_complex",
            f"[0:a]volume={mapped['vocalGain']:.3f}[v];[1:a]volume={mapped['backingGain']:.3f}[b];[v][b]amix=inputs=2:weights=1 1:normalize=0,alimiter=limit=0.95[out]",
            "-map",
            "[out]",
            str(output_path),
        ])
        return {"outputPath": output_path, **mapped}

    async def normalize_loudness(self, source_path: Path, output_path: Path) -> Path:
        loudness_chain = ",".join([
            "agate=threshold=0.018:ratio=10:attack=6:release=180:makeup=0.2",
            "acompressor=threshold=-22dB:ratio=1.55:attack=20:release=220:makeup=1.4",
            "dynaudnorm=f=180:g=5:p=0.82:m=10",
            "loudnorm=I=-16:LRA=10:TP=-1.5",
            "silenceremove=start_periods=1:start_duration=0.14:start_threshold=-39dB:stop_periods=1:stop_duration=0.20:stop_threshold=-40dB",
            "alimiter=limit=0.95",
        ])
        await run_ffmpeg(["-i", str(source_path), "-af", loudness_chain, str(output_path)])
        return output_path

    async def export_final(self, source_path: Path, output_path: Path) -> Path:
        await run_ffmpeg(["-i", str(source_path), "-c:a", "libmp3lame", "-b:a", "192k", str(output_path)])
        return output_path
