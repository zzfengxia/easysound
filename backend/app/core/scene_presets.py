SCENE_PRESETS = {
    "studio": {
        "id": "studio",
        "name": "录音棚",
        "description": "空间感克制、清晰自然，适合贴近成品唱片的听感。",
        "accent": "#0f766e",
        "chain": [
            "highpass=f=80",
            "equalizer=f=200:t=q:w=1.0:g=-2",
            "equalizer=f=3200:t=q:w=1.2:g=2",
            "aecho=0.80:0.70:28|56|84:0.18|0.11|0.07",
            "stereowiden=delay=14:feedback=0.22:crossfeed=0.10:drymix=0.88",
        ],
    },
    "concert": {
        "id": "concert",
        "name": "音乐会现场",
        "description": "更开阔的尾音和轻微观众空间感，突出舞台现场氛围。",
        "accent": "#ea580c",
        "chain": [
            "highpass=f=70",
            "equalizer=f=2800:t=q:w=1.0:g=2.2",
            "aecho=0.86:0.78:70|140|220|320:0.34|0.26|0.18|0.12",
            "stereowiden=delay=26:feedback=0.38:crossfeed=0.14:drymix=0.80",
            "alimiter=limit=0.92",
        ],
    },
    "bar": {
        "id": "bar",
        "name": "酒吧驻唱",
        "description": "更暖、更近的人声包围感，模拟小型演出空间。",
        "accent": "#7c3aed",
        "chain": [
            "highpass=f=75",
            "lowshelf=f=180:g=1.4",
            "treble=g=1.0",
            "aecho=0.82:0.72:42|84|126:0.28|0.20|0.12",
            "extrastereo=m=1.72",
        ],
    },
    "theater": {
        "id": "theater",
        "name": "小剧场",
        "description": "保留清晰度的同时增加纵深感，适合叙事和抒情类演唱。",
        "accent": "#b45309",
        "chain": [
            "highpass=f=75",
            "equalizer=f=260:t=q:w=1.1:g=-1.5",
            "equalizer=f=4200:t=q:w=1.4:g=1.5",
            "aecho=0.82:0.70:40|80|120|170:0.22|0.15|0.10|0.06",
            "haas",
        ],
    },
}

DEFAULT_SCENE_PRESET = "concert"


def list_scene_presets() -> list[dict]:
    return list(SCENE_PRESETS.values())


def get_scene_preset(preset_id: str | None) -> dict:
    if preset_id and preset_id in SCENE_PRESETS:
        return SCENE_PRESETS[preset_id]
    return SCENE_PRESETS[DEFAULT_SCENE_PRESET]
