"""Маршруты модуля «Инструкция OpenVPN».

Адреса без префикса /UNA.md/orasldev/vpnguide — его подставляет ядро.

* `/`                          — общая инструкция для сотрудников, под входом;
* `/s/<токен>`                 — персональная инструкция с файлом, БЕЗ входа:
                                 у получателя учётной записи портала нет;
* `/s/<токен>/profile`         — сам файл .ovpn;
* `/s/<токен>/instructions.md` — то же простым текстом для ИИ-агента;
* `/s/<токен>/windows.ps1`, `/s/<токен>/apple.mobileconfig` — для L2TP:
                                 готовая настройка Windows и macOS/iPhone.

Ссылки по токену живут 15 минут по умолчанию (rules.TTL_DEFAULT). Устройство
защиты — в docstring rules.py.
"""
import os

from flask import Response, abort, redirect, render_template, request, url_for

from controllers.auth_controller import AuthController
from modules.vpnguide import blueprint, rules

# Платформы в порядке показа: ключ вкладки, подпись.
PLATFORMS = [
    ("windows", "Windows"),
    ("macos", "macOS"),
    ("iphone", "iPhone / iPad"),
    ("android", "Android"),
    ("linux", "Linux"),
]

# Ссылку открывают снаружи, поэтому абсолютный адрес — всегда публичного
# сервера, даже если ссылку создали на машине администратора.
PUBLIC_BASE = os.environ.get("VPNGUIDE_PUBLIC_BASE", "https://nufarul.eminescu.md").rstrip("/")


def public_url(endpoint: str, **values) -> str:
    return PUBLIC_BASE + url_for(endpoint, **values)


def _private(resp: Response) -> Response:
    """Заголовки для всего, что открывается по токену.

    no-referrer — главное: со страницы есть ссылки на openvpn.net, Apple и
    Google, и без этого заголовка адрес с токеном ушёл бы им в Referer.
    """
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


def _client_ip() -> str:
    fwd = request.headers.get("X-Forwarded-For", "")
    return (fwd.split(",")[0].strip() if fwd else request.remote_addr) or ""


def _open(token: str, kind: str) -> dict:
    from modules.vpnguide import store
    return store.open_share(token, kind, _client_ip(), request.headers.get("User-Agent", ""))


def _gone(state: str):
    lang = rules.lang(request.args.get("lang") or request.accept_languages.best_match(rules.LANGS))
    html = render_template("vpnguide_gone.html", lang=lang, langs=rules.LANGS, t=rules.text)
    return _private(Response(html, status=404 if state == "unknown" else 410, mimetype="text/html"))


@blueprint.route("")
@blueprint.route("/")
def index():
    if not AuthController.is_authenticated():
        return redirect(url_for("login", next=request.full_path))
    return render_template("vpnguide.html", platforms=PLATFORMS)


@blueprint.route("/s/<token>")
def share_page(token):
    s = _open(token, "page")
    if s["state"] != "active":
        return _gone(s["state"])
    lang = rules.lang(request.args.get("lang") or s["lang"])
    name = s["client_name"]
    if s.get("kind") == "smb":
        cfg = rules.smb_settings(s["profile"])
        html = render_template(
            "vpnguide_share_smb.html",
            lang=lang, langs=rules.LANGS, t=rules.text, cfg=cfg, client_name=name,
            expires_local=s["expires_local"], minutes_left=s["minutes_left"],
            cmd_url=url_for("vpnguide.share_cmd", token=token),
            md_url=url_for("vpnguide.share_markdown", token=token))
        return _private(Response(html, mimetype="text/html"))
    if s.get("kind") == "l2tp":
        cfg = rules.l2tp_settings(s["profile"])
        html = render_template(
            "vpnguide_share_l2tp.html",
            lang=lang, langs=rules.LANGS, t=rules.text, cfg=cfg, client_name=name,
            expires_local=s["expires_local"], minutes_left=s["minutes_left"],
            ps1_url=url_for("vpnguide.share_windows", token=token),
            apple_url=url_for("vpnguide.share_apple", token=token),
            md_url=url_for("vpnguide.share_markdown", token=token))
        return _private(Response(html, mimetype="text/html"))
    html = render_template(
        "vpnguide_share.html",
        lang=lang, langs=rules.LANGS, t=rules.text, dl=rules.DOWNLOADS,
        client_name=name, file_name=rules.file_name(name),
        profile=s["profile"], sha256=rules.profile_sha256(s["profile"]),
        expires_local=s["expires_local"], minutes_left=s["minutes_left"],
        profile_url=url_for("vpnguide.share_profile", token=token),
        md_url=url_for("vpnguide.share_markdown", token=token))
    return _private(Response(html, mimetype="text/html"))


@blueprint.route("/s/<token>/profile")
def share_profile(token):
    s = _open(token, "profile")
    if s["state"] != "active":
        return _gone(s["state"])
    if s.get("kind") != "openvpn":
        abort(404)          # у L2TP файла профиля нет — есть .ps1 и .mobileconfig
    name = rules.file_name(s["client_name"])
    return _private(Response(
        s["profile"], mimetype="application/x-openvpn-profile",
        headers={"Content-Disposition": f'attachment; filename="{name}"'}))


@blueprint.route("/s/<token>/instructions.md")
def share_markdown(token):
    s = _open(token, "markdown")
    if s["state"] != "active":
        abort(404 if s["state"] == "unknown" else 410)
    expires = s["expires_local"] + " (Europe/Chisinau)"
    if s.get("kind") == "smb":
        body = rules.markdown_smb(rules.smb_settings(s["profile"]), expires, s["minutes_left"],
                                  public_url("vpnguide.share_cmd", token=token))
    elif s.get("kind") == "l2tp":
        body = rules.markdown_l2tp(
            rules.l2tp_settings(s["profile"]), expires, s["minutes_left"],
            public_url("vpnguide.share_windows", token=token),
            public_url("vpnguide.share_apple", token=token))
    else:
        body = rules.markdown(
            s["client_name"], s["profile"], expires, s["minutes_left"],
            public_url("vpnguide.share_profile", token=token))
    return _private(Response(body, mimetype="text/markdown; charset=utf-8"))


def _l2tp(token: str, kind: str):
    s = _open(token, kind)
    if s["state"] != "active":
        return None, _gone(s["state"])
    if s.get("kind") != "l2tp":
        abort(404)
    return rules.l2tp_settings(s["profile"]), None


@blueprint.route("/s/<token>/windows.ps1")
def share_windows(token):
    """Скрипт PowerShell: создаёт подключение L2TP и сразу подключается."""
    cfg, gone = _l2tp(token, "windows")
    if gone:
        return gone
    # BOM нужен: без него PowerShell 5 читает кириллицу в комментариях как ANSI.
    body = "\ufeff" + rules.powershell(cfg)
    return _private(Response(body.encode("utf-8"), mimetype="text/plain",
                             headers={"Content-Disposition": 'attachment; filename="office-vpn.ps1"'}))


@blueprint.route("/s/<token>/apple.mobileconfig")
def share_apple(token):
    """Профиль конфигурации для macOS и iPhone: L2TP уже настроен."""
    cfg, gone = _l2tp(token, "apple")
    if gone:
        return gone
    return _private(Response(rules.mobileconfig(cfg),
                             mimetype="application/x-apple-aspen-config",
                             headers={"Content-Disposition": 'attachment; filename="office-vpn.mobileconfig"'}))


@blueprint.route("/s/<token>/office-drives.cmd")
def share_cmd(token):
    """Файл .cmd: подключает сотруднику диски его роли."""
    s = _open(token, "cmd")
    if s["state"] != "active":
        return _gone(s["state"])
    if s.get("kind") != "smb":
        abort(404)
    # Без BOM: cmd спотыкается о него в первой строке («@echo» не распознаётся).
    body = rules.smb_cmd(rules.smb_settings(s["profile"])).encode("utf-8")
    return _private(Response(body, mimetype="text/plain",
                             headers={"Content-Disposition": 'attachment; filename="office-drives.cmd"'}))
