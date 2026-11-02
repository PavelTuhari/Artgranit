"""Целостность поставки: контрольные суммы SHA-256 и подпись Ed25519 подписанта «unisim-soft».

Как это работает:
  * при каждом push сборка GitHub Actions считает SHA-256 всех файлов скриптовой версии
    (MANIFEST.sha256) и всех собранных архивов (SHA256SUMS), подписывает их закрытым ключом
    unisim-soft (секрет репозитория UNISIM_SOFT_SIGNING_KEY);
  * открытый ключ зашит сюда и лежит в install/signing/unisim-soft.pub;
  * texflow_app.py при запуске сам проверяет свои файлы (``--verify`` — подробно);
    любой архив проверяется командой ``python texflow_app.py --verify-sums SHA256SUMS``.

Ed25519 реализован по RFC 8032 на чистом Python (без внешних библиотек), чтобы проверка работала
везде, где запускается сама программа.
"""
from __future__ import annotations

import base64
import hashlib
import os

SIGNER = "unisim-soft"
# открытый ключ подписанта (Ed25519, 32 байта, base64)
PUBLIC_KEYS = {
    "unisim-soft": "sNx6NImwj1Atg9+kKGfAv4CVyJQMvZEzo3k8CHZh7rw=",
}
MANIFEST = "MANIFEST.sha256"
SIGNATURE = "MANIFEST.sha256.sig"
SKIP = {MANIFEST, SIGNATURE}

# ======================================================================= Ed25519 (RFC 8032)

_p = 2 ** 255 - 19
_q = 2 ** 252 + 27742317777372353535851937790883648493


def _inv(x: int) -> int:
    return pow(x, _p - 2, _p)


_d = -121665 * _inv(121666) % _p
_sqrt_m1 = pow(2, (_p - 1) // 4, _p)


def _add(P, Q):
    A, B = (P[1] - P[0]) * (Q[1] - Q[0]) % _p, (P[1] + P[0]) * (Q[1] + Q[0]) % _p
    C, D = 2 * P[3] * Q[3] * _d % _p, 2 * P[2] * Q[2] % _p
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F, G * H, F * G, E * H)


def _mul(s: int, P):
    Q = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            Q = _add(Q, P)
        P = _add(P, P)
        s >>= 1
    return Q


def _equal(P, Q) -> bool:
    return (P[0] * Q[2] - Q[0] * P[2]) % _p == 0 and (P[1] * Q[2] - Q[1] * P[2]) % _p == 0


def _recover_x(y: int, sign: int):
    if y >= _p:
        return None
    x2 = (y * y - 1) * _inv(_d * y * y + 1)
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_p + 3) // 8, _p)
    if (x * x - x2) % _p:
        x = x * _sqrt_m1 % _p
    if (x * x - x2) % _p:
        return None
    if (x & 1) != sign:
        x = _p - x
    return x


_gy = 4 * _inv(5) % _p
_gx = _recover_x(_gy, 0)
_G = (_gx, _gy, 1, _gx * _gy % _p)


def _compress(P) -> bytes:
    zi = _inv(P[2])
    x, y = P[0] * zi % _p, P[1] * zi % _p
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _decompress(s: bytes):
    if len(s) != 32:
        return None
    y = int.from_bytes(s, "little")
    sign, y = y >> 255, y & ((1 << 255) - 1)
    x = _recover_x(y, sign)
    return None if x is None else (x, y, 1, x * y % _p)


def _expand(seed: bytes):
    h = hashlib.sha512(seed).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def _hq(b: bytes) -> int:
    return int.from_bytes(hashlib.sha512(b).digest(), "little") % _q


def public_key(seed: bytes) -> bytes:
    if len(seed) != 32:
        raise ValueError("Ed25519: закрытый ключ — 32 байта")
    return _compress(_mul(_expand(seed)[0], _G))


def sign(seed: bytes, msg: bytes) -> bytes:
    a, prefix = _expand(seed)
    A = _compress(_mul(a, _G))
    r = _hq(prefix + msg)
    R = _compress(_mul(r, _G))
    s = (r + _hq(R + A + msg) * a) % _q
    return R + int.to_bytes(s, 32, "little")


def verify(pub: bytes, msg: bytes, sig: bytes) -> bool:
    if len(sig) != 64:
        return False
    A, R = _decompress(pub), _decompress(sig[:32])
    if not A or not R:
        return False
    s = int.from_bytes(sig[32:], "little")
    if s >= _q:
        return False
    return _equal(_mul(s, _G), _add(R, _mul(_hq(sig[:32] + pub + msg), A)))


# ======================================================================= ключи

def b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def unb64(s: str) -> bytes:
    return base64.b64decode(s.strip())


def fingerprint(pub: bytes) -> str:
    return hashlib.sha256(pub).hexdigest()[:16]


def known_key(signer: str = SIGNER) -> bytes | None:
    k = PUBLIC_KEYS.get(signer, "")
    try:
        return unb64(k) if k and k != "REPLACE_PUBLIC_KEY" else None
    except ValueError:
        return None


def seed_from_text(text: str) -> bytes:
    """Закрытый ключ из секрета: base64 32 байт (можно с комментариями # и пустыми строками)."""
    lines = [x.strip() for x in text.splitlines() if x.strip() and not x.strip().startswith("#")]
    seed = unb64("".join(lines))
    if len(seed) != 32:
        raise ValueError("Ed25519: закрытый ключ — 32 байта в base64")
    return seed


# ======================================================================= манифест файлов

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def walk(root: str) -> list[str]:
    out = []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in ("__pycache__", "venv", ".git", "instance", "dist", "build",
                                                      ".cache", "node_modules"))
        for f in sorted(files):
            rel = os.path.relpath(os.path.join(dirpath, f), root).replace(os.sep, "/")
            if rel in SKIP or f.endswith((".pyc", ".db", ".db-wal", ".db-shm")) or f.startswith("._"):
                continue
            out.append(rel)
    return out


def make_manifest(root: str, title: str = "") -> str:
    lines = [f"# {title}".rstrip(), f"# signer: {SIGNER}"]
    lines += [f"{sha256_file(os.path.join(root, rel))}  {rel}" for rel in walk(root)]
    return "\n".join(lines) + "\n"


def parse_sums(text: str) -> dict[str, str]:
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        digest, _, name = line.partition("  ")
        out[name.strip().lstrip("*")] = digest.strip().lower()
    return out


def sign_text(seed: bytes, text: str) -> str:
    return b64(sign(seed, text.encode("utf-8")))


def verify_text(text: str, sig_b64: str, pub: bytes | None = None) -> bool:
    pub = pub or known_key()
    if not pub:
        return False
    try:
        return verify(pub, text.encode("utf-8"), unb64(sig_b64))
    except (ValueError, TypeError):
        return False


def check_tree(root: str, pub: bytes | None = None) -> dict:
    """Проверить установленные скрипты по подписанному манифесту.

    status: dev (манифеста нет — рабочая копия из git) | ok | bad-signature | modified | no-key
    """
    mpath, spath = os.path.join(root, MANIFEST), os.path.join(root, SIGNATURE)
    if not os.path.exists(mpath):
        return {"status": "dev", "signer": SIGNER, "files": 0}
    pub = pub or known_key()
    text = open(mpath, encoding="utf-8").read()
    if not pub:
        return {"status": "no-key", "signer": SIGNER, "files": 0}
    sig = open(spath, encoding="utf-8").read().strip() if os.path.exists(spath) else ""
    if not sig or not verify_text(text, sig, pub):
        return {"status": "bad-signature", "signer": SIGNER, "files": 0, "key": fingerprint(pub)}
    sums = parse_sums(text)
    changed = [rel for rel, dg in sums.items()
               if not os.path.exists(os.path.join(root, rel)) or sha256_file(os.path.join(root, rel)) != dg]
    return {"status": "modified" if changed else "ok", "signer": SIGNER, "files": len(sums), "changed": changed,
            "key": fingerprint(pub), "title": text.splitlines()[0].lstrip("# ").strip()}


def check_sums_file(sums_path: str, sig_path: str | None = None, pub: bytes | None = None) -> dict:
    """Проверить SHA256SUMS выпуска: подпись и суммы файлов рядом с ним."""
    sig_path = sig_path or sums_path + ".sig"
    text = open(sums_path, encoding="utf-8").read()
    sig = open(sig_path, encoding="utf-8").read().strip() if os.path.exists(sig_path) else ""
    ok_sig = bool(sig) and verify_text(text, sig, pub)
    base = os.path.dirname(os.path.abspath(sums_path))
    files = {}
    for name, dg in parse_sums(text).items():
        p = os.path.join(base, name)
        files[name] = "missing" if not os.path.exists(p) else ("ok" if sha256_file(p) == dg else "MISMATCH")
    return {"signature": "ok" if ok_sig else "INVALID", "files": files}


def describe(res: dict) -> str:
    st = res["status"]
    if st == "ok":
        return f"целостность: ok · {res['files']} файлов · подпись {res['signer']} ({res['key']})"
    if st == "dev":
        return "целостность: рабочая копия (манифеста нет — сборка не подписана)"
    if st == "modified":
        return f"целостность: ИЗМЕНЕНЫ файлы ({len(res['changed'])}): " + ", ".join(res["changed"][:8])
    if st == "no-key":
        return "целостность: в программе нет открытого ключа подписанта"
    return f"целостность: ПОДПИСЬ НЕВЕРНА ({res['signer']})"
