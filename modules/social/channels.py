"""Отправка в бесплатные площадки с API.

RO: Fiecare retea are propria functie. Cheile stau in setarile magazinului
    (YBIRO_SETTINGS), nu in cod: se schimba din administrare, fara
    redesfasurare - aceeasi regula ca la UNA_USERID.
EN: One function per network; keys live in the shop settings, not in code.

Что нужно получить для каждой площадки — docs/SEOForge/SOCIAL_AUTOMATION.md.
"""

from __future__ import annotations

from typing import Any, Dict, List

import requests

TIMEOUT = 20

# RO: cheile din setari / EN: the settings keys
KEYS = {
    "telegram": ("SOCIAL_TG_ENABLED", "SOCIAL_TG_TOKEN", "SOCIAL_TG_CHAT"),
    "facebook": ("SOCIAL_FB_ENABLED", "SOCIAL_FB_TOKEN", "SOCIAL_FB_PAGE_ID"),
    "instagram": ("SOCIAL_IG_ENABLED", "SOCIAL_IG_TOKEN", "SOCIAL_IG_USER_ID"),
    "vk": ("SOCIAL_VK_ENABLED", "SOCIAL_VK_TOKEN", "SOCIAL_VK_GROUP_ID"),
    "ok": ("SOCIAL_OK_ENABLED", "SOCIAL_OK_TOKEN", "SOCIAL_OK_GROUP_ID"),
}


def _setting(key: str, default: str = "") -> str:
    try:
        from models.biro26_oracle_store import Biro26Store
        return Biro26Store.get_setting(key, default)
    except Exception:                                        # noqa: BLE001
        return default


def enabled(network: str) -> bool:
    keys = KEYS.get(network)
    if not keys:
        return False
    on = _setting(keys[0], "0").strip() == "1"
    return on and bool(_setting(keys[1]).strip())


def configured() -> Dict[str, bool]:
    return {net: enabled(net) for net in KEYS}


def _ok(r) -> Dict[str, Any]:
    try:
        body = r.json()
    except Exception:                                        # noqa: BLE001
        body = {"raw": (r.text or "")[:200]}
    if r.status_code >= 400 or (isinstance(body, dict) and body.get("error")):
        return {"success": False, "error": str(body)[:300]}
    return {"success": True, "id": str((body or {}).get("id") or "")}


def send_telegram(text: str, **_) -> Dict[str, Any]:
    """RO: canal Telegram - gratuit, fara limite practice, cel mai simplu."""
    _, k_token, k_chat = KEYS["telegram"]
    token, chat = _setting(k_token).strip(), _setting(k_chat).strip()
    # RO: daca nu e configurat separat, refolosim canalul de notificari
    #     care deja functioneaza. EN: fall back to the working notify bot.
    # RO: cheile din YBIRO_SETTINGS sint cu MAJUSCULE - get_setting compara
    #     exact, iar varianta cu litere mici nu gaseste nimic.
    # EN: settings keys are UPPERCASE; get_setting matches exactly.
    if not token:
        token = _setting("NOTIFY_TG_TOKEN").strip()
    if not chat:
        chat = _setting("NOTIFY_TG_CHAT").strip()
    if not (token and chat):
        return {"success": False, "error": "Telegram не настроен"}
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": text,
                            "disable_web_page_preview": False},
                      timeout=TIMEOUT)
    return _ok(r)


def send_facebook(text: str, url: str = "", **_) -> Dict[str, Any]:
    """RO: postare pe Pagina Facebook prin Graph API.

    Cere un token de PAGINA de lunga durata; token-ul de utilizator nu
    merge si expira in ore.
    """
    _, k_token, k_page = KEYS["facebook"]
    token, page = _setting(k_token).strip(), _setting(k_page).strip()
    if not (token and page):
        return {"success": False, "error": "Facebook не настроен"}
    data = {"message": text, "access_token": token}
    if url:
        data["link"] = url
    r = requests.post(f"https://graph.facebook.com/v20.0/{page}/feed",
                      data=data, timeout=TIMEOUT)
    return _ok(r)


def send_instagram(text: str, image_url: str = "", **_) -> Dict[str, Any]:
    """RO: Instagram cere OBLIGATORIU o imagine si publica in doi pasi:
    intii se creaza containerul, apoi se publica."""
    _, k_token, k_user = KEYS["instagram"]
    token, user = _setting(k_token).strip(), _setting(k_user).strip()
    if not (token and user):
        return {"success": False, "error": "Instagram не настроен"}
    if not image_url:
        return {"success": False, "error": "Instagram требует изображение"}
    c = requests.post(f"https://graph.facebook.com/v20.0/{user}/media",
                      data={"image_url": image_url, "caption": text,
                            "access_token": token}, timeout=TIMEOUT)
    made = _ok(c)
    if not made.get("success") or not made.get("id"):
        return made
    p = requests.post(f"https://graph.facebook.com/v20.0/{user}/media_publish",
                      data={"creation_id": made["id"], "access_token": token},
                      timeout=TIMEOUT)
    return _ok(p)


def send_vk(text: str, url: str = "", **_) -> Dict[str, Any]:
    """RO: perete de grup VK. Token de grup cu drept `wall`."""
    _, k_token, k_group = KEYS["vk"]
    token, group = _setting(k_token).strip(), _setting(k_group).strip()
    if not (token and group):
        return {"success": False, "error": "VK не настроен"}
    r = requests.post("https://api.vk.com/method/wall.post",
                      data={"owner_id": f"-{group.lstrip('-')}",
                            "from_group": 1,
                            "message": text + ("\n" + url if url else ""),
                            "access_token": token, "v": "5.199"},
                      timeout=TIMEOUT)
    body = {}
    try:
        body = r.json()
    except Exception:                                        # noqa: BLE001
        pass
    if body.get("error"):
        return {"success": False,
                "error": str(body["error"].get("error_msg"))[:200]}
    return {"success": True, "id": str((body.get("response") or {}).get("post_id", ""))}


def send_ok(text: str, url: str = "", **_) -> Dict[str, Any]:
    """RO: Odnoklassniki - grup. API cere semnatura, de aceea aici se
    foloseste metoda simpla cu token de aplicatie."""
    _, k_token, k_group = KEYS["ok"]
    token, group = _setting(k_token).strip(), _setting(k_group).strip()
    if not (token and group):
        return {"success": False, "error": "OK не настроен"}
    import json as _json
    attach = _json.dumps({"media": [{"type": "text", "text": text
                                     + ("\n" + url if url else "")}]})
    r = requests.post("https://api.ok.ru/fb.do",
                      data={"method": "mediatopic.post", "gid": group,
                            "type": "GROUP_THEME", "attachment": attach,
                            "access_token": token, "format": "json"},
                      timeout=TIMEOUT)
    return _ok(r)


SENDERS = {
    "telegram": send_telegram,
    "facebook": send_facebook,
    "instagram": send_instagram,
    "vk": send_vk,
    "ok": send_ok,
}


def publish(post: Dict[str, str], networks: List[str] = None) -> Dict[str, Any]:
    """RO: publica in toate retelele PORNITE; rezultat separat pe fiecare."""
    out: Dict[str, Any] = {}
    for net in (networks or list(SENDERS)):
        if networks is None and not enabled(net):
            continue
        try:
            # RO: cautam expeditorul PE NUME, nu prin referinta prinsa la
            #     import - altfel un test nu-l poate inlocui si ar trimite
            #     mesaje adevarate.
            # EN: look the sender up by name so tests can replace it.
            sender = globals().get(f"send_{net}") or SENDERS[net]
            out[net] = sender(post.get("text", ""),
                                    url=post.get("url", ""),
                                    image_url=post.get("image_url", ""))
        except Exception as e:                               # noqa: BLE001
            out[net] = {"success": False, "error": str(e)[:200]}
    return out
