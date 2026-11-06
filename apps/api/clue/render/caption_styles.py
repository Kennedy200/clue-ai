"""Caption style presets (the editor's style picker). Each is a partial CaptionStyle."""
from .scene import CaptionStyle

PRESETS: dict[str, dict] = {
    "bold-highlight": {"label": "Bold highlight", "color": "FFFFFF", "highlight": "C8FF3D", "outline": "000000", "outline_width": 7},
    "classic": {"label": "Classic", "color": "FFFFFF", "highlight": "FFFFFF", "outline": "000000", "outline_width": 6, "highlight_mode": "none", "words_per_chunk": 5},
    "yellow-box": {"label": "Yellow box", "color": "111111", "highlight": "FFFFFF", "outline": "FFD400", "box": True, "outline_width": 14, "words_per_chunk": 3},
    "lime-box": {"label": "Lime box", "color": "0E0B1F", "highlight": "FFFFFF", "outline": "C8FF3D", "box": True, "outline_width": 14, "words_per_chunk": 3, "uppercase": True},
    "karaoke": {"label": "Karaoke", "color": "FFFFFF", "highlight": "FF5C7A", "outline": "0E0B1F", "outline_width": 8, "words_per_chunk": 5},
    "neon": {"label": "Neon", "color": "E8F9FF", "highlight": "00E5FF", "outline": "1B0B4D", "outline_width": 9, "uppercase": True},
    "pop-single": {"label": "One word pop", "color": "FFFFFF", "highlight": "C8FF3D", "outline": "000000", "outline_width": 9, "words_per_chunk": 1, "size": 130, "uppercase": True, "animate": "pop", "position": "middle"},
    "minimal": {"label": "Minimal", "color": "FFFFFF", "highlight": "FFFFFF", "outline": "000000", "outline_width": 3, "size": 62, "highlight_mode": "none", "words_per_chunk": 6},
    "violet-box": {"label": "Violet box", "color": "FFFFFF", "highlight": "C8FF3D", "outline": "6C4DFF", "box": True, "outline_width": 14, "words_per_chunk": 3},
    "heavy-outline": {"label": "Heavy outline", "color": "FFFFFF", "highlight": "FFD400", "outline": "000000", "outline_width": 12, "size": 96, "words_per_chunk": 3, "uppercase": True},
}


def preset(name: str, **overrides) -> CaptionStyle:
    base = {k: v for k, v in PRESETS.get(name, PRESETS["bold-highlight"]).items() if k != "label"}
    return CaptionStyle(name=name, **{**base, **overrides})
