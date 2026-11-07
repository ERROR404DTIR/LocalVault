from __future__ import annotations

import queue
import threading
from tkinter import messagebox

import customtkinter as ctk

from .. import audit
from . import theme as T


class AuditView(ctk.CTkScrollableFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.results: queue.Queue = queue.Queue()
        self.pwned_box: ctk.CTkFrame | None = None
        self.refresh()

    def refresh(self) -> None:
        for child in self.winfo_children():
            child.destroy()
        report = audit.run_audit(self.app.vault.entries)
        ctk.CTkLabel(self, text="Security audit", font=T.ui(24, True), text_color=T.TEXT).pack(anchor="w", padx=32, pady=(28, 2))
        ctk.CTkLabel(self, text="Everything is checked on this computer.", font=T.ui(13), text_color=T.MUTED).pack(anchor="w", padx=32)

        score_row = ctk.CTkFrame(self, fg_color=T.PANEL, corner_radius=14, border_width=1, border_color=T.LINE)
        score_row.pack(fill="x", padx=32, pady=18)
        color = T.STRENGTH_COLORS[min(4, report.score // 25)]
        ctk.CTkLabel(score_row, text=str(report.score), font=T.ui(48, True), text_color=color).pack(side="left", padx=(28, 6), pady=18)
        info = ctk.CTkFrame(score_row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, padx=14)
        verdict = "Healthy vault" if report.score >= 80 else "Needs attention" if report.score >= 50 else "At risk"
        ctk.CTkLabel(info, text=f"{verdict} out of 100", font=T.ui(16, True), text_color=T.TEXT, anchor="w").pack(fill="x")
        ctk.CTkLabel(info, text=f"{report.total} login{'s' if report.total != 1 else ''} checked", font=T.ui(13),
                     text_color=T.MUTED, anchor="w").pack(fill="x")
        bar = ctk.CTkProgressBar(score_row, width=200, height=8, progress_color=color)
        bar.set(report.score / 100)
        bar.pack(side="right", padx=28)

        self._section("Weak passwords", "Easy to guess. Replace them with generated ones.", report.weak)
        reuse_items = report.reused_entries
        self._section("Reused passwords", "The same password on several sites means one breach exposes all of them.", reuse_items)
        self._section(f"Older than {audit.OLD_AFTER_DAYS} days", "Consider rotating these.", report.old)
        self._section("Missing a password", "These logins have no password saved.", report.no_password)
        self._section("No two-factor code stored", "Add an authenticator key where the site supports it.", report.no_totp)

        breach = ctk.CTkFrame(self, fg_color=T.PANEL, corner_radius=14, border_width=1, border_color=T.LINE)
        breach.pack(fill="x", padx=32, pady=(8, 28))
        ctk.CTkLabel(breach, text="Check for known breaches (online)", font=T.ui(15, True), text_color=T.TEXT, anchor="w").pack(fill="x", padx=18, pady=(14, 0))
        ctk.CTkLabel(
            breach, font=T.ui(12), text_color=T.MUTED, anchor="w", justify="left", wraplength=560,
            text="Uses the Have I Been Pwned range API. Only the first 5 characters of each password's SHA-1 hash are sent; "
                 "your passwords never leave this computer. This is the only feature that uses the internet and it only runs when you press the button.",
        ).pack(fill="x", padx=18, pady=(4, 8))
        self.breach_btn = ctk.CTkButton(breach, text="Run breach check", height=36, fg_color=T.BRASS, hover_color=T.BRASS_HOVER,
                                        text_color=T.ON_BRASS, command=self._start_breach_check)
        self.breach_btn.pack(anchor="w", padx=18, pady=(0, 6))
        self.pwned_box = ctk.CTkFrame(breach, fg_color="transparent")
        self.pwned_box.pack(fill="x", padx=18, pady=(0, 14))

    def _section(self, title: str, hint: str, entries) -> None:
        box = ctk.CTkFrame(self, fg_color=T.PANEL, corner_radius=14, border_width=1, border_color=T.LINE)
        box.pack(fill="x", padx=32, pady=6)
        head = ctk.CTkFrame(box, fg_color="transparent")
        head.pack(fill="x", padx=18, pady=(12, 0))
        ok = not entries
        ctk.CTkLabel(head, text=title, font=T.ui(15, True), text_color=T.TEXT).pack(side="left")
        ctk.CTkLabel(head, text="All clear" if ok else str(len(entries)), font=T.ui(13, True),
                     text_color=T.TEAL if ok else T.DANGER).pack(side="right")
        ctk.CTkLabel(box, text=hint, font=T.ui(12), text_color=T.MUTED, anchor="w").pack(fill="x", padx=18, pady=(0, 6 if entries else 12))
        for e in entries[:8]:
            ctk.CTkButton(box, text=f"{e.title}   {e.username}", anchor="w", height=30, fg_color="transparent",
                          hover_color=T.RAISED, text_color=T.TEXT, command=lambda i=e.id: self.app.open_entry(i)).pack(fill="x", padx=10)
        if len(entries) > 8:
            ctk.CTkLabel(box, text=f"and {len(entries) - 8} more", font=T.ui(12), text_color=T.MUTED).pack(anchor="w", padx=18)
        ctk.CTkFrame(box, height=8, width=1, fg_color=T.PANEL).pack()

    # ---- breach check ------------------------------------------------------------------------
    def _start_breach_check(self) -> None:
        logins = [e for e in self.app.vault.entries if e.kind == "login" and e.password]
        if not logins:
            messagebox.showinfo("Breach check", "There are no passwords to check.", parent=self.app)
            return
        if not messagebox.askokcancel(
            "Go online?",
            "LocalVault will contact api.pwnedpasswords.com.\nOnly a 5-character hash prefix per password is sent.\n\nContinue?",
            parent=self.app,
        ):
            return
        self.breach_btn.configure(state="disabled", text="Checking…")
        for child in self.pwned_box.winfo_children():
            child.destroy()
        data = [(e.id, e.title, e.password) for e in logins]
        threading.Thread(target=self._worker, args=(data,), daemon=True).start()
        self.after(150, self._poll)

    def _worker(self, data) -> None:
        found = []
        try:
            cache: dict[str, int] = {}
            for entry_id, title, password in data:
                if password not in cache:
                    cache[password] = audit.pwned_count(password)
                if cache[password]:
                    found.append((entry_id, title, cache[password]))
            self.results.put(("done", found))
        except OSError as exc:
            self.results.put(("error", str(exc)))

    def _poll(self) -> None:
        if not self.winfo_exists():
            return
        try:
            kind, payload = self.results.get_nowait()
        except queue.Empty:
            self.after(150, self._poll)
            return
        self.breach_btn.configure(state="normal", text="Run breach check")
        if kind == "error":
            ctk.CTkLabel(self.pwned_box, text=f"Could not reach the service: {payload}", text_color=T.DANGER,
                         font=T.ui(13), wraplength=540, justify="left").pack(anchor="w")
        elif not payload:
            ctk.CTkLabel(self.pwned_box, text="None of your passwords were found in known breaches.",
                         text_color=T.TEAL, font=T.ui(13)).pack(anchor="w")
        else:
            ctk.CTkLabel(self.pwned_box, text=f"{len(payload)} password(s) appear in known breaches. Change them now:",
                         text_color=T.DANGER, font=T.ui(13, True)).pack(anchor="w", pady=(0, 4))
            for entry_id, title, count in payload:
                ctk.CTkButton(self.pwned_box, text=f"{title}  (seen {count:,} times)", anchor="w", height=30,
                              fg_color="transparent", hover_color=T.RAISED, text_color=T.TEXT,
                              command=lambda i=entry_id: self.app.open_entry(i)).pack(fill="x")
