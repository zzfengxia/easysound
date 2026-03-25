from app.core.scene_presets import get_scene_preset, list_scene_presets


def test_scene_presets_include_expected_launch_presets():
    preset_ids = sorted(preset["id"] for preset in list_scene_presets())
    assert preset_ids == ["bar", "concert", "studio", "theater"]


def test_unknown_scene_preset_falls_back_to_concert():
    assert get_scene_preset("missing")["id"] == "concert"
