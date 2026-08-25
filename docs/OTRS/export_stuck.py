#!/usr/bin/env python3
"""Выгрузка застрявших писем (STATUS=1) из очереди UN9MAIL_MSG в .eml + zip.

    venv/bin/python docs/OTRS/export_stuck.py

Кладёт результат в docs/OTRS/export/un9mail_stuck_<дата>.zip:
  otrs/<nrmsg>_<дата>_<получатель>.eml     — 80 писем сотрудникам
  tickets/<nrmsg>_...eml                   — 722 письма клиентам
  index.csv                                — сводная таблица
Файлы .eml открываются любым почтовым клиентом и пересылаются как есть.
"""
import csv
import io
import subprocess
import sys
import zipfile
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from models.unisim_cassa import _call_worker, _rows  # noqa: E402

DSN = "orange.una.md:4024/cloudbd.world"
OUT = ROOT / "docs/OTRS/export"
SCHEMAS = {"otrs": "oracle-cloudbd-otrs", "tickets": "oracle-cloudbd-tickets"}


def auth(user, keychain):
    pw = subprocess.run(["security", "find-generic-password", "-s", keychain, "-w"],
                        capture_output=True, text=True, check=True).stdout.strip()
    return {"user": user, "password": pw, "dsn": DSN}


def safe(s, n=40):
    keep = "".join(c if c.isalnum() or c in "-_.@" else "_" for c in (s or ""))
    return keep[:n] or "no_addr"


def fetch(a):
    """Тело письма — CLOB, тянем отдельным запросом на письмо, иначе воркер
    отдаёт LOB-обёртку вместо текста."""
    heads = _rows(_call_worker(a,
        "SELECT NRMSG, SUBJECT, SENDER, RECIPIENTS, CC, BCC, "
        "TO_CHAR(SENT_DATE,'YYYY-MM-DD HH24:MI:SS') SD, SUBSTR(ERR_MSG,1,300) EM "
        "FROM UN9MAIL_MSG WHERE STATUS=1 ORDER BY NRMSG", 120))
    out = []
    for h in heads:
        body = _rows(_call_worker(a,
            f"SELECT TO_CHAR(SUBSTR(TEXT,1,3900)) T1, "
            f"TO_CHAR(SUBSTR(TEXT,3901,3900)) T2, TO_CHAR(SUBSTR(TEXT,7801,3900)) T3 "
            f"FROM UN9MAIL_MSG WHERE NRMSG={h['nrmsg']}", 60))
        h["body"] = "".join((body[0].get(k) or "") for k in ("t1", "t2", "t3")) if body else ""
        out.append(h)
    return out


def to_eml(m):
    msg = EmailMessage()
    msg["Subject"] = m.get("subject") or ""
    msg["From"] = m.get("sender") or ""
    msg["To"] = m.get("recipients") or ""
    if m.get("cc"):
        msg["Cc"] = m["cc"]
    if m.get("bcc"):
        msg["Bcc"] = m["bcc"]
    msg["Date"] = m.get("sd") or ""
    msg["X-Un9mail-Nrmsg"] = str(m.get("nrmsg"))
    if m.get("em"):
        msg["X-Un9mail-Error"] = " ".join(str(m["em"]).split())
    msg.set_content(m.get("body") or "", subtype="html")
    return msg.as_bytes()


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    zpath = OUT / f"un9mail_stuck_{stamp}.zip"
    index = io.StringIO()
    w = csv.writer(index)
    w.writerow(["схема", "nrmsg", "дата", "отправитель", "получатель", "тема", "байт", "ошибка"])
    total = 0
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for user, kc in SCHEMAS.items():
            msgs = fetch(auth(user, kc))
            print(f"{user}: писем {len(msgs)}")
            for m in msgs:
                name = f"{user}/{m['nrmsg']}_{(m.get('sd') or '')[:10]}_{safe(m.get('recipients'))}.eml"
                z.writestr(name, to_eml(m))
                w.writerow([user, m["nrmsg"], m.get("sd"), m.get("sender"), m.get("recipients"),
                            m.get("subject"), len(m.get("body") or ""),
                            " ".join(str(m.get("em") or "").split())[:160]])
                total += 1
        z.writestr("index.csv", index.getvalue())
    print(f"\nготово: {zpath} ({total} писем, {zpath.stat().st_size // 1024} КБ)")
