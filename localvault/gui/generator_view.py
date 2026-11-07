from __future__ import annotations

import customtkinter as ctk

from .. import generator as G
from . import theme as T
from .widgets import StrengthBar


class GeneratorPanel(ctk.CTkFrame):
    """Password / passphrase generator. When `on_use` is given a "Use this password" button appears."""

    def __init__(self, master, app, on_use=None):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.on_use = on_use
        self.mode = ctk.StringVar(value="Password")

        self.output = ctk.CTkEntry(self, height=54, font=T.mono(18), justify="center")
        self.output.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.output.bind("<KeyRelease>", lambda _e: self._rate())
        self.strength = StrengthBar(self)
        self.strength.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 14))

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=2, column=0, columnspan=2, sticky="ew")
        ctk.CTkButton(buttons, text="Generate", width=120, height=38, fg_color=T.BRASS, hover_color=T.BRASS_HOVER,
                      text_color=T.ON_BRASS, font=T.ui(13, True), command=self.generate).pack(side="left")
        ctk.CTkButton(buttons, text="Copy", width=90, height=38, fg_color=T.RAISED, hover_color=T.RAISED_HOVER,
                      text_color=T.TEXT, command=self._copy).pack(side="left", padx=8)
        if on_use:
            ctk.CTkButton(buttons, text="Use this password", height=38, fg_color=T.TEAL, hover_color=T.TEAL,
                          text_color=T.ON_BRASS, command=lambda: self.on_use(self.output.get())).pack(side="right")

        ctk.CTkSegmentedButton(self, values=["Password", "Passphrase"], variable=self.mode,
                               command=lambda _v: self._switch()).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(18, 10))

        self.options = ctk.CTkFrame(self, fg_color=T.PANEL, corner_radius=12, border_width=1, border_color=T.LINE)
        self.options.grid(row=4, column=0, columnspan=2, sticky="ew")
        self.columnconfigure(0, weight=1)

        # password options
        self.length = ctk.IntVar(value=20)
        self.upper = ctk.BooleanVar(value=True)
        self.lower = ctk.BooleanVar(value=True)
        self.digits = ctk.BooleanVar(value=True)
        self.symbols = ctk.BooleanVar(value=True)
        self.ambiguous = ctk.BooleanVar(value=False)
        # passphrase options
        self.words = ctk.IntVar(value=5)
        self.separator = ctk.StringVar(value="-")
        self.capitalize = ctk.BooleanVar(value=True)
        self.add_number = ctk.BooleanVar(value=False)

        self._switch()

    # ---- UI ----------------------------------------------------------------------------------
    def _slider_row(self, parent, text, var, lo, hi):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(16, 4))
        ctk.CTkLabel(row, text=text, font=T.ui(13), text_color=T.TEXT).pack(side="left")
        value = ctk.CTkLabel(row, text=str(var.get()), font=T.mono(13, True), text_color=T.BRASS, width=36)
        value.pack(side="right")

        def changed(v):
            var.set(int(float(v)))
            value.configure(text=str(var.get()))
            self.generate()

        ctk.CTkSlider(parent, from_=lo, to=hi, number_of_steps=hi - lo, command=changed,
                      progress_color=T.BRASS, button_color=T.BRASS, button_hover_color=T.BRASS_HOVER,
                      variable=var).pack(fill="x", padx=18, pady=(0, 8))

    def _switch_row(self, parent, text, var):
        ctk.CTkSwitch(parent, text=text, variable=var, command=self.generate, progress_color=T.BRASS,
                      font=T.ui(13), text_color=T.TEXT).pack(anchor="w", padx=18, pady=6)

    def _switch(self) -> None:
        for child in self.options.winfo_children():
            child.destroy()
        if self.mode.get() == "Password":
            self._slider_row(self.options, "Length", self.length, 8, 64)
            self._switch_row(self.options, "Uppercase letters (A-Z)", self.upper)
            self._switch_row(self.options, "Lowercase letters (a-z)", self.lower)
            self._switch_row(self.options, "Numbers (0-9)", self.digits)
            self._switch_row(self.options, "Symbols (!@#$%)", self.symbols)
            self._switch_row(self.options, "Avoid look-alike characters (l, 1, O, 0)", self.ambiguous)
        else:
            self._slider_row(self.options, "Words", self.words, 3, 12)
            sep = ctk.CTkFrame(self.options, fg_color="transparent")
            sep.pack(fill="x", padx=18, pady=6)
            ctk.CTkLabel(sep, text="Separator", font=T.ui(13), text_color=T.TEXT).pack(side="left")
            entry = ctk.CTkEntry(sep, textvariable=self.separator, width=60, justify="center")
            entry.pack(side="right")
            entry.bind("<KeyRelease>", lambda _e: self.generate())
            self._switch_row(self.options, "Capitalize words", self.capitalize)
            self._switch_row(self.options, "Add a number", self.add_number)
        ctk.CTkFrame(self.options, height=8, width=1, fg_color=T.PANEL).pack()
        self.generate()

    # ---- behavior ----------------------------------------------------------------------------
    def generate(self) -> None:
        try:
            if self.mode.get() == "Password":
                opts = G.PasswordOptions(
                    length=self.length.get(), upper=self.upper.get(), lower=self.lower.get(),
                    digits=self.digits.get(), symbols=self.symbols.get(), avoid_ambiguous=self.ambiguous.get(),
                )
                text = G.generate_password(opts)
            else:
                text = G.generate_passphrase(self.words.get(), self.separator.get(), self.capitalize.get(),
                                             self.add_number.get())
        except ValueError as exc:
            self.strength.set_password("")
            self.strength.label.configure(text=str(exc))
            return
        self.output.delete(0, "end")
        self.output.insert(0, text)
        self._rate()

    def _rate(self) -> None:
        text = self.output.get()
        self.strength.set_password(text)
        if self.mode.get() == "Passphrase" and text:
            bits = G.passphrase_entropy(self.words.get(), self.add_number.get())
            name, score = G.strength_label(bits)
            self.strength.label.configure(text=f"{name} ({bits:.0f} bits)")
            for i, seg in enumerate(self.strength.segments):
                seg.configure(fg_color=T.STRENGTH_COLORS[score] if i < max(1, score) else T.LINE)

    def _copy(self) -> None:
        self.app.copy(self.output.get(), "Password")


class GeneratorView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        ctk.CTkLabel(self, text="Password generator", font=T.ui(24, True), text_color=T.TEXT).pack(anchor="w", padx=32, pady=(28, 2))
        ctk.CTkLabel(self, text="Generated locally with your operating system's secure random source.",
                     font=T.ui(13), text_color=T.MUTED).pack(anchor="w", padx=32, pady=(0, 20))
        GeneratorPanel(self, app).pack(fill="x", padx=32)
