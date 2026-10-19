"""Alertele CRM: colectarea si trimiterea pe canalele deja configurate.

RO: regulile (ce e o alerta, cum arata textul, cind se repeta) sint in
`alerts.py`; aici sint interogarile si trimiterea. Conditiile comenzilor NU
se scriu din nou: se iau din `process.stage_where` / `overdue_where`, ca sa
existe un singur adevar despre etape (regula prototipului).

Canalele NU se configureaza a doua oara (cerinta proprietarului 08.09.2026:
«Telegram si WhatsApp sint deja setate pentru comenzile de pe site, folositi
acele setari»): pentru OfficePlus sumarul pleaca prin `Biro26Notify.send_all`
— exact canalele bifate in «Setari notificari» ale magazinului (e-mail,
Telegram, WhatsApp). Clientul din cabinet nu are acces la acele setari, deci
el indica doar `chat_id`-ul lui de Telegram, iar botul ramine cel al
magazinului — asa nu apar token-uri de clienti in baza.
EN: alerts are delivered through the channels already configured for site
orders (Biro26Notify.send_all); cabinet clients only add their chat id.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from models.biro26_notify import Biro26Notify

from modules.crm import alerts as A
from modules.crm import process
from modules.crm.store_process import CrmData
from modules.crm.tenant import CLIENT, OFFICE, Tenant

DEFAULT_CFG: Dict[str, Any] = {
    "enabled": 0, "tg_token": "", "tg_chat": "", "lang": "ro", "kinds": "",
    "days_before_due": 3, "min_debt": 0, "quiet_days": 1, "send_hour": 8, "last_run": None,
}
_EDITABLE = ("enabled", "tg_token", "tg_chat", "lang", "kinds", "days_before_due",
             "min_debt", "quiet_days", "send_hour")


# ── setari ────────────────────────────────────────────────────────────────
def get_cfg(data: CrmData) -> Dict[str, Any]:
    rows = data.rows("SELECT ENABLED, TG_TOKEN, TG_CHAT, LANG, KINDS, DAYS_BEFORE_DUE, MIN_DEBT, "
                     "QUIET_DAYS, SEND_HOUR, TO_CHAR(LAST_RUN,'YYYY-MM-DD HH24:MI') LAST_RUN "
                     "FROM CRM_ALERT_CFG t WHERE %s" % data.t.where(), data.t.params())
    cfg = dict(DEFAULT_CFG)
    if rows:
        r = rows[0]
        cfg.update({k: r.get(k) for k in DEFAULT_CFG if r.get(k) is not None})
        for k in ("enabled", "days_before_due", "quiet_days", "send_hour"):
            cfg[k] = int(cfg[k] or 0)
        cfg["min_debt"] = float(cfg["min_debt"] or 0)
    cfg["tg_token_own"] = bool((cfg.get("tg_token") or "").strip())
    cfg.pop("tg_token", None)                       # RO: tokenul nu iese niciodata din server
    cfg["channels"] = channels(data, cfg)
    cfg["configured"] = any(c["ready"] for c in cfg["channels"])
    return cfg


def shop_settings() -> Dict[str, str]:
    """RO: setarile de notificari ale magazinului (pagina biro26-notify-settings)."""
    try:
        r = Biro26Notify.get_settings()
        return (r.get("data") or {}) if r.get("success") else {}
    except Exception:                                            # noqa: BLE001
        return {}


def channels(data: CrmData, cfg: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """RO: pe unde pleaca sumarul. OfficePlus = canalele bifate pentru
    comenzile de pe site; clientul din cabinet = Telegram-ul lui."""
    s = shop_settings()
    if data.t.is_office:
        own = (cfg or {}).get("tg_chat") or ""
        if str(own).strip():                        # RO: chat propriu pentru CRM (rar, dar posibil)
            return [{"channel": "telegram", "target": str(own).strip(), "ready": bool(s.get("notify_tg_token")),
                     "source": "crm"}]
        out = [{"channel": "email", "target": s.get("notify_email_to") or "",
                "ready": s.get("notify_email_enabled") == "1" and bool(s.get("smtp_configured")), "source": "shop"},
               {"channel": "telegram", "target": s.get("notify_tg_chat") or "",
                "ready": s.get("notify_tg_enabled") == "1" and bool(s.get("notify_tg_token")) and bool(s.get("notify_tg_chat")),
                "source": "shop"},
               {"channel": "whatsapp",
                "target": (s.get("notify_wa_cloud_to") if s.get("notify_wa_mode") == "cloud" else s.get("notify_wa_phone")) or "",
                "ready": s.get("notify_wa_enabled") == "1" and bool(s.get("notify_wa_phone") or s.get("notify_wa_cloud_to")),
                "source": "shop"}]
        return [c for c in out if c["target"] or c["ready"]]
    chat = str((cfg or {}).get("tg_chat") or "").strip()
    return [{"channel": "telegram", "target": chat, "ready": bool(chat) and bool(_token_for(data)),
             "source": "crm"}]


def _token_for(data: CrmData) -> str:
    rows = data.rows("SELECT TG_TOKEN FROM CRM_ALERT_CFG t WHERE %s" % data.t.where(), data.t.params())
    own = (rows[0].get("tg_token") if rows else "") or ""
    return own.strip() or (shop_settings().get("notify_tg_token") or "").strip()


def save_cfg(data: CrmData, values: Dict[str, Any]) -> Dict[str, Any]:
    v = {k: values.get(k) for k in _EDITABLE if k in values}
    if "lang" in v and v["lang"] not in ("ro", "ru", "en"):
        raise ValueError("lang: doar ro / ru / en")
    if "kinds" in v and v["kinds"]:
        bad = [k for k in str(v["kinds"]).split(",") if k.strip() and k.strip() not in A.ALL_KINDS]
        if bad:
            raise ValueError("kinds: tip necunoscut %s" % ", ".join(bad))
    if "send_hour" in v and not 0 <= int(v["send_hour"] or 0) <= 23:
        raise ValueError("send_hour: 0..23")
    cur = data.rows("SELECT OWNER_ID FROM CRM_ALERT_CFG t WHERE %s" % data.t.where(), data.t.params())
    p = dict(data.t.params())
    cols = {"enabled": ":enabled", "tg_chat": ":tg_chat", "lang": ":lang", "kinds": ":kinds",
            "days_before_due": ":days_before_due", "min_debt": ":min_debt",
            "quiet_days": ":quiet_days", "send_hour": ":send_hour", "tg_token": ":tg_token"}
    vals: Dict[str, Any] = {}
    for k in cols:
        if k not in v:
            continue
        if k == "enabled":
            vals[k] = 1 if str(v[k]) in ("1", "true", "True", "on") else 0
        elif k in ("days_before_due", "quiet_days", "send_hour"):
            vals[k] = int(v[k] or 0)
        elif k == "min_debt":
            vals[k] = float(str(v[k] or 0).replace(",", "."))
        else:
            vals[k] = (str(v[k] or "")).strip()[:200] or None
    if not vals:
        raise ValueError("nimic de salvat")
    if cur:
        sets = ", ".join("%s = %s" % (k.upper(), cols[k]) for k in vals)
        data.dml("UPDATE CRM_ALERT_CFG t SET %s, UPDATED = SYSDATE WHERE %s" % (sets, data.t.where()),
                 dict(p, **vals))
    else:
        keys = list(vals)
        data.dml("INSERT INTO CRM_ALERT_CFG (OWNER_KIND, OWNER_ID, %s) VALUES (:ok, :oi, %s)"
                 % (", ".join(k.upper() for k in keys), ", ".join(cols[k] for k in keys)),
                 dict(p, **vals))
    return get_cfg(data)


# ── colectarea alertelor ──────────────────────────────────────────────────
def _orders(data: CrmData, where: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    return data.rows(
        "SELECT t.ID, t.DOC_NO, NVL(c.NAME,'-') CLIENT, NVL(t.TOTAL,0) TOTAL, NVL(t.PAID,0) PAID, "
        "NVL(t.ADVANCE,0) ADVANCE, t.STATUS, TO_CHAR(t.DUE_DATE,'YYYY-MM-DD') DUE, "
        "TO_CHAR(t.SHIP_DATE,'YYYY-MM-DD') SHIP FROM CRM_ORDER t "
        "LEFT JOIN CRM_CLIENT c ON c.ID = t.CLIENT_ID WHERE %s AND (%s) ORDER BY t.DUE_DATE, t.ID"
        % (data.t.where(), where), dict(data.t.params(), **params))


def collect(data: CrmData, cfg: Dict[str, Any], today: Optional[date] = None) -> List[A.Alert]:
    """RO: toate alertele active ale chiriasului, dupa setari."""
    today = today or date.today()
    want = A.enabled_kinds(cfg)
    min_debt = float(cfg.get("min_debt") or 0)
    out: List[A.Alert] = []

    def order_alert(kind: str, r: Dict[str, Any], amount: float = 0.0) -> A.Alert:
        return A.Alert(kind=kind, ref_id=int(r["id"]), title="#%s" % (r.get("doc_no") or r["id"]),
                       client=r.get("client") or "-", amount=amount, total=float(r.get("total") or 0),
                       due=r.get("due") or "", days=A.days_late(r.get("due"), today),
                       status=r.get("status") or "")

    if "debt" in want:                       # livrat si neplatit (etapa «asteptam plata»)
        w, p = process.stage_where("await_payment")
        for r in _orders(data, w, p):
            debt = float(r["total"] or 0) - float(r["paid"] or 0)
            if debt >= max(0.01, min_debt):
                a = order_alert("debt", r, debt)
                a.days = A.days_late(r.get("due"), today)
                out.append(a)

    if "overdue_work" in want:               # in lucru cu termenul depasit
        w, p = process.overdue_where("in_work")
        out += [order_alert("overdue_work", r, float(r["total"] or 0)) for r in _orders(data, w, p)]

    if "await_advance" in want:              # confirmat, avansul nu a intrat
        w, p = process.stage_where("await_advance")
        out += [order_alert("await_advance", r) for r in _orders(data, w, p)]

    if "ready_to_ship" in want:              # executat, livrarea neintocmita
        w, p = process.stage_where("ready_to_ship")
        out += [order_alert("ready_to_ship", r) for r in _orders(data, w, p)]

    if "unposted" in want:                   # executat/platit, dar necontabilizat
        rows = _orders(data, "t.STATUS IN (:u1, :u2) AND NVL(t.POSTED,0) = 0",
                       {"u1": "Выполнен", "u2": "Оплачен"})
        out += [order_alert("unposted", r) for r in rows]

    if "due_soon" in want:                   # termenul vine in N zile (inca nelivrat)
        n = max(0, int(cfg.get("days_before_due") or 0))
        if n:
            rows = _orders(data, "t.STATUS <> :cancel AND t.SHIP_DATE IS NULL AND t.DUE_DATE IS NOT NULL "
                                 "AND t.DUE_DATE >= TRUNC(SYSDATE) AND t.DUE_DATE <= TRUNC(SYSDATE) + :n",
                           {"cancel": "Отменён", "n": n})
            out += [order_alert("due_soon", r, float(r["total"] or 0)) for r in rows]

    if "project_debt" in want:               # proiect deschis cu bugetul neacoperit
        rows = data.rows(
            "SELECT t.ID, t.NAME, NVL(c.NAME,'-') CLIENT, NVL(t.BUDGET,0) BUDGET, NVL(t.PREPAID,0) PREPAID, "
            "NVL(t.PAID,0) PAID, t.STATUS, TO_CHAR(t.DUE_DATE,'YYYY-MM-DD') DUE FROM CRM_PROJECT t "
            "LEFT JOIN CRM_CLIENT c ON c.ID = t.CLIENT_ID WHERE %s AND t.STATUS NOT IN (:c1, :c2) "
            "AND NVL(t.BUDGET,0) - NVL(t.PREPAID,0) - NVL(t.PAID,0) > :m ORDER BY t.DUE_DATE, t.ID"
            % data.t.where(), dict(data.t.params(), c1="Закрыт", c2="Проигран", m=max(0.0, min_debt)))
        for r in rows:
            left = float(r["budget"] or 0) - float(r["prepaid"] or 0) - float(r["paid"] or 0)
            out.append(A.Alert(kind="project_debt", ref_id=int(r["id"]), title=r["name"][:60],
                               client=r.get("client") or "-", amount=left, total=float(r["budget"] or 0),
                               due=r.get("due") or "", days=A.days_late(r.get("due"), today),
                               status=r.get("status") or ""))

    if "deal_stale" in want:                 # oferta cu data de inchidere trecuta
        rows = data.rows(
            "SELECT t.ID, t.TITLE, NVL(c.NAME,'-') CLIENT, NVL(t.AMOUNT,0) AMOUNT, t.STAGE, "
            "TO_CHAR(t.CLOSE_DATE,'YYYY-MM-DD') DUE FROM CRM_DEAL t "
            "LEFT JOIN CRM_CLIENT c ON c.ID = t.CLIENT_ID WHERE %s AND t.STAGE IN (:s1, :s2) "
            "AND t.CLOSE_DATE IS NOT NULL AND t.CLOSE_DATE < TRUNC(SYSDATE) ORDER BY t.CLOSE_DATE, t.ID"
            % data.t.where(), dict(data.t.params(), s1="Предложение", s2="Переговоры"))
        out += [A.Alert(kind="deal_stale", ref_id=int(r["id"]), title=(r["title"] or "")[:60],
                        client=r.get("client") or "-", total=float(r["amount"] or 0),
                        due=r.get("due") or "", days=A.days_late(r.get("due"), today),
                        status=r.get("stage") or "") for r in rows]
    return out


# ── ce s-a trimis deja ────────────────────────────────────────────────────
def sent_map(data: CrmData) -> Dict[str, Dict[str, Any]]:
    rows = data.rows("SELECT ALERT_KEY, AMOUNT, TO_CHAR(SENT_AT,'YYYY-MM-DD') SENT_AT "
                     "FROM CRM_ALERT_SENT t WHERE %s" % data.t.where(), data.t.params())
    return {r["alert_key"]: r for r in rows}


def mark_sent(data: CrmData, items: List[A.Alert]) -> None:
    for a in items:
        data.dml("MERGE INTO CRM_ALERT_SENT s USING (SELECT :ok OK_, :oi OI_, :k K_ FROM dual) n "
                 "ON (s.OWNER_KIND = n.OK_ AND s.OWNER_ID = n.OI_ AND s.ALERT_KEY = n.K_) "
                 "WHEN MATCHED THEN UPDATE SET AMOUNT = :amt, SENT_AT = SYSDATE, KIND = :kind, "
                 "REF_TABLE = :tbl, REF_ID = :rid "
                 "WHEN NOT MATCHED THEN INSERT (OWNER_KIND, OWNER_ID, ALERT_KEY, KIND, REF_TABLE, REF_ID, AMOUNT) "
                 "VALUES (:ok, :oi, :k, :kind, :tbl, :rid, :amt)",
                 dict(data.t.params(), k=a.key, kind=a.kind, tbl=a.table, rid=a.ref_id,
                      amt=round(float(a.amount or a.total or 0), 2)))


def prune_sent(data: CrmData, alerts: List[A.Alert]) -> int:
    """RO: alertele rezolvate (nu mai apar) se sterg din istoric, ca la
    reaparitie sa fie anuntate din nou."""
    keys = {a.key for a in alerts}
    old = [k for k in sent_map(data) if k not in keys]
    for k in old:
        data.dml("DELETE FROM CRM_ALERT_SENT t WHERE t.ALERT_KEY = :k AND %s" % data.t.where(),
                 dict(data.t.params(), k=k))
    return len(old)


# ── trimiterea ────────────────────────────────────────────────────────────
def digest(data: CrmData, cfg: Optional[Dict[str, Any]] = None, only_new: bool = True,
           today: Optional[date] = None, url: str = "") -> Dict[str, Any]:
    """RO: pregateste sumarul. `only_new` = doar alertele care nu au fost deja
    trimise (regula de liniste); False = tot ce e deschis acum (previzualizare)."""
    cfg = cfg if cfg is not None else get_cfg(data)
    today = today or date.today()
    found = collect(data, cfg, today)
    if only_new:
        seen = sent_map(data)
        quiet = int(cfg.get("quiet_days") or 0)
        items = [a for a in found if A.should_resend(seen.get(a.key), a.amount or a.total, quiet, today)]
    else:
        items = found
    text = A.render(items, cfg.get("lang") or "ro", data.t.label, today, url)
    return {"alerts": items, "all": found, "text": text,
            "counts": {k: sum(1 for a in found if a.kind == k) for k in A.ALL_KINDS if any(x.kind == k for x in found)},
            "money": round(sum(a.amount for a in found if a.kind in A.MONEY_KINDS), 2)}


def send(data: CrmData, cfg: Optional[Dict[str, Any]] = None, only_new: bool = True,
         url: str = "", force: bool = False) -> Dict[str, Any]:
    """RO: trimite sumarul pe canalele deja configurate. `force` = si daca nu
    e nimic nou (butonul «Trimite acum»)."""
    cfg = cfg if cfg is not None else get_cfg(data)
    chans = cfg.get("channels") or channels(data, cfg)
    if not any(c["ready"] for c in chans):
        return {"success": False, "error": "niciun canal pregatit — verificati «Setari notificari» ale magazinului"
                                           if data.t.is_office else "Telegram chat_id lipseste"}
    d = digest(data, cfg, only_new=only_new, url=url)
    if not d["alerts"] and not force:
        return {"success": True, "sent": False, "reason": "nimic nou", "counts": d["counts"]}
    lang = cfg.get("lang") or "ro"
    subject = (A.TEXTS.get(lang) or A.TEXTS["ro"])["title"] % data.t.label
    own_chat = str(cfg.get("tg_chat") or "").strip()

    if data.t.is_office and not own_chat:
        # RO: exact canalele bifate pentru comenzile de pe site (e-mail / Telegram /
        #     WhatsApp), dar textul difera pe canal: callmebot trece mesajul prin
        #     URL si un sumar intreg da HTTP 414 — acolo pleaca varianta scurta.
        s = shop_settings()
        short = A.render_short(d["alerts"] or d["all"], lang, data.t.label, url=url)
        res: Dict[str, Any] = {}
        if s.get("notify_email_enabled") == "1":
            res["email"] = Biro26Notify._send_email(s, subject, d["text"])
        if s.get("notify_tg_enabled") == "1":
            res["telegram"] = Biro26Notify._send_telegram(s, d["text"])
        if s.get("notify_wa_enabled") == "1":
            # RO: modul 'cloud' nu are limita de adresa — acolo merge textul intreg
            res["whatsapp"] = Biro26Notify._send_whatsapp(
                s, d["text"] if s.get("notify_wa_mode") == "cloud" else short)
        ok = [k for k, v in res.items() if v.get("success")]
        if not ok:
            errs = "; ".join("%s: %s" % (k, v.get("error")) for k, v in res.items()) or "niciun canal activ"
            return {"success": False, "error": errs}
    else:
        token = _token_for(data)
        if not token:
            return {"success": False, "error": "Telegram token lipseste (setarile de notificari ale magazinului)"}
        one = Biro26Notify._send_telegram({"notify_tg_token": token, "notify_tg_chat": own_chat}, d["text"])
        if not one.get("success"):
            return {"success": False, "error": one.get("error")}
        res, ok = {"telegram": one}, ["telegram"]

    mark_sent(data, d["alerts"])
    prune_sent(data, d["all"])
    data.dml("UPDATE CRM_ALERT_CFG t SET LAST_RUN = SYSDATE WHERE %s" % data.t.where(), data.t.params())
    return {"success": True, "sent": True, "alerts": len(d["alerts"]), "open": len(d["all"]),
            "money": d["money"], "counts": d["counts"], "text": d["text"],
            "channels": ok, "results": {k: {"success": v.get("success"), "error": v.get("error")} for k, v in res.items()}}


# ── rularea programata (toti chiriasii) ───────────────────────────────────
def tenants_due(hour: Optional[int] = None) -> List[Tenant]:
    """RO: chiriasii cu alerte pornite; daca `hour` e dat — doar cei a caror
    ora de sumar coincide (timerul poate rula in fiecare ora)."""
    d = CrmData(Tenant(OFFICE, 0))
    sql = "SELECT OWNER_KIND, OWNER_ID, SEND_HOUR FROM CRM_ALERT_CFG WHERE ENABLED = 1"
    rows = d.rows(sql)
    out = []
    for r in rows:
        if hour is not None and int(r.get("send_hour") or 0) != int(hour):
            continue
        out.append(Tenant(str(r["owner_kind"]), int(r["owner_id"] or 0)))
    return out


def run_all(hour: Optional[int] = None, url: str = "", dry: bool = False) -> List[Dict[str, Any]]:
    res = []
    for t in tenants_due(hour):
        data = CrmData(t)
        try:
            if dry:
                d = digest(data, url=url)
                res.append({"tenant": t.label, "success": True, "sent": False, "alerts": len(d["alerts"]),
                            "open": len(d["all"]), "text": d["text"]})
            else:
                r = send(data, url=url)
                r["tenant"] = t.label
                res.append(r)
        except Exception as e:                                   # noqa: BLE001
            res.append({"tenant": t.label, "success": False, "error": str(e)[:300]})
    return res
