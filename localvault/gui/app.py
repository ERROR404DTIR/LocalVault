from __future__ import annotations

import argparse
import time
import tkinter as tk
from pathlib import Path

import customtkinter as ctk

from .. import APP_NAME, __version__
from ..paths import default_vault_path
from ..vault import Vault
from . import theme as T
from .audit_view import AuditView
from .generator_view import GeneratorView
from .lock_screen import LockScreen
from .settings_view import SettingsView
from .vault_view import VaultView


class MainScreen(ctk.CTkFrame):
    NAV = (("vault", "All items"), ("favorites", "Favorites"), ("generator", "Generator"),
           ("audit", "Security audit"), ("settings", "Settings"))

    def __init__(self, master, app: "App"):
        super().__init__(master, fg_color=T.BG)
        self.app = app
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, fg_color=T.PANEL, corner_radius=0, width=210)
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.sidebar.grid_propagate(False)
        self.sidebar.rowconfigure(3, weight=1)
        ctk.CTkLabel(self.sidebar, text="LocalVault", font=T.ui(18, True), text_color=T.BRASS).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 14))

        nav = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        nav.grid(row=1, column=0, sticky="ew", padx=10)
        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        for key, label in self.NAV:
            b = ctk.CTkButton(nav, text=label, anchor="w", height=36, corner_radius=8, fg_color="transparent",
                              hover_color=T.RAISED_HOVER, text_color=T.TEXT, font=T.ui(13),
                              command=lambda k=key: self.show(k))
            b.pack(fill="x", pady=1)
            self.nav_buttons[key] = b

        head = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        head.grid(row=2, column=0, sticky="ew", padx=20, pady=(16, 4))
        ctk.CTkLabel(head, text="Folders", font=T.ui(12, True), text_color=T.MUTED).pack(side="left")
        ctk.CTkButton(head, text="+", width=26, height=22, fg_color=T.RAISED, hover_color=T.RAISED_HOVER,
                      text_color=T.TEXT, command=self.new_folder).pack(side="right")
        self.folder_list = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.folder_list.grid(row=3, column=0, sticky="nsew", padx=4)
        ctk.CTkButton(self.sidebar, text="Lock now", height=38, fg_color=T.RAISED, hover_color=T.RAISED_HOVER,
                      text_color=T.TEXT, command=app.lock).grid(row=4, column=0, sticky="ew", padx=14, pady=14)

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.rowconfigure(0, weight=1)
        self.content.columnconfigure(0, weight=1)
        self.vault_view = VaultView(self.content, app)
        self.vault_view.grid(row=0, column=0, sticky="nsew")
        self.current = "vault"
        self.other: ctk.CTkFrame | None = None
        self.refresh_folders()
        self._highlight("vault")

    def _highlight(self, key: str | None) -> None:
        for k, b in self.nav_buttons.items():
            b.configure(fg_color=T.RAISED if k == key else "transparent")

    def show(self, key: str) -> None:
        if self.other is not None:
            self.other.destroy()
            self.other = None
        if key in ("vault", "favorites"):
            self.vault_view.set_filter("all" if key == "vault" else "favorites")
            self.vault_view.grid(row=0, column=0, sticky="nsew")
            self.vault_view.lift()
        else:
            view = {"generator": GeneratorView, "audit": AuditView, "settings": SettingsView}[key](self.content, self.app)
            view.grid(row=0, column=0, sticky="nsew")
            self.other = view
        self.current = key
        self._highlight(key)

    def show_folder(self, name: str | None, kind: str = "folder") -> None:
        if self.other is not None:
            self.other.destroy()
            self.other = None
        self.vault_view.set_filter(kind, name)
        self.vault_view.grid(row=0, column=0, sticky="nsew")
        self.current = "vault"
        self._highlight(None)

    def refresh_folders(self) -> None:
        for child in self.folder_list.winfo_children():
            child.destroy()
        names = self.app.vault.folders
        unfiled = any(not e.folder for e in self.app.vault.entries)
        for name in names:
            count = sum(1 for e in self.app.vault.entries if e.folder == name)
            b = ctk.CTkButton(self.folder_list, text=f"{name}  ({count})", anchor="w", height=32, fg_color="transparent",
                              hover_color=T.RAISED_HOVER, text_color=T.TEXT, font=T.ui(13),
                              command=lambda n=name: self.show_folder(n))
            b.pack(fill="x", pady=1)
            for ev in ("<Button-3>", "<Button-2>"):
                b.bind(ev, lambda e, n=name: self._folder_menu(e, n))
        if names and unfiled:
            ctk.CTkButton(self.folder_list, text="No folder", anchor="w", height=32, fg_color="transparent",
                          hover_color=T.RAISED_HOVER, text_color=T.MUTED, font=T.ui(13),
                          command=lambda: self.show_folder("", "unfiled")).pack(fill="x", pady=1)
        if not names:
            ctk.CTkLabel(self.folder_list, text="No folders yet", font=T.ui(12), text_color=T.MUTED).pack(pady=8)

    def _folder_menu(self, event, name: str) -> None:
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Rename…", command=lambda: self.rename_folder(name))
        menu.add_command(label="Delete folder (keeps items)", command=lambda: self.delete_folder(name))
        menu.tk_popup(event.x_root, event.y_root)

    def new_folder(self) -> None:
        name = ctk.CTkInputDialog(text="Folder name:", title="New folder").get_input()
        if name and name.strip():
            name = name.strip()
            if name not in self.app.vault.folders:
                self.app.vault.folders.append(name)
                self.app.vault.folders.sort(key=str.lower)
                self.app.vault.save()
            self.refresh_folders()

    def rename_folder(self, old: str) -> None:
        new = ctk.CTkInputDialog(text=f"Rename “{old}” to:", title="Rename folder").get_input()
        if new and new.strip():
            self.app.vault.rename_folder(old, new)
            self.refresh_folders()
            self.vault_view.refresh()

    def delete_folder(self, name: str) -> None:
        self.app.vault.delete_folder(name)
        self.refresh_folders()
        self.show("vault")


class App(ctk.CTk):
    def __init__(self, vault_path: Path):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        T.apply()
        self.title(APP_NAME)
        self.geometry("1140x740")
        self.minsize(940, 620)
        self.configure(fg_color=T.BG)
        self.vault_path = Path(vault_path)
        self.vault: Vault | None = None
        self.screen: ctk.CTkFrame | None = None
        self.last_activity = time.time()
        self._clip_job = None
        self._toast_job = None
        self._last_copied: str | None = None
        self.toast_label = ctk.CTkLabel(self, text="", font=T.ui(13, True), fg_color=T.RAISED, text_color=T.TEXT,
                                        corner_radius=18, height=36)
        for ev in ("<Any-KeyPress>", "<Motion>", "<Button>"):
            self.bind_all(ev, lambda _e: self.touch(), add="+")
        self.bind("<Unmap>", self._on_unmap)
        self.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.show_lock()
        self.after(1000, self._tick)

    # ---- screens -----------------------------------------------------------------------------
    def show_lock(self) -> None:
        if self.screen is not None:
            self.screen.destroy()
        ctk.set_appearance_mode("dark")
        self.screen = LockScreen(self, self.vault_path, self._unlocked)
        self.screen.pack(fill="both", expand=True)

    def _unlocked(self, vault: Vault) -> None:
        self.vault = vault
        ctk.set_appearance_mode(vault.settings.get("theme", "dark"))
        self.screen.destroy()
        self.screen = MainScreen(self, self)
        self.screen.pack(fill="both", expand=True)
        self.touch()

    def lock(self) -> None:
        for w in self.winfo_children():
            if isinstance(w, (tk.Toplevel,)):
                w.destroy()
        self.clear_clipboard_now()
        if self.vault:
            self.vault.lock()
            self.vault = None
        self.show_lock()

    def quit_app(self) -> None:
        self.clear_clipboard_now()
        if self.vault:
            self.vault.lock()
        self.destroy()

    # ---- helpers used by views ---------------------------------------------------------------
    def touch(self) -> None:
        self.last_activity = time.time()

    def sidebar_refresh(self) -> None:
        if isinstance(self.screen, MainScreen):
            self.screen.refresh_folders()

    def open_entry(self, entry_id: str) -> None:
        if isinstance(self.screen, MainScreen):
            self.screen.show("vault")
            self.screen.vault_view.query.set("")
            self.screen.vault_view.select(entry_id)

    def toast(self, text: str, ms: int = 2200) -> None:
        self.toast_label.configure(text=f"  {text}  ")
        self.toast_label.place(relx=0.5, rely=0.96, anchor="s")
        self.toast_label.lift()
        if self._toast_job:
            self.after_cancel(self._toast_job)
        self._toast_job = self.after(ms, self.toast_label.place_forget)

    def copy(self, text: str, what: str = "Text", sensitive: bool = True) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update_idletasks()
        seconds = self.vault.settings.get("clipboard_clear_seconds", 20) if self.vault else 20
        if self._clip_job:
            self.after_cancel(self._clip_job)
            self._clip_job = None
        self._last_copied = text
        if sensitive and seconds:
            self._clip_job = self.after(seconds * 1000, self.clear_clipboard_now)
            self.toast(f"{what} copied. Clipboard clears in {seconds}s")
        else:
            self.toast(f"{what} copied")

    def clear_clipboard_now(self) -> None:
        if self._clip_job:
            self.after_cancel(self._clip_job)
            self._clip_job = None
        if self._last_copied is None:
            return
        try:
            if self.clipboard_get() == self._last_copied:  # don't wipe something the user copied elsewhere
                self.clipboard_clear()
                self.clipboard_append("")
        except tk.TclError:
            pass
        self._last_copied = None

    # ---- timers ------------------------------------------------------------------------------
    def _tick(self) -> None:
        if self.vault:
            minutes = self.vault.settings.get("autolock_minutes", 5)
            if minutes and time.time() - self.last_activity > minutes * 60:
                self.lock()
            elif isinstance(self.screen, MainScreen):
                self.screen.vault_view.tick()
        self.after(1000, self._tick)

    def _on_unmap(self, event) -> None:
        if event.widget is self and self.vault and self.vault.settings.get("lock_on_minimize"):
            if self.state() == "iconic":
                self.lock()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="localvault", description="LocalVault - offline password manager")
    parser.add_argument("--vault", type=Path, help="path to the vault file (default: per-user data folder)")
    parser.add_argument("--version", action="version", version=f"LocalVault {__version__}")
    args = parser.parse_args(argv)
    App(args.vault or default_vault_path()).mainloop()
