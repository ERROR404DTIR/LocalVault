import json
import time

import pytest

from localvault import audit, crypto, generator, importexport, totp
from localvault.vault import Entry, Vault, VaultError

# Fast KDF for tests only.
FAST = {"name": "scrypt", "n": 2**10, "r": 8, "p": 1}


@pytest.fixture(autouse=True)
def fast_kdf(monkeypatch):
    monkeypatch.setattr(crypto, "DEFAULT_KDF", FAST)


def test_crypto_roundtrip_and_wrong_password():
    sealed = crypto.encrypt_new(b"secret data", "correct horse")
    plain, _ = crypto.decrypt(sealed.blob, "correct horse")
    assert plain == b"secret data"
    with pytest.raises(crypto.VaultCryptoError):
        crypto.decrypt(sealed.blob, "wrong")


def test_crypto_detects_tampering():
    sealed = crypto.encrypt_new(b"secret data", "pw-pw-pw-pw")
    doc = json.loads(sealed.blob)
    doc["kdf"]["n"] = 2**9  # header is authenticated
    with pytest.raises(crypto.VaultCryptoError):
        crypto.decrypt(json.dumps(doc).encode(), "pw-pw-pw-pw")
    with pytest.raises(crypto.VaultCryptoError):
        crypto.decrypt(b"not json", "x")


def test_vault_create_open_edit(tmp_path):
    path = tmp_path / "v.lv"
    v = Vault.create(path, "master-pass-1")
    e = v.add(Entry(title="GitHub", username="me", password="pw1", folder="Dev", url="https://github.com"))
    e.set_password("pw2")
    v.update(e)

    v2 = Vault.open(path, "master-pass-1")
    got = v2.get(e.id)
    assert got.password == "pw2" and got.history[0]["password"] == "pw1"
    assert v2.folders == ["Dev"]
    with pytest.raises(VaultError):
        Vault.open(path, "bad-password")
    assert b"GitHub" not in path.read_bytes()  # nothing readable on disk


def test_vault_short_master_rejected(tmp_path):
    with pytest.raises(VaultError):
        Vault.create(tmp_path / "v.lv", "short")


def test_change_master_password(tmp_path):
    path = tmp_path / "v.lv"
    v = Vault.create(path, "old-master-pw")
    v.add(Entry(title="X", password="p"))
    v.change_master_password("new-master-pw")
    with pytest.raises(VaultError):
        Vault.open(path, "old-master-pw")
    assert len(Vault.open(path, "new-master-pw").entries) == 1


def test_search_folders_and_favorites(tmp_path):
    v = Vault.create(tmp_path / "v.lv", "master-pass-1")
    v.add(Entry(title="Alpha", folder="Work", favorite=True))
    v.add(Entry(title="Beta", username="bob@mail.com"))
    assert [e.title for e in v.search("bob")] == ["Beta"]
    assert [e.title for e in v.search(favorites_only=True)] == ["Alpha"]
    assert [e.title for e in v.search(folder="Work")] == ["Alpha"]
    v.rename_folder("Work", "Job")
    assert v.get(v.entries[0].id).folder == "Job"
    v.delete_folder("Job")
    assert all(e.folder == "" for e in v.entries)


def test_backup_file_created(tmp_path):
    v = Vault.create(tmp_path / "v.lv", "master-pass-1")
    v.add(Entry(title="a"))
    assert (tmp_path / "v.lv.bak").exists()


def test_generator_options():
    for _ in range(50):
        pw = generator.generate_password(generator.PasswordOptions(length=16, avoid_ambiguous=True))
        assert len(pw) == 16
        assert not set(pw) & generator.AMBIGUOUS
        assert any(c.isdigit() for c in pw) and any(c.isupper() for c in pw) and any(c.islower() for c in pw)
    only_digits = generator.generate_password(generator.PasswordOptions(length=8, upper=False, lower=False, symbols=False))
    assert only_digits.isdigit()
    with pytest.raises(ValueError):
        generator.generate_password(generator.PasswordOptions(upper=False, lower=False, digits=False, symbols=False))


def test_passphrase():
    p = generator.generate_passphrase(words=6, separator=".", add_number=True)
    assert len(p.split(".")) == 6
    assert generator.passphrase_entropy(6) > 40


def test_strength():
    assert generator.strength_label(generator.estimate_entropy("password"))[1] == 0
    assert generator.strength_label(generator.estimate_entropy("aaaaaaaa"))[1] <= 1
    assert generator.strength_label(generator.estimate_entropy(generator.generate_password()))[1] >= 3


def test_totp_rfc6238_vectors():
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # ASCII "12345678901234567890"
    assert totp.generate_totp(secret, at=59, digits=8) == "94287082"
    assert totp.generate_totp(secret, at=1111111109, digits=8) == "07081804"
    assert totp.generate_totp(secret, at=20000000000, digits=8) == "65353130"


def test_totp_uri():
    p = totp.parse_totp_input("otpauth://totp/Test:me?secret=JBSWY3DPEHPK3PXP&issuer=Test&digits=8&period=60")
    assert p["digits"] == 8 and p["period"] == 60 and p["issuer"] == "Test"
    with pytest.raises(totp.TOTPError):
        totp.parse_totp_input("!!!not base32!!!")
    code, left = totp.current_code("JBSWY3DPEHPK3PXP")
    assert len(code) == 6 and 1 <= left <= 30


def test_audit():
    old = Entry(title="old", password="Xk9#mQ2$vL8@nR4!", password_changed=time.time() - 400 * 86400)
    entries = [
        Entry(title="a", password="password"),
        Entry(title="b", password="SameOne#2024xyz"),
        Entry(title="c", password="SameOne#2024xyz"),
        old,
        Entry(title="empty"),
        Entry(title="note", kind="note"),
    ]
    r = audit.run_audit(entries)
    assert [e.title for e in r.weak] == ["a"]
    assert {e.title for e in r.reused_entries} == {"b", "c"}
    assert [e.title for e in r.old] == ["old"]
    assert [e.title for e in r.no_password] == ["empty"]
    assert 0 <= r.score <= 100


def test_import_export_csv(tmp_path):
    v = Vault.create(tmp_path / "v.lv", "master-pass-1")
    v.add(Entry(title="Site", username="u", password="p,w\"1", url="https://x.com", folder="F", favorite=True, totp="JBSWY3DPEHPK3PXP"))
    out = tmp_path / "out.csv"
    importexport.export_csv(v, out)

    v2 = Vault.create(tmp_path / "v2.lv", "master-pass-2")
    imported, skipped = importexport.import_csv(v2, out)
    assert (imported, skipped) == (1, 0)
    e = v2.entries[0]
    assert e.password == 'p,w"1' and e.favorite and e.folder == "F" and e.totp == "JBSWY3DPEHPK3PXP"
    assert importexport.import_csv(v2, out) == (0, 1)  # duplicates skipped


def test_import_chrome_csv(tmp_path):
    f = tmp_path / "chrome.csv"
    f.write_text("name,url,username,password,note\nExample,https://example.com,bob,hunter2!,hi\n", encoding="utf-8")
    v = Vault.create(tmp_path / "v.lv", "master-pass-1")
    assert importexport.import_csv(v, f) == (1, 0)
    assert v.entries[0].url == "https://example.com"
