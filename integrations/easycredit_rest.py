"""EasyCredit — REST/JSON gateway (api.ecredit.md).

RO: Gateway-ul nou al EasyCredit e REST (FastAPI), NU SOAP ca vechiul
    tst.ecmoldova.cloud:8082. Doua nivele de autentificare:
      * HTTP Basic pe cerere            -> basic_user / basic_password
      * Login/Password in corpul JSON   -> user / passwd
    URL: {base_url}/{environment}/{operatie}, environment = TEST | PRODUCTION.
    Schema: https://api.ecredit.md/openapi.json

EN: EasyCredit's new gateway is REST (FastAPI), not the old SOAP service.
    It needs BOTH HTTP Basic on the request and Login/Password in the JSON body.

Operatiile folosite de magazin / operations used by the shop:
    Preapproved_v2_1  — suma preaprobata pentru un IDNP
    eShopRequest_V5   — cererea de credit pentru PERSOANE FIZICE (4 cimpuri
                        obligatorii). Atentie: Request_v4_PJ e pentru persoane
                        JURIDICE si cere 19 cimpuri (firma, director, fondator).
    URNStatus_v2      — statusul cererii dupa URN

Functiile intorc ACELEASI forme ca integrations/easycredit_client.py, ca
straturile de deasupra (provider, models/biro26_credit.py) sa nu se schimbe.
"""
from __future__ import annotations

from typing import Any

import requests

TIMEOUT = 30


def _split_env(base_url: str) -> tuple[str, str]:
    """RO: din `https://api.ecredit.md/TEST/` -> (`https://api.ecredit.md`, `TEST`).

    Daca mediul nu e in URL, cade pe TEST — mai sigur decit PRODUCTION.
    """
    u = (base_url or "").rstrip("/")
    for env in ("TEST", "PRODUCTION"):
        if u.upper().endswith("/" + env):
            return u[: -(len(env) + 1)], env
    return u, "TEST"


def _post(base_url: str, op: str, payload: dict[str, Any],
          basic_user: str = "", basic_password: str = "",
          verify_ssl: bool = True) -> tuple[dict[str, Any] | None, str | None]:
    """POST JSON. Intoarce (raspuns, eroare) — exact una din ele e None."""
    root, env = _split_env(base_url)
    url = f"{root}/{env}/{op}"
    try:
        r = requests.post(url, json=payload, timeout=TIMEOUT, verify=verify_ssl,
                          auth=(basic_user, basic_password) if basic_user else None)
    except requests.RequestException as e:
        return None, str(e)
    try:
        j = r.json()
    except ValueError:
        return None, (f"HTTP {r.status_code}: {(r.text or '')[:200]}" if r.status_code >= 400
                      else f"raspuns care nu e JSON: {(r.text or '')[:200]}")
    if r.status_code >= 400 and not (isinstance(j, dict) and "response" in j):
        # RO: eroare adevarata de transport — corpul e {"detail": ...}
        detail = j.get("detail") if isinstance(j, dict) else None
        return None, f"HTTP {r.status_code}: {detail if detail is not None else (r.text or '')[:200]}"
    # RO: ATENTIE — gateway-ul raspunde 404 si cind clientul pur si simplu nu e
    #     gasit ("Wrong Customer - 50000"), dar corpul e plicul normal. Asta NU
    #     e o eroare tehnica: se despacheteaza si se citeste Status ca de obicei.
    # EN: the gateway answers 404 for "client not found" too, with the normal
    #     envelope — unwrap it instead of reporting a transport error.
    # RO: gateway-ul intoarce un PLIC {"request": {...}, "response": {...}} —
    #     cimpurile utile (Status, URN, MaxAutoApprove...) sint in "response".
    #     Fara despachetare totul pare gol: preapproved 0, URN lipsa.
    # EN: the gateway wraps everything in {"request", "response"}; the useful
    #     fields live under "response" — unwrap or everything reads as empty.
    if isinstance(j, dict) and "response" in j:
        inner = j.get("response")
        return (inner if isinstance(inner, dict) else {"value": inner}), None
    return j, None


def _preapproved_message(status: str, approved: bool) -> str:
    """RO: statusul tehnic al gateway-ului -> text pentru client."""
    s = (status or "").lower()
    if "wrong customer" in s:
        # RO: IDNP-ul nu e in baza EasyCredit — nu e o defectiune tehnica
        return "Clientul nu a fost găsit la EasyCredit. / Клиент не найден в базе EasyCredit."
    if "wrong" in s or "error" in s:
        return status
    return status or ("Предодобрено." if approved else "Не предодобрено.")


def preapproved(
    base_url: str,
    user: str,
    passwd: str,
    idn: str = "",
    amount: int | float = 0,
    phone: str = "",
    birth_date: str = "",
    card_id: str = "",
    verify_ssl: bool = True,
    basic_user: str = "",
    basic_password: str = "",
) -> dict[str, Any]:
    """Preapproved_v2_1 — suma preaprobata. `amount` nu e cerut de gateway."""
    # RO: cimpurile optionale NU se trimit goale — gateway-ul valideaza
    #     lungimea (ex. `cardid` cere minim 16 caractere) si respinge "".
    # EN: never send empty optional fields — the gateway validates their
    #     length and rejects an empty string.
    payload = {"Login": user, "Password": passwd, "UIN": idn or "",
               "BirthDate": birth_date or "", "Phone": phone or ""}
    if card_id:
        payload["cardid"] = card_id
    d, err = _post(base_url, "Preapproved_v2_1", payload,
                   basic_user, basic_password, verify_ssl)
    if err:
        return {"success": False,
                "data": {"preapproved": False, "max_amount": 0, "message": err},
                "error": err}
    status = str(d.get("Status") or "")
    mx_reuseste = int(float(d.get("MaxAutoApproveAmountForReuseste") or 0))

    mx_esimplu = int(float(d.get("MaxAutoApproveAmountForeSimplu") or 0))
    max_amount = max(mx_reuseste, mx_esimplu)
    is_approved = max_amount > 0 and "Wrong" not in status
    return {"success": True, "data": {
        "preapproved": is_approved,
        "max_amount": max_amount,
        "max_reuseste": mx_reuseste,
        "max_esimplu": mx_esimplu,
        "status": status,
        "message": _preapproved_message(status, is_approved),
        "first_name": d.get("FirstName"),
        "last_name": d.get("LastName"),
        "father_name": d.get("FatherName"),
        "birth_date": d.get("BirthDate"),
    }}


def submit_request(
    base_url: str,
    user: str,
    passwd: str,
    *,
    amount: int | float = 0,
    fio: str = "",
    phone: str = "",
    idn: str = "",
    product_name: str = "",
    program_name: str = "",
    product_id: int | str = 0,
    goods_price: int | float = 0,
    months: int = 0,
    verify_ssl: bool = True,
    basic_user: str = "",
    basic_password: str = "",
) -> dict[str, Any]:
    """eShopRequest_V5 — cererea de credit pentru persoane fizice.

    RO: gateway-ul cere doar suma si numarul de rate; `Mobile`/`ProductId`
        sint optionale. Numarul de rate se ia din `months`, iar daca lipseste,
        din coada lui `program_name` ("0-0-12" -> 12).
    """
    n = int(months or 0)
    if n <= 0:
        tail = str(program_name or "").rsplit("-", 1)[-1]
        n = int(tail) if tail.isdigit() else 0
    if n <= 0:
        return {"success": False, "data": {"urn": "", "message": "numar de rate lipsa"},
                "error": "NumberOfInstallments is required"}
    payload: dict[str, Any] = {
        "Login": user, "Password": passwd,
        "CreditAmount": float(amount or goods_price or 0),
        "NumberOfInstallments": n,
    }
    if phone:
        payload["Mobile"] = phone
    if product_id:
        payload["ProductId"] = str(product_id)
    d, err = _post(base_url, "eShopRequest_V5", payload,
                   basic_user, basic_password, verify_ssl)
    if err:
        return {"success": False, "data": {"urn": "", "message": err}, "error": err}
    urn = str(d.get("URN") or "")
    status = str(d.get("Status") or "")
    if not urn:
        return {"success": False, "data": {"urn": "", "status": status, "message": status},
                "error": status or "gateway-ul nu a returnat URN"}
    return {"success": True, "data": {"urn": urn, "status": status,
                                      "message": status or "Cerere înregistrată."}}


def status(
    base_url: str,
    user: str,
    passwd: str,
    urn: str,
    verify_ssl: bool = True,
    basic_user: str = "",
    basic_password: str = "",
) -> dict[str, Any]:
    """URNStatus_v2 — statusul cererii dupa URN."""
    if not (urn or "").strip():
        return {"success": False, "data": {"urn": "", "status": "", "message": "URN не указан."},
                "error": "URN required"}
    d, err = _post(base_url, "URNStatus_v2",
                   {"Login": user, "Password": passwd, "URN": urn},
                   basic_user, basic_password, verify_ssl)
    if err:
        return {"success": False, "data": {"urn": urn, "status": "", "message": err},
                "error": err}
    st = str(d.get("DocumentStatus") or d.get("Status") or "")
    return {"success": True, "data": {
        "urn": urn, "status": st, "message": st,
        "loan_amount": d.get("LoanAmount"),
        "installments": d.get("Installments"),
        "installment_amount": d.get("InstallmentAmount"),
    }}


def get_client_info(
    base_url: str,
    user: str,
    passwd: str,
    uin: str = "",
    verify_ssl: bool = True,
    basic_user: str = "",
    basic_password: str = "",
) -> dict[str, Any]:
    """eShopClientInfo_v3 — datele clientului dupa IDNP."""
    d, err = _post(base_url, "eShopClientInfo_v3",
                   {"Login": user, "Password": passwd, "Uin": uin},
                   basic_user, basic_password, verify_ssl)
    if err:
        return {"success": False, "data": {}, "error": err}
    return {"success": True, "data": d}
