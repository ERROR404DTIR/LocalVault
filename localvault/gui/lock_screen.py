from __future__ import annotations

import customtkinter as ctk

from ..vault import Vault, VaultError
from . import theme as T
from .widgets import LockIcon, StrengthBar


class LockScreen(ctk.CTkFrame):
    """Create-vault or unlock screen. Calls `on_unlocked(vault)` on success."""

    def __init__(self, master, vault_path, on_unlocked):
        super().__init__(master, fg_color=T.BG)
        self.vault_path = vault_path
        self.on_unlocked = on_unlocked
        self.creating = not Vault.exists(vault_path)
        self.failures = 0

        card = ctk.CTkFrame(self, fg_color=T.PANEL, corner_radius=18, border_width=1, border_color=T.LINE)
        card.place(relx=0.5, rely=0.5, anchor="center")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=44, pady=36)

        self.icon = LockIcon(inner)
        self.icon.pack(pady=(0, 10))
        title = "Create your vault" if self.creating else "LocalVault is locked"
        ctk.CTkLabel(inner, text=title, font=T.ui(22, True), text_color=T.TEXT).pack()
        sub = ("Choose a master password. It never leaves this computer." if self.creating
               else "Enter your master password to unlock.")
        ctk.CTkLabel(inner, text=sub, font=T.ui(13), text_color=T.MUTED).pack(pady=(4, 18))

        self.pw = ctk.CTkEntry(inner, width=320, height=42, show="•", placeholder_text="Master password", font=T.ui(14))
        self.pw.pack()
        self.pw.bind("<Return>", lambda _e: self._submit())
        self.pw.bind("<KeyRelease>", lambda _e: self._on_type())

        self.confirm = None
        self.strength = None
        if self.creating:
            self.strength = StrengthBar(inner)
            self.strength.pack(fill="x", pady=(8, 0))
            self.confirm = ctk.CTkEntry(inner, width=320, height=42, show="•", placeholder_text="Repeat master password", font=T.ui(14))
            self.confirm.pack(pady=(10, 0))
            self.confirm.bind("<Return>", lambda _e: self._submit())
            ctk.CTkLabel(
                inner, text="There is no password recovery.\nIf you forget it, your data cannot be opened.",
                font=T.ui(12), text_color=T.MUTED, justify="center",
            ).pack(pady=(12, 0))

        self.message = ctk.CTkLabel(inner, text="", font=T.ui(13), text_color=T.DANGER, wraplength=320)
        self.message.pack(pady=(10, 0))

        self.button = ctk.CTkButton(
            inner, text="Create vault" if self.creating else "Unlock", width=320, height=44, font=T.ui(14, True),
            fg_color=T.BRASS, hover_color=T.BRASS_HOVER, text_color=T.ON_BRASS, command=self._submit,
        )
        self.button.pack(pady=(8, 0))
        self.after(100, self.pw.focus_set)

    def _on_type(self) -> None:
        if self.strength:
            self.strength.set_password(self.pw.get())

    def _submit(self) -> None:
        password = self.pw.get()
        self.message.configure(text="")
        try:
            if self.creating:
                if password != self.confirm.get():
                    raise VaultError("The two passwords don't match.")
                self.button.configure(state="disabled", text="Creating…")
                self.update_idletasks()
                vault = Vault.create(self.vault_path, password)
            else:
                self.button.configure(state="disabled", text="Unlocking…")
                self.update_idletasks()
                vault = Vault.open(self.vault_path, password)
        except VaultError as exc:
            self._fail(str(exc))
            return
        self.pw.delete(0, "end")
        self.icon.unlock(lambda: self.on_unlocked(vault))

    def _fail(self, text: str) -> None:
        self.failures += 1
        self.message.configure(text=text)
        self.icon.shake()
        label = "Create vault" if self.creating else "Unlock"
        if self.failures >= 3 and not self.creating:
            delay = min(self.failures - 2, 10)
            self.message.configure(text=f"{text}\nTry again in {delay}s.")
            self.after(delay * 1000, lambda: self.button.configure(state="normal", text=label))
        else:
            self.button.configure(state="normal", text=label)
        self.pw.focus_set()
