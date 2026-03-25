from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.services.process_utils import run_ffmpeg

try:
    import numpy as np
    import librosa
    from librosa.sequence import dtw as librosa_dtw
except Exception:  # pragma: no cover - dependency availability is environment-specific
    np = None
    librosa = None
    librosa_dtw = None

try:
    import pretty_midi
except Exception:  # pragma: no cover - dependency availability is environment-specific
    pretty_midi = None

try:
    import crepe as crepe_lib
except Exception:  # pragma: no cover - dependency availability is environment-specific
    crepe_lib = None


NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


@dataclass
class PitchSegment:
    start: float
    end: float
    voiced: bool
    source_midi: float | None = None
    target_midi: float | None = None
    confidence: float = 0.0


class AutoPitchProvider:
    def __init__(self) -> None:
        self.analysis_sr = 16000
        self.hop_length = 320
        self.min_voiced_hz = 65.0
        self.max_voiced_hz = 1046.5

    async def correct_pitch(self, source_path: Path, output_path: Path, *, input_mode: str, settings, temp_dir: Path) -> dict:
        if np is None or librosa is None:
            return {
                "outputPath": source_path,
                "applied": False,
                "note": "Pitch correction dependencies are missing. Install numpy/librosa/pretty_midi to enable automatic tuning.",
                "analysis": {},
                "warnings": [],
            }

        analysis = self._extract_pitch(source_path)
        if not analysis["segments"]:
            return {
                "outputPath": source_path,
                "applied": False,
                "note": "No stable pitched segments were detected. Pitch correction was skipped.",
                "analysis": analysis,
                "warnings": [],
            }

        warnings: list[str] = []
        pitch_mode_used = settings.pitchMode

        if pitch_mode_used == "midi_reference":
            midi_notes = self._load_midi_notes(settings.midiPath)
            if midi_notes:
                self._apply_midi_targets(analysis["segments"], midi_notes, analysis["duration_seconds"])
            else:
                warnings.append("MIDI reference could not be parsed. Falling back to auto-scale pitch correction.")
                pitch_mode_used = "auto_scale"

        elif pitch_mode_used == "reference_vocal":
            reference_result = self._apply_reference_vocal_targets(
                source_segments=analysis["segments"],
                source_duration=analysis["duration_seconds"],
                reference_path=settings.referencePath,
            )
            warnings.extend(reference_result["warnings"])
            analysis["reference_alignment"] = reference_result["alignment"]
            if not reference_result["applied"]:
                pitch_mode_used = "auto_scale"

        if pitch_mode_used == "auto_scale":
            scale = self._estimate_scale(analysis["segments"])
            self._apply_auto_targets(analysis["segments"], scale, settings.pitchStyle, settings.pitchStrength)
            analysis["estimated_scale"] = scale

        rendered = await self._render_segments(
            source_path=source_path,
            output_path=output_path,
            temp_dir=temp_dir,
            segments=analysis["segments"],
            style=settings.pitchStyle,
            strength=settings.pitchStrength,
        )

        applied = rendered["corrected_segments"] > 0
        if not applied:
            return {
                "outputPath": source_path,
                "applied": False,
                "note": "Detected notes were already close to target pitch, so no correction was rendered.",
                "analysis": analysis,
                "warnings": warnings,
            }

        note = self._build_result_note(pitch_mode_used, settings.pitchStyle, rendered["corrected_segments"], analysis)
        return {
            "outputPath": output_path,
            "applied": True,
            "note": note,
            "analysis": analysis,
            "warnings": warnings,
        }

    def _extract_pitch(self, source_path: Path) -> dict:
        audio, sr = librosa.load(source_path, sr=self.analysis_sr, mono=True)
        frame_times, frequencies, confidence = self._track_pitch(audio, sr)
        segments = self._segment_pitch_track(frame_times, frequencies, confidence)
        return {
            "engine": "crepe" if crepe_lib is not None else "librosa.pyin",
            "duration_seconds": float(len(audio) / sr),
            "segments": segments,
        }

    def _track_pitch(self, audio, sr):
        if crepe_lib is not None:
            time_axis, frequency, confidence, _ = crepe_lib.predict(
                audio,
                sr,
                viterbi=True,
                step_size=20,
                model_capacity="small",
                verbose=0,
            )
            frequency = np.asarray(frequency, dtype=float)
            confidence = np.asarray(confidence, dtype=float)
            frequency[confidence < 0.45] = np.nan
            return np.asarray(time_axis, dtype=float), frequency, confidence

        frequencies, voiced_flag, voiced_prob = librosa.pyin(
            audio,
            fmin=self.min_voiced_hz,
            fmax=self.max_voiced_hz,
            sr=sr,
            frame_length=2048,
            hop_length=self.hop_length,
        )
        frame_times = librosa.times_like(frequencies, sr=sr, hop_length=self.hop_length)
        confidence = np.nan_to_num(voiced_prob if voiced_prob is not None else voiced_flag.astype(float), nan=0.0)
        return np.asarray(frame_times, dtype=float), np.asarray(frequencies, dtype=float), np.asarray(confidence, dtype=float)

    def _segment_pitch_track(self, frame_times, frequencies, confidence) -> list[PitchSegment]:
        segments: list[PitchSegment] = []
        if len(frame_times) == 0:
            return segments
        frame_duration = float(np.median(np.diff(frame_times))) if len(frame_times) > 1 else 0.02
        voiced = ~np.isnan(frequencies)
        start_index = 0
        for index in range(1, len(frame_times) + 1):
            at_boundary = index == len(frame_times) or voiced[index] != voiced[start_index]
            if not at_boundary:
                continue
            start_time = float(frame_times[start_index])
            end_time = float(frame_times[index - 1] + frame_duration)
            if voiced[start_index]:
                segment_freq = frequencies[start_index:index]
                segment_conf = confidence[start_index:index]
                cleaned = segment_freq[~np.isnan(segment_freq)]
                if len(cleaned):
                    midi_values = librosa.hz_to_midi(cleaned)
                    if end_time - start_time >= 0.08:
                        segments.append(
                            PitchSegment(
                                start=start_time,
                                end=end_time,
                                voiced=True,
                                source_midi=float(np.median(midi_values)),
                                confidence=float(np.mean(segment_conf)),
                            )
                        )
            else:
                if end_time - start_time >= 0.04:
                    segments.append(PitchSegment(start=start_time, end=end_time, voiced=False, confidence=0.0))
            start_index = index
        return segments

    def _estimate_scale(self, segments: list[PitchSegment]) -> dict:
        major_template = {0, 2, 4, 5, 7, 9, 11}
        minor_template = {0, 2, 3, 5, 7, 8, 10}
        best = {"root": 0, "mode": "major", "score": -1.0, "pitch_classes": major_template}
        voiced = [segment for segment in segments if segment.voiced and segment.source_midi is not None]
        histogram = {pitch_class: 0.0 for pitch_class in range(12)}
        for segment in voiced:
            pitch_class = int(round(segment.source_midi)) % 12
            histogram[pitch_class] += max(segment.confidence, 0.1) * (segment.end - segment.start)
        for root in range(12):
            for mode, template in (("major", major_template), ("minor", minor_template)):
                score = 0.0
                shifted = {(root + degree) % 12 for degree in template}
                for pitch_class, value in histogram.items():
                    score += value if pitch_class in shifted else value * -0.45
                if score > best["score"]:
                    best = {"root": root, "mode": mode, "score": score, "pitch_classes": shifted}
        return best

    def _apply_auto_targets(self, segments: list[PitchSegment], scale: dict, style: str, strength: int) -> None:
        threshold_cents = 35 if style == "natural" else 8
        snap_ratio = 0.42 + (strength / 100.0) * (0.5 if style == "natural" else 0.58)
        for segment in segments:
            if not segment.voiced or segment.source_midi is None:
                continue
            source = segment.source_midi
            nearest_in_scale = self._nearest_scale_midi(source, scale["pitch_classes"])
            diff_cents = (nearest_in_scale - source) * 100.0
            if abs(diff_cents) < threshold_cents:
                segment.target_midi = source
            else:
                segment.target_midi = source + (nearest_in_scale - source) * snap_ratio

    def _load_midi_notes(self, midi_path: str | None) -> list[dict]:
        if not midi_path or pretty_midi is None:
            return []
        midi = pretty_midi.PrettyMIDI(midi_path)
        notes = []
        for instrument in midi.instruments:
            if instrument.is_drum:
                continue
            for note in instrument.notes:
                notes.append({"start": note.start, "end": note.end, "pitch": float(note.pitch)})
        return sorted(notes, key=lambda item: item["start"])

    def _apply_midi_targets(self, segments: list[PitchSegment], midi_notes: list[dict], vocal_duration: float) -> None:
        voiced_segments = [segment for segment in segments if segment.voiced and segment.source_midi is not None]
        if not voiced_segments or not midi_notes:
            return
        midi_duration = max(note["end"] for note in midi_notes) or 1.0
        for segment in voiced_segments:
            midpoint = (segment.start + segment.end) / 2
            mapped_time = (midpoint / max(vocal_duration, 0.001)) * midi_duration
            nearest_note = min(midi_notes, key=lambda note: abs(((note["start"] + note["end"]) / 2) - mapped_time))
            segment.target_midi = nearest_note["pitch"]

    def _apply_reference_vocal_targets(self, source_segments: list[PitchSegment], source_duration: float, reference_path: str | None) -> dict:
        if not reference_path:
            return {
                "applied": False,
                "warnings": ["Reference vocal mode requires a reference vocal file. Falling back to auto-scale pitch correction."],
                "alignment": {},
            }

        reference_analysis = self._extract_pitch(Path(reference_path))
        reference_segments = self._smooth_reference_segments(reference_analysis["segments"])
        voiced_source = [segment for segment in source_segments if segment.voiced and segment.source_midi is not None]
        voiced_reference = [segment for segment in reference_segments if segment.voiced and segment.source_midi is not None]

        warnings: list[str] = []
        if not voiced_reference:
            warnings.append("Reference vocal did not contain stable pitched notes. Falling back to auto-scale pitch correction.")
            return {"applied": False, "warnings": warnings, "alignment": {"matchedSegments": 0, "coverage": 0.0}}

        duration_ratio = reference_analysis["duration_seconds"] / max(source_duration, 0.001)
        if duration_ratio < 0.6 or duration_ratio > 1.67:
            warnings.append("Reference vocal duration differs too much from the target vocal. Falling back to auto-scale pitch correction.")
            return {
                "applied": False,
                "warnings": warnings,
                "alignment": {"matchedSegments": 0, "coverage": 0.0, "durationRatio": duration_ratio},
            }

        matches = self._align_reference_segments(voiced_source, voiced_reference)
        if not matches:
            warnings.append("Reference vocal alignment coverage was too low. Falling back to auto-scale pitch correction.")
            return {"applied": False, "warnings": warnings, "alignment": {"matchedSegments": 0, "coverage": 0.0}}

        matched_duration = 0.0
        large_octave_jumps = 0
        for source_index, reference_index in matches:
            source_segment = voiced_source[source_index]
            reference_segment = voiced_reference[reference_index]
            diff = reference_segment.source_midi - source_segment.source_midi
            if abs(diff) >= 7.0:
                large_octave_jumps += 1
                continue
            source_segment.target_midi = self._blend_reference_target(source_segment, reference_segment)
            matched_duration += source_segment.end - source_segment.start

        coverage = matched_duration / max(sum(segment.end - segment.start for segment in voiced_source), 0.001)
        if coverage < 0.42:
            warnings.append("Reference vocal alignment coverage was too low. Falling back to auto-scale pitch correction.")
            return {
                "applied": False,
                "warnings": warnings,
                "alignment": {"matchedSegments": len(matches), "coverage": coverage, "durationRatio": duration_ratio},
            }
        if large_octave_jumps > max(2, len(matches) // 3):
            warnings.append("Reference vocal alignment produced too many large pitch jumps. Falling back to auto-scale pitch correction.")
            return {
                "applied": False,
                "warnings": warnings,
                "alignment": {
                    "matchedSegments": len(matches),
                    "coverage": coverage,
                    "durationRatio": duration_ratio,
                    "octaveJumpRejects": large_octave_jumps,
                },
            }

        return {
            "applied": True,
            "warnings": warnings,
            "alignment": {
                "matchedSegments": len(matches),
                "coverage": coverage,
                "durationRatio": duration_ratio,
                "octaveJumpRejects": large_octave_jumps,
                "referenceEngine": reference_analysis["engine"],
            },
        }

    def _smooth_reference_segments(self, segments: list[PitchSegment]) -> list[PitchSegment]:
        voiced = [segment for segment in segments if segment.voiced and segment.source_midi is not None]
        if len(voiced) < 3:
            return segments
        midi_values = [segment.source_midi for segment in voiced]
        smoothed = []
        for index, value in enumerate(midi_values):
            left = midi_values[max(index - 1, 0)]
            right = midi_values[min(index + 1, len(midi_values) - 1)]
            smoothed.append((left + value + right) / 3.0)
        smoothed_index = 0
        for segment in segments:
            if segment.voiced and segment.source_midi is not None:
                segment.source_midi = smoothed[smoothed_index]
                smoothed_index += 1
        return segments

    def _align_reference_segments(self, source_segments: list[PitchSegment], reference_segments: list[PitchSegment]) -> list[tuple[int, int]]:
        if not source_segments or not reference_segments:
            return []
        if librosa_dtw is None:
            return self._note_anchor_alignment(source_segments, reference_segments)

        source_features = np.asarray([
            [segment.source_midi, (segment.start + segment.end) / 2, segment.end - segment.start]
            for segment in source_segments
        ], dtype=float).T
        reference_features = np.asarray([
            [segment.source_midi, (segment.start + segment.end) / 2, segment.end - segment.start]
            for segment in reference_segments
        ], dtype=float).T
        _, path = librosa_dtw(X=source_features, Y=reference_features, metric="euclidean")
        path = path[::-1]
        matches: list[tuple[int, int]] = []
        seen_source = set()
        seen_reference = set()
        for source_index, reference_index in path:
            if source_index in seen_source or reference_index in seen_reference:
                continue
            matches.append((int(source_index), int(reference_index)))
            seen_source.add(int(source_index))
            seen_reference.add(int(reference_index))
        matches.sort(key=lambda item: item[0])
        return matches

    def _note_anchor_alignment(self, source_segments: list[PitchSegment], reference_segments: list[PitchSegment]) -> list[tuple[int, int]]:
        matches: list[tuple[int, int]] = []
        used_reference = set()
        source_total = max(source_segments[-1].end, 0.001)
        reference_total = max(reference_segments[-1].end, 0.001)
        for source_index, source_segment in enumerate(source_segments):
            source_mid = ((source_segment.start + source_segment.end) / 2) / source_total
            best_reference = None
            best_score = None
            for reference_index, reference_segment in enumerate(reference_segments):
                if reference_index in used_reference:
                    continue
                reference_mid = ((reference_segment.start + reference_segment.end) / 2) / reference_total
                duration_gap = abs((source_segment.end - source_segment.start) - (reference_segment.end - reference_segment.start))
                pitch_gap = abs(reference_segment.source_midi - source_segment.source_midi)
                score = abs(source_mid - reference_mid) * 3.0 + duration_gap * 0.6 + pitch_gap * 0.08
                if best_score is None or score < best_score:
                    best_score = score
                    best_reference = reference_index
            if best_reference is not None and best_score is not None and best_score < 1.25:
                matches.append((source_index, best_reference))
                used_reference.add(best_reference)
        return matches

    def _blend_reference_target(self, source_segment: PitchSegment, reference_segment: PitchSegment) -> float:
        source = source_segment.source_midi or 0.0
        target = reference_segment.source_midi or source
        raw_shift = target - source
        limited = max(min(raw_shift, 2.5), -2.5)
        return source + limited * 0.9

    def _nearest_scale_midi(self, midi_value: float, pitch_classes: set[int]) -> float:
        candidates = []
        rounded = int(round(midi_value))
        for candidate in range(rounded - 6, rounded + 7):
            if candidate % 12 in pitch_classes:
                candidates.append(candidate)
        return float(min(candidates, key=lambda item: abs(item - midi_value))) if candidates else float(round(midi_value))

    async def _render_segments(self, source_path: Path, output_path: Path, temp_dir: Path, segments: list[PitchSegment], style: str, strength: int) -> dict:
        manifest_path = temp_dir / "pitch-concat.txt"
        segment_paths: list[Path] = []
        corrected_segments = 0
        for index, segment in enumerate(segments):
            segment_path = temp_dir / f"pitch-segment-{index:04d}.wav"
            duration = max(segment.end - segment.start, 0.02)
            shift = self._segment_shift(segment, style, strength)
            if abs(shift) < 0.03 or not segment.voiced:
                await run_ffmpeg([
                    "-ss", f"{segment.start:.5f}",
                    "-t", f"{duration:.5f}",
                    "-i", str(source_path),
                    "-ac", "2",
                    "-ar", "48000",
                    str(segment_path),
                ])
            else:
                corrected_segments += 1
                pitch_ratio = 2 ** (shift / 12.0)
                await run_ffmpeg([
                    "-ss", f"{segment.start:.5f}",
                    "-t", f"{duration:.5f}",
                    "-i", str(source_path),
                    "-af", f"rubberband=pitch={pitch_ratio:.6f}:formant=preserved:transients=smooth:pitchq=quality",
                    "-ac", "2",
                    "-ar", "48000",
                    str(segment_path),
                ])
            segment_paths.append(segment_path)

        manifest_path.write_text("".join(f"file '{path.as_posix()}'\n" for path in segment_paths), encoding="utf-8")
        await run_ffmpeg([
            "-f", "concat",
            "-safe", "0",
            "-i", str(manifest_path),
            "-c:a", "pcm_s16le",
            str(output_path),
        ])
        return {"corrected_segments": corrected_segments}

    def _segment_shift(self, segment: PitchSegment, style: str, strength: int) -> float:
        if segment.source_midi is None or segment.target_midi is None:
            return 0.0
        raw_shift = segment.target_midi - segment.source_midi
        if style == "natural":
            limited = max(min(raw_shift, 1.5), -1.5)
            return limited * (0.35 + (strength / 100.0) * 0.45)
        limited = max(min(raw_shift, 4.0), -4.0)
        return limited * (0.75 + (strength / 100.0) * 0.25)

    def _build_result_note(self, pitch_mode: str, pitch_style: str, corrected_segments: int, analysis: dict) -> str:
        engine = analysis.get("engine", "unknown")
        if pitch_mode == "midi_reference":
            return f"Pitch correction rendered with {engine} tracking and MIDI-guided note anchoring across {corrected_segments} segments."
        if pitch_mode == "reference_vocal":
            alignment = analysis.get("reference_alignment") or {}
            coverage = alignment.get("coverage", 0.0)
            return f"Pitch correction rendered with {engine} tracking and reference-vocal alignment across {corrected_segments} segments (coverage {coverage:.0%})."
        if pitch_style == "autotune":
            return f"Pitch correction rendered with {engine} tracking in Auto-Tune style across {corrected_segments} segments."
        scale = analysis.get("estimated_scale") or {}
        root = scale.get("root")
        mode = scale.get("mode")
        if root is None:
            return f"Pitch correction rendered with {engine} tracking across {corrected_segments} segments."
        return f"Pitch correction rendered with {engine} tracking, estimated {NOTE_NAMES[root]} {mode}, across {corrected_segments} segments."
