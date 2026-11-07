from __future__ import annotations

import time
import webbrowser
from tkinter import messagebox

import customtkinter as ctk

from .. import totp as TOTP
from ..vault import Entry
from . import theme as T
from .entry_dialog import EntryDialog


class _Query:
    """Tiny get/set facade over the search entry."""

    def __init__(self, entry: ctk.CTkEntry):
        self.entry = entry

    def get(self) -> str:
        return self.entry.get()

    def set(self, value: str) -> None:
        self.entry.delete(0, "end")
        if value:
            self.entry.insert(0, value)


class VaultView(ctk.CTkFrame):
    """Item list on the left, selected item details on the right."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.filter: tuple[str, str | None] = ("all", None)  # ("all"|"favorites"|"folder"|"unfiled", name)
        self.selected_id: str | None = None
        self.reveal = False

        self.columnconfigure(0, minsize=330)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        left = ctk.CTkFrame(self, fg_color=T.PANEL, corner_radius=0, border_width=0)
        left.grid(row=0, column=0, sticky="nsew")
        left.rowconfigure(2, weight=1)
        left.columnconfigure(0, weight=1)
        self.heading = ctk.CTkLabel(left, text="All items", font=T.ui(18, True), text_color=T.TEXT, anchor="w")
        self.heading.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 8))
        bar = ctk.CTkFrame(left, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 8))
        bar.columnconfigure(0, weight=1)
        self.search = ctk.CTkEntry(bar, placeholder_text="Search items", height=36)
        self.search.grid(row=0, column=0, sticky="ew")
        self.search.bind("<KeyRelease>", lambda _e: self.refresh_list())
        self.query = _Query(self.search)
        ctk.CTkButton(bar, text="+ New", width=70, height=36, fg_color=T.BRASS, hover_color=T.BRASS_HOVER,
                      text_color=T.ON_BRASS, font=T.ui(13, True), command=self.new_item).grid(row=0, column=1, padx=(8, 0))
        self.list = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.list.grid(row=2, column=0, sticky="nsew", padx=6, pady=(0, 6))

        self.detail = ctk.CTkFrame(self, fg_color="transparent")
        self.detail.grid(row=0, column=1, sticky="nsew")
        self.totp_label: ctk.CTkLabel | None = None
        self.totp_bar: ctk.CTkProgressBar | None = None
        self.totp_secret = ""
        self.refresh()

    # ---- list --------------------------------------------------------------------------------
    def set_filter(self, kind: str, name: str | None = None) -> None:
        self.filter = (kind, name)
        self.selected_id = None
        titles = {"all": "All items", "favorites": "Favorites", "unfiled": "No folder"}
        self.heading.configure(text=name if kind == "folder" else titles[kind])
        self.refresh()

    def _visible(self) -> list[Entry]:
        kind, name = self.filter
        v = self.app.vault
        if kind == "favorites":
            return v.search(self.query.get(), favorites_only=True)
        if kind == "folder":
            return v.search(self.query.get(), folder=name)
        if kind == "unfiled":
            return v.search(self.query.get(), folder="")
        return v.search(self.query.get())

    def refresh(self) -> None:
        self.refresh_list()
        self.show_detail()

    def refresh_list(self) -> None:
        for child in self.list.winfo_children():
            child.destroy()
        items = self._visible()
        if not items:
            msg = "No matches." if self.query.get() else "Nothing here yet.\nPress “+ New” to add your first item."
            ctk.CTkLabel(self.list, text=msg, font=T.ui(13), text_color=T.MUTED, justify="center").pack(pady=40)
            return
        for e in items:
            self._list_row(e)

    def _list_row(self, e: Entry) -> None:
        selected = e.id == self.selected_id
        base = T.RAISED if selected else "transparent"
        row = ctk.CTkFrame(self.list, fg_color=base, corner_radius=8, cursor="hand2")
        row.pack(fill="x", pady=1)
        star = "★ " if e.favorite else ""
        sub = e.username or e.url or ("Secure note" if e.kind == "note" else "")
        title = ctk.CTkLabel(row, text=f"{star}{e.title or '(untitled)'}", font=T.ui(13, True), text_color=T.TEXT, anchor="w")
        title.pack(fill="x", padx=12, pady=(8, 0))
        detail = ctk.CTkLabel(row, text=sub, font=T.ui(12), text_color=T.MUTED, anchor="w")
        detail.pack(fill="x", padx=12, pady=(0, 8))
        for w in (row, title, detail):
            w.bind("<Button-1>", lambda _ev, i=e.id: self.select(i))
            if not selected:
                w.bind("<Enter>", lambda _ev, r=row: r.configure(fg_color=T.RAISED_HOVER))
                w.bind("<Leave>", lambda _ev, r=row: r.configure(fg_color="transparent"))

    def select(self, entry_id: str) -> None:
        self.selected_id = entry_id
        self.reveal = False
        self.refresh()

    # ---- detail ------------------------------------------------------------------------------
    def _row(self, parent, label: str, value: str, secret: bool = False, link: bool = False) -> None:
        box = ctk.CTkFrame(parent, fg_color=T.PANEL, corner_radius=10, border_width=1, border_color=T.LINE)
        box.pack(fill="x", pady=4)
        box.columnconfigure(0, weight=1)
        ctk.CTkLabel(box, text=label, font=T.ui(12), text_color=T.MUTED, anchor="w").grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 0))
        shown = ("•" * min(len(value), 24) if secret and not self.reveal else value)
        ctk.CTkLabel(box, text=shown, font=T.mono(14) if secret else T.ui(14), text_color=T.TEXT, anchor="w",
                     wraplength=420, justify="left").grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))
        actions = ctk.CTkFrame(box, fg_color="transparent")
        actions.grid(row=0, column=1, rowspan=2, padx=8)
        if secret:
            ctk.CTkButton(actions, text="Hide" if self.reveal else "Show", width=56, height=30, fg_color=T.RAISED,
                          hover_color=T.RAISED_HOVER, text_color=T.TEXT, command=self._toggle_reveal).pack(side="left", padx=2)
        if link:
            ctk.CTkButton(actions, text="Open", width=56, height=30, fg_color=T.RAISED, hover_color=T.RAISED_HOVER,
                          text_color=T.TEXT, command=lambda: self._open(value)).pack(side="left", padx=2)
        ctk.CTkButton(actions, text="Copy", width=56, height=30, fg_color=T.RAISED, hover_color=T.RAISED_HOVER,
                      text_color=T.TEXT, command=lambda: self.app.copy(value, label, sensitive=secret)).pack(side="left", padx=2)

    def _toggle_reveal(self) -> None:
        self.reveal = not self.reveal
        self.show_detail()

    def _open(self, url: str) -> None:
        if "://" not in url:
            url = "https://" + url
        webbrowser.open(url)

    def show_detail(self) -> None:
        for child in self.detail.winfo_children():
            child.destroy()
        self.totp_label = self.totp_bar = None
        entry = self.app.vault.get(self.selected_id) if self.selected_id else None
        if not entry:
            ctk.CTkLabel(self.detail, text="Select an item to see its details.", font=T.ui(14),
                         text_color=T.MUTED).place(relx=0.5, rely=0.45, anchor="center")
            return
        page = ctk.CTkScrollableFrame(self.detail, fg_color="transparent")
        page.pack(fill="both", expand=True, padx=26, pady=18)

        top = ctk.CTkFrame(page, fg_color="transparent")
        top.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(top, text=entry.title or "(untitled)", font=T.ui(22, True), text_color=T.TEXT,
                     anchor="w", wraplength=360, justify="left").pack(side="left")
        ctk.CTkButton(top, text="Delete", width=70, height=32, fg_color="transparent", border_width=1,
                      border_color=T.DANGER, text_color=T.DANGER, hover_color=T.RAISED,
                      command=lambda: self.delete(entry)).pack(side="right")
        ctk.CTkButton(top, text="Edit", width=70, height=32, fg_color=T.RAISED, hover_color=T.RAISED_HOVER,
                      text_color=T.TEXT, command=lambda: self.edit(entry)).pack(side="right", padx=6)
        ctk.CTkButton(top, text="★" if entry.favorite else "☆", width=36, height=32, fg_color=T.RAISED,
                      hover_color=T.RAISED_HOVER, text_color=T.BRASS, font=T.ui(16),
                      command=lambda: self.toggle_favorite(entry)).pack(side="right")

        if entry.folder:
            ctk.CTkLabel(page, text=f"Folder: {entry.folder}", font=T.ui(12), text_color=T.MUTED, anchor="w").pack(fill="x", pady=(0, 6))
        if entry.username:
            self._row(page, "Username", entry.username)
        if entry.kind == "login" and entry.password:
            self._row(page, "Password", entry.password, secret=True)
        if entry.url:
            self._row(page, "Website", entry.url, link=True)
        if entry.totp:
            self._totp_box(page, entry.totp)
        if entry.notes:
            self._row(page, "Notes", entry.notes)

        stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(entry.updated))
        meta = f"Last modified {stamp}"
        if entry.kind == "login" and entry.password:
            days = int((time.time() - entry.password_changed) / 86400)
            meta += f"  ·  password set {days} day{'s' if days != 1 else ''} ago"
        ctk.CTkLabel(page, text=meta, font=T.ui(12), text_color=T.MUTED, anchor="w").pack(fill="x", pady=(10, 0))

        if entry.history:
            self._history(page, entry)
        self.tick()

    def _totp_box(self, parent, secret: str) -> None:
        self.totp_secret = secret
        box = ctk.CTkFrame(parent, fg_color=T.PANEL, corner_radius=10, border_width=1, border_color=T.LINE)
        box.pack(fill="x", pady=4)
        box.columnconfigure(0, weight=1)
        ctk.CTkLabel(box, text="Authenticator code", font=T.ui(12), text_color=T.MUTED, anchor="w").grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 0))
        self.totp_label = ctk.CTkLabel(box, text="", font=T.mono(24, True), text_color=T.TEAL, anchor="w")
        self.totp_label.grid(row=1, column=0, sticky="ew", padx=14)
        self.totp_bar = ctk.CTkProgressBar(box, height=4, progress_color=T.TEAL)
        self.totp_bar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=14, pady=(4, 12))
        ctk.CTkButton(box, text="Copy", width=56, height=30, fg_color=T.RAISED, hover_color=T.RAISED_HOVER, text_color=T.TEXT,
                      command=self._copy_totp).grid(row=0, column=1, rowspan=2, padx=8)

    def _copy_totp(self) -> None:
        try:
            self.app.copy(TOTP.current_code(self.totp_secret)[0], "Authenticator code")
        except TOTP.TOTPError:
            self.app.toast("This authenticator key is invalid.")

    def tick(self) -> None:
        """Called every second by the app to animate the TOTP code."""
        if not self.totp_label or not self.totp_label.winfo_exists():
            return
        try:
            code, left = TOTP.current_code(self.totp_secret)
        except TOTP.TOTPError:
            self.totp_label.configure(text="invalid key", text_color=T.DANGER)
            return
        self.totp_label.configure(text=f"{code[:3]} {code[3:]}" if len(code) == 6 else code)
        self.totp_bar.set(left / 30)

    def _history(self, parent, entry: Entry) -> None:
        ctk.CTkLabel(parent, text="Previous passwords", font=T.ui(13, True), text_color=T.TEXT, anchor="w").pack(fill="x", pady=(18, 4))
        for old in entry.history[:5]:
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x")
            when = time.strftime("%Y-%m-%d", time.localtime(old["changed"]))
            ctk.CTkLabel(row, text=f"set {when}", font=T.ui(12), text_color=T.MUTED).pack(side="left")
            ctk.CTkButton(row, text="Copy", width=52, height=24, fg_color=T.RAISED, hover_color=T.RAISED_HOVER,
                          text_color=T.TEXT, command=lambda p=old["password"]: self.app.copy(p, "Old password")).pack(side="right")

    # ---- actions -----------------------------------------------------------------------------
    def new_item(self) -> None:
        folder = self.filter[1] if self.filter[0] == "folder" else ""
        EntryDialog(self.app, folder=folder or "", on_saved=self._saved)

    def edit(self, entry: Entry) -> None:
        EntryDialog(self.app, entry=entry, on_saved=self._saved)

    def _saved(self, entry: Entry) -> None:
        self.selected_id = entry.id
        self.reveal = False
        self.app.sidebar_refresh()
        self.refresh()

    def toggle_favorite(self, entry: Entry) -> None:
        entry.favorite = not entry.favorite
        self.app.vault.update(entry)
        self.refresh()

    def delete(self, entry: Entry) -> None:
        if messagebox.askyesno("Delete item", f"Delete “{entry.title}”?\nThis cannot be undone.", parent=self.app):
            self.app.vault.delete(entry.id)
            self.selected_id = None
            self.app.sidebar_refresh()
            self.refresh()
