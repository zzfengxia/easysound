from app.providers.audio_provider import FfmpegAudioProvider
from app.providers.pitch_provider import AutoPitchProvider


def create_providers() -> dict:
    return {
        "audio": FfmpegAudioProvider(),
        "pitch": AutoPitchProvider(),
    }
