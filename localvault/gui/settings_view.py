from __future__ import annotations

import time
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .. import __version__, importexport
from ..vault import Vault, VaultError
from . import theme as T
from .widgets import StrengthBar

AUTOLOCK = {"1 minute": 1, "2 minutes": 2, "5 minutes": 5, "10 minutes": 10, "15 minutes": 15, "30 minutes": 30, "Never": 0}
CLIPBOARD = {"10 seconds": 10, "20 seconds": 20, "30 seconds": 30, "60 seconds": 60, "Never": 0}
THEMES = {"Dark": "dark", "Light": "light", "Match system": "system"}


def _key_for(mapping: dict, value) -> str:
    return next((k for k, v in mapping.items() if v == value), next(iter(mapping)))


class SettingsView(ctk.CTkScrollableFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        s = app.vault.settings
        ctk.CTkLabel(self, text="Settings", font=T.ui(24, True), text_color=T.TEXT).pack(anchor="w", padx=32, pady=(28, 12))

        sec = self._card("Security")
        self._option(sec, "Lock automatically after", list(AUTOLOCK), _key_for(AUTOLOCK, s["autolock_minutes"]),
                     lambda v: self._set("autolock_minutes", AUTOLOCK[v]))
        self._option(sec, "Clear copied passwords after", list(CLIPBOARD), _key_for(CLIPBOARD, s["clipboard_clear_seconds"]),
                     lambda v: self._set("clipboard_clear_seconds", CLIPBOARD[v]))
        row = ctk.CTkFrame(sec, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=8)
        self.lock_min = ctk.BooleanVar(value=s["lock_on_minimize"])
        ctk.CTkSwitch(row, text="Lock when the window is minimized", variable=self.lock_min, progress_color=T.BRASS,
                      command=lambda: self._set("lock_on_minimize", self.lock_min.get())).pack(anchor="w")
        ctk.CTkButton(sec, text="Change master password…", height=36, fg_color=T.RAISED, hover_color=T.RAISED_HOVER,
                      text_color=T.TEXT, command=self._change_master).pack(anchor="w", padx=18, pady=(6, 16))

        look = self._card("Appearance")
        self._option(look, "Theme", list(THEMES), _key_for(THEMES, s["theme"]), self._theme)
        ctk.CTkFrame(look, height=10, width=1, fg_color=T.PANEL).pack()

        data = self._card("Your data")
        ctk.CTkLabel(data, text=f"Vault file: {app.vault.path}", font=T.mono(11), text_color=T.MUTED, anchor="w",
                     wraplength=560, justify="left").pack(fill="x", padx=18, pady=(0, 10))
        btns = ctk.CTkFrame(data, fg_color="transparent")
        btns.pack(fill="x", padx=18, pady=(0, 16))
        for text, cmd in (("Import CSV…", self._import), ("Export CSV…", self._export), ("Encrypted backup…", self._backup)):
            ctk.CTkButton(btns, text=text, height=36, fg_color=T.RAISED, hover_color=T.RAISED_HOVER, text_color=T.TEXT,
                          command=cmd).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(data, text="Import understands Bitwarden, Chrome, Edge, Firefox and generic CSV files.",
                     font=T.ui(12), text_color=T.MUTED, anchor="w").pack(fill="x", padx=18, pady=(0, 14))

        about = self._card("About")
        ctk.CTkLabel(about, text=f"LocalVault {__version__}  ·  AES-256-GCM + scrypt  ·  100% offline",
                     font=T.ui(13), text_color=T.MUTED, anchor="w").pack(fill="x", padx=18, pady=(0, 16))

    # ---- helpers -----------------------------------------------------------------------------
    def _card(self, title: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(self, fg_color=T.PANEL, corner_radius=14, border_width=1, border_color=T.LINE)
        card.pack(fill="x", padx=32, pady=8)
        ctk.CTkLabel(card, text=title, font=T.ui(16, True), text_color=T.TEXT, anchor="w").pack(fill="x", padx=18, pady=(14, 8))
        return card

    def _option(self, parent, label, values, current, command) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=6)
        ctk.CTkLabel(row, text=label, font=T.ui(13), text_color=T.TEXT).pack(side="left")
        menu = ctk.CTkOptionMenu(row, values=values, command=command, width=160, fg_color=T.RAISED,
                                 button_color=T.RAISED_HOVER, text_color=T.TEXT)
        menu.set(current)
        menu.pack(side="right")

    def _set(self, key: str, value) -> None:
        self.app.vault.settings[key] = value
        self.app.vault.save()
        self.app.touch()

    def _theme(self, choice: str) -> None:
        self._set("theme", THEMES[choice])
        ctk.set_appearance_mode(THEMES[choice])

    # ---- data actions ------------------------------------------------------------------------
    def _import(self) -> None:
        path = filedialog.askopenfilename(parent=self.app, title="Import CSV", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            imported, skipped = importexport.import_csv(self.app.vault, Path(path))
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            messagebox.showerror("Import failed", str(exc), parent=self.app)
            return
        self.app.sidebar_refresh()
        messagebox.showinfo("Import finished", f"Imported {imported} item(s). Skipped {skipped} duplicate or empty row(s).\n\n"
                            "Delete the CSV file now: it contains your passwords in plain text.", parent=self.app)

    def _export(self) -> None:
        if not messagebox.askyesno("Unencrypted export", "The exported CSV will contain ALL passwords in plain text.\n"
                                   "Anyone who gets the file can read them.\n\nExport anyway?", icon="warning", parent=self.app):
            return
        path = filedialog.asksaveasfilename(parent=self.app, title="Export CSV", defaultextension=".csv",
                                            initialfile="localvault-export.csv", filetypes=[("CSV files", "*.csv")])
        if path:
            try:
                n = importexport.export_csv(self.app.vault, Path(path))
                messagebox.showinfo("Exported", f"Exported {n} item(s).\nDelete the file when you are done with it.", parent=self.app)
            except OSError as exc:
                messagebox.showerror("Export failed", str(exc), parent=self.app)

    def _backup(self) -> None:
        stamp = time.strftime("%Y%m%d-%H%M")
        path = filedialog.asksaveasfilename(parent=self.app, title="Encrypted backup", defaultextension=".lv",
                                            initialfile=f"localvault-backup-{stamp}.lv", filetypes=[("LocalVault files", "*.lv")])
        if path:
            try:
                importexport.backup_encrypted(self.app.vault, Path(path))
                messagebox.showinfo("Backup saved", "The backup is encrypted with your master password and is safe to store anywhere.", parent=self.app)
            except OSError as exc:
                messagebox.showerror("Backup failed", str(exc), parent=self.app)

    def _change_master(self) -> None:
        win = ctk.CTkToplevel(self.app)
        win.title("Change master password")
        win.geometry("420x440")
        win.configure(fg_color=T.BG)
        win.transient(self.app)
        win.after(200, win.grab_set)
        fields = {}
        for key, label in (("old", "Current master password"), ("new", "New master password"), ("again", "Repeat new password")):
            ctk.CTkLabel(win, text=label, font=T.ui(12), text_color=T.MUTED).pack(anchor="w", padx=28, pady=(14, 2))
            e = ctk.CTkEntry(win, show="•", height=38)
            e.pack(fill="x", padx=28)
            fields[key] = e
        strength = StrengthBar(win)
        strength.pack(fill="x", padx=28)
        fields["new"].bind("<KeyRelease>", lambda _e: strength.set_password(fields["new"].get()))
        msg = ctk.CTkLabel(win, text="", text_color=T.DANGER, font=T.ui(13), wraplength=360)
        msg.pack(pady=8)

        def apply() -> None:
            try:
                Vault.open(self.app.vault.path, fields["old"].get()).lock()
            except VaultError:
                msg.configure(text="The current master password is wrong.")
                return
            if fields["new"].get() != fields["again"].get():
                msg.configure(text="The new passwords don't match.")
                return
            try:
                self.app.vault.change_master_password(fields["new"].get())
            except VaultError as exc:
                msg.configure(text=str(exc))
                return
            win.destroy()
            self.app.toast("Master password changed")

        ctk.CTkButton(win, text="Change password", height=40, fg_color=T.BRASS, hover_color=T.BRASS_HOVER,
                      text_color=T.ON_BRASS, command=apply).pack(fill="x", padx=28, pady=(4, 0))
