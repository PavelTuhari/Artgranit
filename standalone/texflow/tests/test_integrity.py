"""Подпись unisim-soft (Ed25519) и контрольные суммы: манифест скриптов, SHA256SUMS, самопроверка, CI."""
import importlib.util
import os
import shutil
import subprocess
import sys
import zipfile

import pytest

from texflow import integrity as I

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.abspath(os.path.join(ROOT, "..", ".."))
SEED = bytes(range(32))                       # тестовый ключ (не unisim-soft)
PUB = I.public_key(SEED)


def test_rfc8032_vectors():
    sk = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
    assert I.public_key(sk).hex() == "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
    assert I.sign(sk, b"").hex() == ("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb882"
                                     "1590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")
    sk2 = bytes.fromhex("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb")
    assert I.sign(sk2, bytes([0x72])).hex().startswith("92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223eb")
    assert I.verify(I.public_key(sk2), bytes([0x72]), I.sign(sk2, bytes([0x72])))


def test_matches_cryptography_if_available():
    ed = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ed25519")
    for n in range(8):
        seed, msg = os.urandom(32), os.urandom(n * 13)
        k = ed.Ed25519PrivateKey.from_private_bytes(seed)
        assert k.sign(msg) == I.sign(seed, msg)
        assert I.verify(I.public_key(seed), msg, k.sign(msg))


def test_tamper_detection_on_signature():
    sig = I.sign(SEED, b"hello")
    assert I.verify(PUB, b"hello", sig)
    assert not I.verify(PUB, b"hellO", sig)
    assert not I.verify(PUB, b"hello", sig[:-1] + bytes([sig[-1] ^ 1]))
    assert not I.verify(I.public_key(os.urandom(32)), b"hello", sig)
    assert not I.verify(PUB, b"hello", b"short")


def test_embedded_unisim_soft_key_matches_pub_file():
    key = I.known_key("unisim-soft")
    assert key and len(key) == 32
    text = open(os.path.join(ROOT, "install", "signing", "unisim-soft.pub"), encoding="utf-8").read()
    assert I.b64(key) in text and I.fingerprint(key) in text and I.SIGNER == "unisim-soft"


def make_tree(tmp_path):
    root = tmp_path / "app"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "a.py").write_text("print('a')\n")
    (root / "b.txt").write_text("b\n")
    (root / "pkg" / "__pycache__").mkdir()
    (root / "pkg" / "__pycache__" / "x.pyc").write_bytes(b"junk")
    text = I.make_manifest(str(root), "test")
    (root / I.MANIFEST).write_text(text)
    (root / I.SIGNATURE).write_text(I.sign_text(SEED, text))
    return root, text


def test_manifest_ok_modified_badsig_nokey(tmp_path):
    root, text = make_tree(tmp_path)
    assert I.parse_sums(text).keys() == {"b.txt", "pkg/a.py"}           # .pyc и сам манифест не входят
    r = I.check_tree(str(root), PUB)
    assert r["status"] == "ok" and r["files"] == 2 and "ok" in I.describe(r)
    (root / "pkg" / "a.py").write_text("print('evil')\n")
    r = I.check_tree(str(root), PUB)
    assert r["status"] == "modified" and r["changed"] == ["pkg/a.py"]
    os.remove(root / "b.txt")
    assert set(I.check_tree(str(root), PUB)["changed"]) == {"pkg/a.py", "b.txt"}
    (root / "b.txt").write_text("b\n")
    (root / "pkg" / "a.py").write_text("print('a')\n")
    os.remove(root / I.SIGNATURE)                                      # сборка без ключа
    r = I.check_tree(str(root), PUB)
    assert r["status"] == "unsigned" and "ПОДПИСИ НЕТ" in I.describe(r)
    (root / "b.txt").write_text("evil\n")
    assert I.check_tree(str(root), PUB)["status"] == "modified"
    (root / I.SIGNATURE).write_text(I.sign_text(SEED, text))
    (root / I.MANIFEST).write_text(text.replace("b.txt", "c.txt"))
    assert I.check_tree(str(root), PUB)["status"] == "bad-signature"
    assert I.check_tree(str(root), I.public_key(os.urandom(32)))["status"] == "bad-signature"
    assert I.check_tree(str(tmp_path / "nothing"))["status"] == "dev"


def test_sums_file(tmp_path):
    (tmp_path / "a.zip").write_bytes(b"AAA")
    (tmp_path / "b.zip").write_bytes(b"BBB")
    text = "# t\n" + "".join(f"{I.sha256_file(str(tmp_path / n))}  {n}\n" for n in ("a.zip", "b.zip"))
    (tmp_path / "SHA256SUMS").write_text(text)
    (tmp_path / "SHA256SUMS.sig").write_text(I.sign_text(SEED, text))
    r = I.check_sums_file(str(tmp_path / "SHA256SUMS"), pub=PUB)
    assert r == {"signature": "ok", "files": {"a.zip": "ok", "b.zip": "ok"}}
    (tmp_path / "b.zip").write_bytes(b"EVIL")
    assert I.check_sums_file(str(tmp_path / "SHA256SUMS"), pub=PUB)["files"]["b.zip"] == "MISMATCH"
    (tmp_path / "SHA256SUMS").write_text(text.replace("# t", "# x"))
    assert I.check_sums_file(str(tmp_path / "SHA256SUMS"), pub=PUB)["signature"] == "INVALID"


def test_seed_from_secret_text():
    secret = "# comment\n\n" + I.b64(SEED) + "\n"
    assert I.seed_from_text(secret) == SEED
    with pytest.raises(ValueError):
        I.seed_from_text(I.b64(b"short"))


def load_release():
    spec = importlib.util.spec_from_file_location("tf_release", os.path.join(ROOT, "tools", "release.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_release_scripts_and_sums_with_test_key(tmp_path, monkeypatch):
    rel = load_release()
    monkeypatch.setitem(I.PUBLIC_KEYS, "unisim-soft", I.b64(PUB))
    monkeypatch.setenv("UNISIM_SOFT_SIGNING_KEY", "# test\n" + I.b64(SEED))
    out = tmp_path / "out"
    z = rel.cmd_scripts(str(out), True)
    (out / "TexFlow-0-linux.zip").write_bytes(b"binary")
    rel.cmd_sums(str(out), True)
    assert rel.cmd_verify(str(out)) == 0
    with zipfile.ZipFile(z) as zf:
        names = zf.namelist()
    top = names[0].split("/")[0]
    assert f"{top}/MANIFEST.sha256" in names and f"{top}/MANIFEST.sha256.sig" in names
    assert f"{top}/texflow_app.py" in names and not any(n.endswith(".pyc") for n in names)
    signer = (out / "SIGNER-unisim-soft.txt").read_text()
    assert I.fingerprint(PUB) in signer
    (out / "TexFlow-0-linux.zip").write_bytes(b"evil")
    assert rel.cmd_verify(str(out)) == 1


def test_release_refuses_foreign_key(tmp_path, monkeypatch):
    rel = load_release()
    monkeypatch.setenv("UNISIM_SOFT_SIGNING_KEY", I.b64(SEED))            # не ключ unisim-soft
    with pytest.raises(SystemExit):
        rel.cmd_scripts(str(tmp_path), True)
    monkeypatch.delenv("UNISIM_SOFT_SIGNING_KEY")
    with pytest.raises(SystemExit):
        rel.seed_or_none(True)
    assert rel.seed_or_none(False) is None


def test_app_self_check_and_strict_mode(tmp_path, monkeypatch, capsys):
    """Копия программы, подписанная тестовым ключом: ok → подмена файла → предупреждение → строгий отказ."""
    app_dir = tmp_path / "TexFlow"
    shutil.copytree(os.path.join(ROOT, "texflow"), app_dir / "texflow",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(os.path.join(ROOT, "texflow_app.py"), app_dir / "texflow_app.py")
    text = I.make_manifest(str(app_dir), "t")
    (app_dir / I.MANIFEST).write_text(text)
    (app_dir / I.SIGNATURE).write_text(I.sign_text(SEED, text))
    monkeypatch.setitem(I.PUBLIC_KEYS, "unisim-soft", I.b64(PUB))
    spec = importlib.util.spec_from_file_location("tf_app_copy", str(app_dir / "texflow_app.py"))
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)
    assert app.main(["--verify"]) == 0
    assert "целостность: ok" in capsys.readouterr().out
    assert app.integrity_status()["status"] == "ok"
    (app_dir / "texflow" / "rules.py").write_text("raise SystemExit('evil')\n")
    assert app.main(["--verify"]) == 1
    assert "ИЗМЕНЕНЫ" in capsys.readouterr().out
    monkeypatch.setenv("TEXFLOW_STRICT_INTEGRITY", "1")
    assert app.main(["--check"]) == 3
    monkeypatch.delenv("TEXFLOW_STRICT_INTEGRITY")
    (app_dir / "texflow" / "rules.py").write_bytes(open(os.path.join(ROOT, "texflow", "rules.py"), "rb").read())
    os.remove(app_dir / I.SIGNATURE)                                   # без подписи: суммы ок, предупреждение
    assert app.integrity_status()["status"] == "unsigned" and app.main(["--verify"]) == 0
    monkeypatch.setenv("TEXFLOW_STRICT_INTEGRITY", "1")
    assert app.main(["--verify"]) == 1 and app.main(["--check"]) == 3   # строгий режим требует подпись


def test_dev_checkout_reports_dev():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "texflow_app.py"), "--verify"], capture_output=True,
                       text=True, timeout=60)
    assert r.returncode == 0 and "рабочая копия" in r.stdout


def test_workflow_builds_runs_and_signs_on_every_push():
    path = os.path.join(REPO, ".github", "workflows", "texflow-desktop.yml")
    if not os.path.exists(path):
        pytest.skip("нет .github в этой копии")
    text = open(path, encoding="utf-8").read()
    for needle in ("branches: [\"**\"]", "texflow-v*", "windows-latest", "macos-latest", "ubuntu",
                   "--smoke", "--verify", "build_exe.py", "release.py scripts", "release.py sums",
                   "UNISIM_SOFT_SIGNING_KEY", "attest-build-provenance", "texflow-nightly"):
        assert needle in text, needle
    yaml = pytest.importorskip("yaml")
    jobs = yaml.safe_load(text)["jobs"]
    assert set(jobs) == {"test", "scripts", "build", "sign"}
    assert jobs["build"]["needs"] == "scripts" and jobs["sign"]["needs"] == "build"
    oses = {m["os"].split("-")[0] for m in jobs["build"]["strategy"]["matrix"]["include"]}
    assert oses == {"windows", "macos", "ubuntu"}
