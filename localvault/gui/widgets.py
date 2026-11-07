from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from ..generator import estimate_entropy, strength_label
from . import theme as T


class StrengthBar(ctk.CTkFrame):
    """Four-segment strength meter with a text label underneath."""

    def __init__(self, master, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.segments = []
        for i in range(4):
            seg = ctk.CTkFrame(self, width=78, height=5, corner_radius=3, fg_color=T.LINE)
            seg.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 3, 0))
            self.columnconfigure(i, weight=1)
            self.segments.append(seg)
        self.label = ctk.CTkLabel(self, text="", font=T.ui(12), text_color=T.MUTED, anchor="w")
        self.label.grid(row=1, column=0, columnspan=4, sticky="w", pady=(4, 0))

    def set_password(self, password: str) -> None:
        if not password:
            for seg in self.segments:
                seg.configure(fg_color=T.LINE)
            self.label.configure(text="")
            return
        bits = estimate_entropy(password)
        name, score = strength_label(bits)
        lit = max(1, score)
        for i, seg in enumerate(self.segments):
            seg.configure(fg_color=T.STRENGTH_COLORS[score] if i < lit else T.LINE)
        self.label.configure(text=f"{name} ({bits:.0f} bits)")


class LockIcon(tk.Canvas):
    """A small padlock drawn on a canvas. `unlock()` lifts the shackle; `shake()` signals an error."""

    def __init__(self, master, size: int = 84, bg=T.PANEL):
        super().__init__(master, width=size, height=size, bg=T.resolve(bg), highlightthickness=0)
        self.size = size
        self.lift = 0
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        brass, ink = T.resolve(T.BRASS), T.resolve(T.PANEL)
        lift = self.lift
        self.create_line(26, 38 - lift, 26, 24 - lift, width=7, fill=brass, capstyle="round")
        self.create_arc(26, 8 - lift, 58, 40 - lift, start=0, extent=180, style="arc", width=7, outline=brass)
        self.create_line(58, 24 - lift, 58, 38 if lift < 6 else 24 - lift + 4, width=7, fill=brass, capstyle="round")
        self.create_rectangle(16, 38, 68, 76, fill=brass, outline=brass, width=2)
        self.create_oval(36, 48, 48, 60, fill=ink, outline=ink)
        self.create_rectangle(40, 56, 44, 68, fill=ink, outline=ink)

    def unlock(self, done=None, step: int = 0) -> None:
        if step > 10:
            if done:
                done()
            return
        self.lift = step
        self._draw()
        self.after(22, lambda: self.unlock(done, step + 1))

    def shake(self, i: int = 0) -> None:
        offsets = [10, -20, 16, -12, 8, -4, 2]
        if i >= len(offsets):
            self._draw()
            return
        self.move("all", offsets[i], 0)
        self.after(35, lambda: self.shake(i + 1))
