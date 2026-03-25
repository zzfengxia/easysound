import io

import pytest
from fastapi import HTTPException, UploadFile

from app.services.upload_payload import normalize_upload_payload


@pytest.mark.asyncio
async def test_normalize_upload_payload_parses_pitch_flags():
    upload = UploadFile(filename="demo.wav", file=io.BytesIO(b"123"))
    payload, content, midi_content, reference_content = await normalize_upload_payload(
        upload,
        input_mode="vocals_only",
        scene_preset="concert",
        noise_reduction=True,
        pitch_correction=True,
        polish=True,
        scene_enhancement=False,
        pitch_mode="auto_scale",
        pitch_style="autotune",
        pitch_strength=72,
    )

    assert content == b"123"
    assert midi_content is None
    assert reference_content is None
    assert payload["pitch"].pitchMode == "auto_scale"
    assert payload["pitch"].pitchStyle == "autotune"
    assert payload["pitch"].pitchStrength == 72


@pytest.mark.asyncio
async def test_normalize_upload_payload_rejects_bad_extension():
    upload = UploadFile(filename="demo.txt", file=io.BytesIO(b"123"))
    with pytest.raises(HTTPException):
        await normalize_upload_payload(upload)


@pytest.mark.asyncio
async def test_normalize_upload_payload_requires_midi_file_for_midi_mode():
    upload = UploadFile(filename="demo.wav", file=io.BytesIO(b"123"))
    with pytest.raises(HTTPException):
        await normalize_upload_payload(upload, pitch_mode="midi_reference")


@pytest.mark.asyncio
async def test_normalize_upload_payload_accepts_midi_reference_file():
    upload = UploadFile(filename="demo.wav", file=io.BytesIO(b"123"))
    midi = UploadFile(filename="reference.mid", file=io.BytesIO(b"midi"))
    payload, _, midi_content, _ = await normalize_upload_payload(
        upload,
        pitch_mode="midi_reference",
        midi_file=midi,
    )

    assert midi_content == b"midi"
    assert payload["pitch"].midiOriginalName == "reference.mid"


@pytest.mark.asyncio
async def test_normalize_upload_payload_requires_reference_vocal_file_for_reference_mode():
    upload = UploadFile(filename="demo.wav", file=io.BytesIO(b"123"))
    with pytest.raises(HTTPException):
        await normalize_upload_payload(upload, pitch_mode="reference_vocal")


@pytest.mark.asyncio
async def test_normalize_upload_payload_accepts_reference_vocal_file():
    upload = UploadFile(filename="demo.wav", file=io.BytesIO(b"123"))
    reference = UploadFile(filename="guide.wav", file=io.BytesIO(b"guide"))
    payload, _, _, reference_content = await normalize_upload_payload(
        upload,
        pitch_mode="reference_vocal",
        reference_vocal_file=reference,
    )

    assert reference_content == b"guide"
    assert payload["pitch"].referenceOriginalName == "guide.wav"
