"""Colors and sizes shared by every screen (same palette as the design mockups)."""

# Summer palette: warm sand background, ocean-turquoise primary, coral accent, sunny yellow highlights.
BG = "#FFF6E5"
CARD = "#FFFFFF"
LINE = "#F4E4C8"
SOFT = "#FFEFD0"
INK = "#14284B"
MUTED = "#5A6A85"
FAINT = "#8D9BB3"

PRIMARY = "#0891B2"
PRIMARY_SOFT = "#D5F3FA"
ACCENT = "#FF6B4A"          # floating add button
SUN = "#FFC53D"
HERO = "#0B3C5D"            # dark text colour used on light chips over the hero gradient
HERO_GRAD = ("#0891B2", "#2F6BEA")
HERO_CARD = "#1E5FA8"
HERO_TEXT = "#E4F7FF"
MINT = "#C8FFE0"

INCOME = "#0E9F6E"
EXPENSE = "#E5484D"
TRANSFER = "#3B82F6"

# chart palette: bright but still separable
CHART_INCOME = "#06B6D4"
CHART_EXPENSE = "#FF7A59"
SERIES = ["#06B6D4", "#FF7A59", "#FFC53D", "#8E6CEF", "#FF5C8A", "#2EC27E", "#3A86FF"]
from ..palette import VIVID, vivid  # noqa: E402,F401

TONE = {  # tone -> (text colour, background)
    "income": (INCOME, "#D9F7EA"),
    "expense": (EXPENSE, "#FFE3E1"),
    "neutral": (MUTED, SOFT),
    "good": ("#0B4A3D", "#D9F7EA"),
    "bad": ("#8A1C12", "#FFE3E1"),
    "warn": ("#7A4A00", "#FFF0C2"),
    "info": ("#0B3C5D", "#D5F3FA"),
    "debt": ("#8A1C12", "#FFE3E1"),       # I owe: red
    "owed": ("#7A4A00", "#FFF0C2"),       # owed to me: amber
    "paid": ("#0B4A3D", "#D9F7EA"),       # settled / collected: green
}
TONE_ICON = {"good": "#0E9F6E", "warn": "#E0A100", "bad": "#E5484D", "info": "#0891B2"}

DEFAULT_WIDTH = 390  # used until the real window width is known
