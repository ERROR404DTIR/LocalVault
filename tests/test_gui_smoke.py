"""Drives the real GUI end to end. Skipped automatically when no display / tkinter is available."""
import os
import time

import pytest

tk = pytest.importorskip("tkinter")
pytest.importorskip("customtkinter")


@pytest.fixture
def app(tmp_path, monkeypatch):
    from localvault import crypto
    monkeypatch.setattr(crypto, "DEFAULT_KDF", {"name": "scrypt", "n": 2**10, "r": 8, "p": 1})
    monkeypatch.setenv("LOCALVAULT_HOME", str(tmp_path))
    from localvault.gui.app import App
    try:
        a = App(tmp_path / "vault.lv")
    except tk.TclError:
        pytest.skip("no display available")
    yield a
    try:
        a.destroy()
    except tk.TclError:
        pass


def pump(app, n=40):
    for _ in range(n):
        app.update_idletasks()
        app.update()
        time.sleep(0.01)


def test_create_browse_and_lock(app):
    from localvault.gui.app import MainScreen
    from localvault.vault import Entry

    pump(app)
    screen = app.screen
    screen.pw.insert(0, "correct-horse-battery")
    screen.confirm.insert(0, "correct-horse-battery")
    screen._submit()
    for _ in range(100):
        pump(app, 3)
        if isinstance(app.screen, MainScreen):
            break
    assert isinstance(app.screen, MainScreen)

    e = Entry(title="Example", username="me", url="https://example.com", totp="JBSWY3DPEHPK3PXP")
    e.set_password("S3cure#Pass!word42")
    app.vault.add(e)
    app.open_entry(e.id)
    pump(app)
    for view in ("generator", "audit", "settings", "favorites", "vault"):
        app.screen.show(view)
        pump(app, 10)

    app.lock()
    pump(app)
    assert app.vault is None
