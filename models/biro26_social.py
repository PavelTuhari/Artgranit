"""RO: Biro26Social — atributia traficului din retele sociale / reclama.

Contur (ca in sistemele e-commerce mature — WooCommerce Order Attribution,
Matomo, GA4):

1. Nucleul site-ului (Flask) prinde TOATE click-ID-urile cunoscute
   (fbclid, gclid, ttclid, twclid, msclkid, yclid, li_fat_id, igshid,
   ScCid, epik...), parametrii utm_* si referrer-ul social/organic.
2. Prima si ultima atingere se tin intr-un cookie first-party (90 zile),
   vizitatorul primeste un ID anonim.
3. Vizitele atribuite si conversiile (facturi, comenzi B2B, cereri de
   credit) se scriu in BAZA WORDPRESS (MySQL, prefix `wp_`) — WordPress
   este «receptionerul» traficului extern, iar analiza eficientei
   retelelor se face din pluginul WP `officeplus-social-analytics`.

Scrierea e fail-silent si asincrona (coada + fir daemon): daca MySQL
lipseste (de ex. pe conturul nufarul), modulul tace si nu incetineste
site-ul. Configurare prin .env: WP_DB_HOST / WP_DB_NAME / WP_DB_USER /
WP_DB_PASSWORD (parola ramane pe server, nu in repo).

EN: social-traffic attribution core. Captures ad click IDs + UTM +
referrer, keeps first/last touch in a cookie, logs attributed visits and
conversions into the WordPress MySQL schema; a WP admin plugin renders
the effectiveness dashboard. Async + fail-silent by design.
"""

import hashlib
import json
import os
import queue
import threading
import time
import uuid
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

# ── cookie-uri (first-party) ───────────────────────────────────────────
VISITOR_COOKIE = "op_vid"     # ID anonim de vizitator (uuid hex)
ATTR_COOKIE = "op_attr"       # JSON compact {f:{...prima}, l:{...ultima}}
COOKIE_DAYS = 90              # standardul de atributie (Meta/Google)

# ── click-ID-urile platformelor de reclama / retele ────────────────────
# RO: param URL -> canal; ordinea conteaza doar la afisare.
CLICK_IDS = (
    ("fbclid",    "facebook"),      # Meta: Facebook (si Instagram Ads)
    ("gclid",     "google-ads"),
    ("gbraid",    "google-ads"),
    ("wbraid",    "google-ads"),
    ("ttclid",    "tiktok"),
    ("twclid",    "twitter"),
    ("msclkid",   "bing-ads"),
    ("yclid",     "yandex-direct"),
    ("li_fat_id", "linkedin"),
    ("igshid",    "instagram"),
    ("igsh",      "instagram"),
    ("ScCid",     "snapchat"),
    ("epik",      "pinterest"),
    ("mc_eid",    "email"),         # Mailchimp
    ("vk_ref",    "vk"),
)
# RO: parametrii de tracking care se curata din URL pe client (site.js)
TRACKING_PARAMS = tuple(p for p, _ in CLICK_IDS) + (
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")

# ── clasificare dupa referrer (trafic organic din retele) ──────────────
REF_DOMAINS = (
    (("facebook.", "fb.me", "fb.com", "messenger."), "facebook"),
    (("instagram.", "l.instagram."),                 "instagram"),
    (("t.me", "telegram.", "web.telegram."),         "telegram"),
    (("tiktok.",),                                   "tiktok"),
    (("twitter.", "t.co", "x.com"),                  "twitter"),
    (("linkedin.", "lnkd.in"),                       "linkedin"),
    (("vk.com", "vk.ru", "away.vk.com"),             "vk"),
    (("ok.ru", "odnoklassniki."),                    "odnoklassniki"),
    (("youtube.", "youtu.be"),                       "youtube"),
    (("pinterest.",),                                "pinterest"),
    (("viber.",),                                    "viber"),
    (("wa.me", "whatsapp."),                         "whatsapp"),
    (("google.",),                                   "google-organic"),
    (("yandex.", "ya.ru"),                           "yandex-organic"),
    (("bing.",),                                     "bing-organic"),
    (("mail.ru",),                                   "mailru"),
)
# RO: normalizarea utm_source -> canal (fb, ig, tg etc.)
UTM_SOURCES = {
    "fb": "facebook", "facebook": "facebook", "meta": "facebook",
    "ig": "instagram", "instagram": "instagram",
    "tg": "telegram", "telegram": "telegram",
    "tiktok": "tiktok", "tt": "tiktok",
    "twitter": "twitter", "x": "twitter",
    "vk": "vk", "ok": "odnoklassniki", "odnoklassniki": "odnoklassniki",
    "linkedin": "linkedin", "youtube": "youtube", "yt": "youtube",
    "google": "google-ads", "yandex": "yandex-direct",
    "viber": "viber", "whatsapp": "whatsapp", "wa": "whatsapp",
    "email": "email", "newsletter": "email", "mailchimp": "email",
}

_IP_SALT = "op26-social"


class Biro26Social:
    """Atributie sociala: captare -> cookie -> MySQL WordPress."""

    _q: "queue.Queue[tuple]" = queue.Queue(maxsize=1000)
    _worker_started = False
    _tables_ready = False
    _lock = threading.Lock()

    # ── configurare MySQL (baza WordPress) ─────────────────────────────
    @staticmethod
    def _cfg() -> Optional[Dict[str, str]]:
        name = os.environ.get("WP_DB_NAME")
        user = os.environ.get("WP_DB_USER")
        pwd = os.environ.get("WP_DB_PASSWORD")
        if not (name and user and pwd):
            return None
        return {"host": os.environ.get("WP_DB_HOST", "localhost"),
                "db": name, "user": user, "password": pwd}

    @staticmethod
    def enabled() -> bool:
        return Biro26Social._cfg() is not None

    # ── clasificarea cererii ───────────────────────────────────────────
    @staticmethod
    def classify(args: Dict[str, str], referrer: str) -> Optional[Dict[str, Any]]:
        """RO: intoarce atributia {channel, click_param, click_id, utm_*}
        sau None daca cererea nu are niciun semnal (vizita directa)."""
        a: Dict[str, Any] = {}
        for param, channel in CLICK_IDS:
            v = args.get(param)
            if v:
                a["channel"] = channel
                a["click_param"] = param
                a["click_id"] = str(v)[:512]
                break
        for u in ("utm_source", "utm_medium", "utm_campaign",
                  "utm_content", "utm_term"):
            v = args.get(u)
            if v:
                a[u] = str(v)[:150]
        # RO: utm_source poate preciza canalul (fbclid vine si din Instagram)
        if a.get("utm_source") and "channel" not in a:
            a["channel"] = UTM_SOURCES.get(
                a["utm_source"].strip().lower(),
                "utm-" + a["utm_source"].strip().lower()[:24])
        host = (urlsplit(referrer or "").hostname or "").lower()
        if host:
            for needles, channel in REF_DOMAINS:
                if any(n in host for n in needles):
                    a.setdefault("channel", channel)
                    break
            a.setdefault("referrer", (referrer or "")[:512])
        # RO: fbclid + referrer instagram => canalul real e Instagram
        if a.get("channel") == "facebook" and "instagram" in host:
            a["channel"] = "instagram"
        return a if a.get("channel") else None

    # ── integrare Flask: apel din before/after_request ─────────────────
    @staticmethod
    def on_request(req) -> Optional[Dict[str, Any]]:
        """RO: proceseaza o cerere de pagina din vitrina. Intoarce dict-ul
        {set_cookies: {...}} cind cookie-urile trebuie (re)scrise; logheaza
        vizita atribuita in fundal. Fail-silent integral."""
        try:
            attr = Biro26Social.classify(req.args, req.referrer or "")
            vid = req.cookies.get(VISITOR_COOKIE)
            new_vid = False
            if not vid or len(vid) != 32:
                vid = uuid.uuid4().hex
                new_vid = True
            if not attr:
                # RO: vizita directa — doar ID-ul de vizitator, daca lipseste
                return ({"set_cookies": {VISITOR_COOKIE: vid}}
                        if new_vid else None)
            # RO: cookie-ul de atributie: prima atingere se pastreaza,
            #     ultima se actualizeaza (first & last touch, ca in Woo)
            touch = {"c": attr["channel"],
                     "s": attr.get("utm_source") or "",
                     "cp": attr.get("utm_campaign") or "",
                     "t": int(time.time())}
            try:
                cur = json.loads(req.cookies.get(ATTR_COOKIE) or "{}")
            except (ValueError, TypeError):
                cur = {}
            if not isinstance(cur, dict) or "f" not in cur:
                cur = {"f": touch}
            cur["l"] = touch
            ip = (req.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                  or req.remote_addr or "")
            Biro26Social._enqueue(("visit", {
                "visitor": vid, "channel": attr["channel"],
                "click_param": attr.get("click_param"),
                "click_id": attr.get("click_id"),
                "utm_source": attr.get("utm_source"),
                "utm_medium": attr.get("utm_medium"),
                "utm_campaign": attr.get("utm_campaign"),
                "utm_content": attr.get("utm_content"),
                "utm_term": attr.get("utm_term"),
                "landing": req.path[:512],
                "referrer": attr.get("referrer"),
                "ua": (req.user_agent.string or "")[:256],
                # RO: IP doar ca hash sarat scurt (fara date personale)
                "ip_hash": hashlib.sha256(
                    (_IP_SALT + ip).encode()).hexdigest()[:16],
            }))
            return {"set_cookies": {
                VISITOR_COOKIE: vid,
                ATTR_COOKIE: json.dumps(cur, separators=(",", ":"))}}
        except Exception:                                    # noqa: BLE001
            return None

    @staticmethod
    def conversion(req, kind: str, doc: Any = None,
                   amount: Any = None) -> None:
        """RO: inregistreaza o conversie (factura / comanda B2B / cerere de
        credit) cu atributia din cookie; canal 'direct' cind nu exista."""
        try:
            try:
                cur = json.loads(req.cookies.get(ATTR_COOKIE) or "{}")
            except (ValueError, TypeError):
                cur = {}
            f = cur.get("f") or {}
            l = cur.get("l") or {}
            try:
                amt = round(float(amount), 2) if amount is not None else None
            except (TypeError, ValueError):
                amt = None
            Biro26Social._enqueue(("conv", {
                "visitor": req.cookies.get(VISITOR_COOKIE) or "",
                "first_channel": f.get("c") or "direct",
                "last_channel": l.get("c") or "direct",
                "utm_campaign": (l.get("cp") or f.get("cp") or "")[:150],
                "kind": kind[:24],
                "doc_cod": (str(doc)[:40] if doc is not None else None),
                "amount": amt,
            }))
        except Exception:                                    # noqa: BLE001
            pass

    # ── scrierea asincrona in MySQL ────────────────────────────────────
    @staticmethod
    def _enqueue(item: tuple) -> None:
        if not Biro26Social.enabled():
            return
        with Biro26Social._lock:
            if not Biro26Social._worker_started:
                threading.Thread(target=Biro26Social._worker,
                                 daemon=True).start()
                Biro26Social._worker_started = True
        try:
            Biro26Social._q.put_nowait(item)
        except queue.Full:
            pass                       # RO: mai bine pierdem un rand decit sa blocam site-ul

    @staticmethod
    def _connect():
        import pymysql
        c = Biro26Social._cfg()
        return pymysql.connect(host=c["host"], user=c["user"],
                               password=c["password"], database=c["db"],
                               charset="utf8mb4", connect_timeout=4,
                               autocommit=True)

    # RO: DDL identic cu cel din pluginul WP (dbDelta) — cine ajunge primul
    #     creeaza tabelele; IF NOT EXISTS le face idempotente.
    DDL = (
        """CREATE TABLE IF NOT EXISTS wp_op_social_visit (
             id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
             ts DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
             visitor CHAR(32) NOT NULL,
             channel VARCHAR(32) NOT NULL,
             click_param VARCHAR(24) NULL,
             click_id VARCHAR(512) NULL,
             utm_source VARCHAR(150) NULL,
             utm_medium VARCHAR(150) NULL,
             utm_campaign VARCHAR(150) NULL,
             utm_content VARCHAR(150) NULL,
             utm_term VARCHAR(150) NULL,
             landing VARCHAR(512) NULL,
             referrer VARCHAR(512) NULL,
             ua VARCHAR(256) NULL,
             ip_hash CHAR(16) NULL,
             KEY ix_ts (ts), KEY ix_ch (channel, ts), KEY ix_vis (visitor)
           ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        """CREATE TABLE IF NOT EXISTS wp_op_social_conv (
             id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
             ts DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
             visitor CHAR(32) NOT NULL,
             first_channel VARCHAR(32) NOT NULL,
             last_channel VARCHAR(32) NOT NULL,
             utm_campaign VARCHAR(150) NULL,
             kind VARCHAR(24) NOT NULL,
             doc_cod VARCHAR(40) NULL,
             amount DECIMAL(12,2) NULL,
             currency CHAR(3) NOT NULL DEFAULT 'MDL',
             KEY ix_ts (ts), KEY ix_ch (last_channel, ts),
             KEY ix_vis (visitor)
           ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    )

    @staticmethod
    def _worker() -> None:
        """RO: fir daemon — goleste coada in MySQL; la eroare reincearca
        conexiunea la urmatorul rand, fara sa afecteze site-ul."""
        conn = None
        while True:
            kind, row = Biro26Social._q.get()
            for _attempt in (1, 2):
                try:
                    if conn is None:
                        conn = Biro26Social._connect()
                        if not Biro26Social._tables_ready:
                            with conn.cursor() as cur:
                                for ddl in Biro26Social.DDL:
                                    cur.execute(ddl)
                            Biro26Social._tables_ready = True
                    table = ("wp_op_social_visit" if kind == "visit"
                             else "wp_op_social_conv")
                    cols = [k for k, v in row.items() if v is not None]
                    sql = ("INSERT INTO %s (%s) VALUES (%s)"
                           % (table, ",".join(cols),
                              ",".join(["%s"] * len(cols))))
                    with conn.cursor() as cur:
                        cur.execute(sql, [row[k] for k in cols])
                    break
                except Exception:                            # noqa: BLE001
                    try:
                        if conn is not None:
                            conn.close()
                    except Exception:                        # noqa: BLE001
                        pass
                    conn = None      # RO: a doua incercare cu conexiune noua
