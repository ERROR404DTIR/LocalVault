from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from .. import generator as G
from .. import totp as TOTP
from ..vault import Entry
from . import theme as T
from .generator_view import GeneratorPanel
from .widgets import StrengthBar


class EntryDialog(ctk.CTkToplevel):
    def __init__(self, app, entry: Entry | None = None, folder: str = "", on_saved=None):
        super().__init__(app)
        self.app = app
        self.entry = entry
        self.on_saved = on_saved
        self.title("Edit item" if entry else "New item")
        self.geometry("500x760")
        self.minsize(460, 620)
        self.configure(fg_color=T.BG)
        self.transient(app)
        self.after(200, self._grab)

        e = entry or Entry(folder=folder)
        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=(12, 0))

        self.kind = ctk.StringVar(value="Secure note" if e.kind == "note" else "Login")
        ctk.CTkSegmentedButton(body, values=["Login", "Secure note"], variable=self.kind,
                               command=lambda _v: self._kind_changed()).pack(fill="x", padx=8, pady=(4, 12))

        self.title_e = self._field(body, "Name", e.title)
        self.login_box = ctk.CTkFrame(body, fg_color="transparent")
        self.login_box.pack(fill="x")
        self.user_e = self._field(self.login_box, "Username or email", e.username)

        ctk.CTkLabel(self.login_box, text="Password", font=T.ui(12), text_color=T.MUTED).pack(anchor="w", padx=10, pady=(10, 2))
        row = ctk.CTkFrame(self.login_box, fg_color="transparent")
        row.pack(fill="x", padx=8)
        self.pw_e = ctk.CTkEntry(row, height=38, show="•", font=T.mono(13))
        self.pw_e.pack(side="left", fill="x", expand=True)
        self.pw_e.insert(0, e.password)
        self.pw_e.bind("<KeyRelease>", lambda _e: self.strength.set_password(self.pw_e.get()))
        self.show = ctk.CTkButton(row, text="Show", width=58, height=38, fg_color=T.RAISED, hover_color=T.RAISED_HOVER,
                                  text_color=T.TEXT, command=self._toggle_show)
        self.show.pack(side="left", padx=(6, 0))
        ctk.CTkButton(row, text="Generate", width=78, height=38, fg_color=T.BRASS, hover_color=T.BRASS_HOVER,
                      text_color=T.ON_BRASS, command=self._quick_generate).pack(side="left", padx=(6, 0))
        ctk.CTkButton(self.login_box, text="Generator options…", height=26, fg_color="transparent", hover=False,
                      text_color=T.BRASS, anchor="w", command=self._open_generator).pack(anchor="w", padx=4)
        self.strength = StrengthBar(self.login_box)
        self.strength.pack(fill="x", padx=10)
        self.strength.set_password(e.password)

        self.url_e = self._field(self.login_box, "Website", e.url)
        self.totp_e = self._field(self.login_box, "Authenticator key (TOTP secret or otpauth:// link)", e.totp)

        self.folder_label = ctk.CTkLabel(body, text="Folder", font=T.ui(12), text_color=T.MUTED)
        self.folder_label.pack(anchor="w", padx=10, pady=(10, 2))
        self.folder_e = ctk.CTkComboBox(body, values=[""] + app.vault.folders, height=38)
        self.folder_e.pack(fill="x", padx=8)
        self.folder_e.set(e.folder)

        ctk.CTkLabel(body, text="Notes", font=T.ui(12), text_color=T.MUTED).pack(anchor="w", padx=10, pady=(10, 2))
        self.notes_e = ctk.CTkTextbox(body, height=110, border_width=1, border_color=T.LINE)
        self.notes_e.pack(fill="x", padx=8)
        self.notes_e.insert("1.0", e.notes)

        self.fav = ctk.BooleanVar(value=e.favorite)
        ctk.CTkSwitch(body, text="Favorite", variable=self.fav, progress_color=T.BRASS).pack(anchor="w", padx=10, pady=14)

        self.error = ctk.CTkLabel(self, text="", text_color=T.DANGER, font=T.ui(13))
        self.error.pack(pady=(4, 0))
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=20, pady=14)
        ctk.CTkButton(bar, text="Cancel", width=100, height=40, fg_color=T.RAISED, hover_color=T.RAISED_HOVER,
                      text_color=T.TEXT, command=self.destroy).pack(side="right")
        ctk.CTkButton(bar, text="Save", width=120, height=40, fg_color=T.BRASS, hover_color=T.BRASS_HOVER,
                      text_color=T.ON_BRASS, font=T.ui(13, True), command=self._save).pack(side="right", padx=8)
        self._kind_changed()
        self.title_e.focus_set()

    def _grab(self) -> None:
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _field(self, parent, label: str, value: str):
        ctk.CTkLabel(parent, text=label, font=T.ui(12), text_color=T.MUTED).pack(anchor="w", padx=10, pady=(10, 2))
        entry = ctk.CTkEntry(parent, height=38)
        entry.pack(fill="x", padx=8)
        entry.insert(0, value)
        return entry

    def _kind_changed(self) -> None:
        if self.kind.get() == "Login":
            self.login_box.pack(fill="x", before=self.folder_label)
        else:
            self.login_box.pack_forget()

    def _toggle_show(self) -> None:
        hidden = self.pw_e.cget("show") == "•"
        self.pw_e.configure(show="" if hidden else "•")
        self.show.configure(text="Hide" if hidden else "Show")

    def _quick_generate(self) -> None:
        self.pw_e.delete(0, "end")
        self.pw_e.insert(0, G.generate_password())
        self.pw_e.configure(show="")
        self.show.configure(text="Hide")
        self.strength.set_password(self.pw_e.get())

    def _open_generator(self) -> None:
        win = ctk.CTkToplevel(self)
        win.title("Generator")
        win.geometry("460x600")
        win.configure(fg_color=T.BG)
        win.transient(self)

        def use(pw: str) -> None:
            self.pw_e.delete(0, "end")
            self.pw_e.insert(0, pw)
            self.strength.set_password(pw)
            win.destroy()

        GeneratorPanel(win, self.app, on_use=use).pack(fill="both", expand=True, padx=20, pady=20)

    def _save(self) -> None:
        is_login = self.kind.get() == "Login"
        title = self.title_e.get().strip()
        if not title:
            self.error.configure(text="Give this item a name.")
            return
        totp_value = self.totp_e.get().strip() if is_login else ""
        if totp_value:
            try:
                TOTP.parse_totp_input(totp_value)
            except TOTP.TOTPError as exc:
                self.error.configure(text=f"Authenticator key: {exc}")
                return
        entry = self.entry or Entry()
        entry.kind = "login" if is_login else "note"
        entry.title = title
        entry.username = self.user_e.get().strip() if is_login else ""
        entry.url = self.url_e.get().strip() if is_login else ""
        entry.totp = totp_value
        entry.folder = self.folder_e.get().strip()
        entry.notes = self.notes_e.get("1.0", "end").rstrip("\n")
        entry.favorite = self.fav.get()
        entry.set_password(self.pw_e.get() if is_login else "")
        if self.entry:
            self.app.vault.update(entry)
        else:
            self.app.vault.add(entry)
        self.destroy()
        if self.on_saved:
            self.on_saved(entry)
