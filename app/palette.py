"""Bright summer colours shared by the data layer and the UI."""
import zlib

VIVID = ["#FF6B4A", "#06B6D4", "#FFB703", "#8E6CEF", "#2EC27E", "#FF5C8A", "#3A86FF", "#FB8500", "#14B8A6", "#EF476F"]
OLD_GREY = "#8A9A95"  # colour older versions gave every new category


def vivid(name: str) -> str:
    """Stable bright colour for a name."""
    return VIVID[zlib.crc32((name or "").encode("utf-8")) % len(VIVID)]


def pick(color, name: str) -> str:
    """A category's own colour, or a bright one when it has none (or only the old grey)."""
    return vivid(name) if not color or color == OLD_GREY else color
