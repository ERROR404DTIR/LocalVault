"""Colors and fonts. Every color is a (light, dark) pair understood by customtkinter."""
from __future__ import annotations

import sys

import customtkinter as ctk

BG = ("#EEF2F7", "#0B131D")
PANEL = ("#FFFFFF", "#121E2D")
RAISED = ("#E4EBF4", "#192A3E")
RAISED_HOVER = ("#D5DFEB", "#223750")
LINE = ("#C9D5E3", "#263B55")
TEXT = ("#142033", "#E6EDF5")
MUTED = ("#5B6E86", "#8FA3BA")
BRASS = ("#B97F0E", "#F2B544")
BRASS_HOVER = ("#9C6A08", "#FFC85F")
ON_BRASS = ("#FFFFFF", "#1A1204")
TEAL = ("#0E8F86", "#4FD1C5")
DANGER = ("#C2352F", "#F2706B")
DANGER_HOVER = ("#A22A25", "#FF8A85")

STRENGTH_COLORS = ["#E5484D", "#F2884B", "#F2B544", "#7BC96F", "#3FB68B"]

if sys.platform.startswith("win"):
    UI_FAMILY, MONO_FAMILY = "Segoe UI", "Consolas"
elif sys.platform == "darwin":
    UI_FAMILY, MONO_FAMILY = "Helvetica Neue", "Menlo"
else:
    UI_FAMILY, MONO_FAMILY = "DejaVu Sans", "DejaVu Sans Mono"


def ui(size: int = 13, bold: bool = False) -> ctk.CTkFont:
    return ctk.CTkFont(family=UI_FAMILY, size=size, weight="bold" if bold else "normal")


def mono(size: int = 13, bold: bool = False) -> ctk.CTkFont:
    return ctk.CTkFont(family=MONO_FAMILY, size=size, weight="bold" if bold else "normal")


def resolve(color: tuple[str, str] | str) -> str:
    """Pick the concrete color for the current appearance mode (for raw tkinter widgets)."""
    if isinstance(color, str):
        return color
    return color[1] if ctk.get_appearance_mode() == "Dark" else color[0]


def apply() -> None:
    """Restyle customtkinter's default widgets so they match the LocalVault palette."""
    tm = ctk.ThemeManager.theme
    L = list
    tm["CTkEntry"].update(fg_color=L(RAISED), border_color=L(LINE), text_color=L(TEXT),
                          placeholder_text_color=L(MUTED), border_width=1)
    tm["CTkTextbox"].update(fg_color=L(RAISED), border_color=L(LINE), text_color=L(TEXT))
    tm["CTkComboBox"].update(fg_color=L(RAISED), border_color=L(LINE), button_color=L(RAISED_HOVER),
                             button_hover_color=L(LINE), text_color=L(TEXT))
    tm["CTkSegmentedButton"].update(selected_color=["#2F5D8A", "#2C4F78"], selected_hover_color=["#2A5481", "#35608E"],
                                    unselected_color=["#7B8EA8", "#192A3E"], unselected_hover_color=["#6A7E99", "#223750"],
                                    text_color=["#FFFFFF", "#E6EDF5"])
    tm["CTkSwitch"].update(progress_color=L(BRASS))
    tm["CTkSlider"].update(progress_color=L(BRASS), button_color=L(BRASS), button_hover_color=L(BRASS_HOVER))
    tm["CTkProgressBar"].update(fg_color=L(LINE))
