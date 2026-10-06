"""Маршруты модуля Мониторинг офиса: сеть и Telegram.

Адреса БЕЗ префикса /UNA.md/orasldev/netmon — его подставляет ядро.
Здесь только разбор запроса и код ответа; логика — в controller.py.
"""
import ipaddress
import os

from flask import abort, jsonify, redirect, render_template, request, session, url_for

from controllers.auth_controller import AuthController
from modules.netmon import blueprint
from modules.netmon.controller import NetmonController

# Откуда модуль вообще отвечает: сама машина, офисная сеть и туннель OpenVPN.
# Переопределяется в .env через NETMON_ALLOWED_NETS (через запятую).
_DEFAULT_NETS = "127.0.0.0/8,::1/128,192.168.0.0/24,10.8.0.0/24"
ALLOWED_NETS = [
    ipaddress.ip_network(n.strip(), strict=False)
    for n in os.environ.get("NETMON_ALLOWED_NETS", _DEFAULT_NETS).split(",")
    if n.strip()
]


def source_allowed(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address((addr or "").split("%")[0])
    except ValueError:
        return False
    return any(ip in net for net in ALLOWED_NETS if ip.version == net.version)


@blueprint.before_request
def _only_from_inside():
    """Вторая линия после флага NETMON_ENABLED — на КАЖДЫЙ маршрут модуля.

    Повешено на blueprint, а не на отдельные маршруты: маршрут, добавленный
    потом, эту проверку не обойдёт. Отвечаем 404, а не 403 — снаружи не
    должно быть видно даже того, что модуль здесь есть.
    """
    if not source_allowed(request.remote_addr):
        abort(404)


def _guard():
    if AuthController.is_authenticated():
        return None
    return jsonify({"success": False, "message": "Требуется вход в систему"}), 401


def _reply(reply):
    payload, status = reply
    return jsonify(payload), status


def _int(name, default=None):
    v = request.args.get(name)
    try:
        return int(v) if v else default
    except (TypeError, ValueError):
        return default


@blueprint.route("")
@blueprint.route("/")
def index():
    if not AuthController.is_authenticated():
        return redirect(url_for("login"))
    return render_template("netmon.html", vpn_guide_url=_vpn_guide_url())


def _vpn_guide_url():
    """Адрес инструкции OpenVPN из соседнего модуля — или None, если его нет.

    Модуль не должен падать из-за отсутствия другого модуля: 04.10.2026
    прямой url_for('vpnguide.index') в шаблоне уронил всю панель с BuildError,
    когда сервер работал без vpnguide.
    """
    from werkzeug.routing import BuildError
    try:
        return url_for("vpnguide.index")
    except BuildError:
        return None


@blueprint.route("/api/status")
def api_status():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.status())


@blueprint.route("/api/overview")
def api_overview():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.overview())


@blueprint.route("/api/devices")
def api_devices():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.devices(
        kind=request.args.get("kind"),
        only_missing=request.args.get("missing") == "1"))


@blueprint.route("/api/channels")
def api_channels():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.channels())


@blueprint.route("/api/alerts")
def api_alerts():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.alerts(
        limit=_int("limit", 100), channel_id=_int("channel"),
        severity=request.args.get("severity")))


@blueprint.route("/api/sync/channels", methods=["POST"])
def api_sync_channels():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.sync_channels())


@blueprint.route("/api/sync/alerts", methods=["POST"])
def api_sync_alerts():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.sync_alerts(days=_int("days", 30)))


@blueprint.route("/api/sync/devices", methods=["POST"])
def api_sync_devices():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.sync_devices(run_by=session.get("username", "system")))


@blueprint.route("/api/sync/all", methods=["POST"])
def api_sync_all():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.sync_all(run_by=session.get("username", "system")))


@blueprint.route("/api/zabbix")
def api_zabbix():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.zabbix_overview())


@blueprint.route("/api/pve")
def api_pve():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.pve_guests(
        status=request.args.get("status"),
        decision=request.args.get("decision"),
        risk=request.args.get("risk")))


@blueprint.route("/api/pve/<int:vmid>")
def api_pve_guest(vmid):
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.pve_guest(vmid))


@blueprint.route("/api/sync/pve", methods=["POST"])
def api_sync_pve():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.sync_pve())


@blueprint.route("/api/assets")
def api_assets():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.assets())


@blueprint.route("/api/vault")
def api_vault():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.vault())


@blueprint.route("/api/sync/assets", methods=["POST"])
def api_sync_assets():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.sync_assets())


@blueprint.route("/api/facilities")
def api_facilities():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.facilities(kind=request.args.get("kind"),
                                              room=request.args.get("room")))


@blueprint.route("/api/facilities/<code>")
def api_facility(code):
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.facility(code))


@blueprint.route("/api/facilities/<code>/work", methods=["POST"])
def api_facility_work(code):
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.add_work(code, request.get_json(silent=True) or {},
                                            user=session.get("username", "system")))


@blueprint.route("/api/facilities/<code>/photo", methods=["POST"])
def api_facility_photo(code):
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.add_photo(
        code, request.files.get("photo"),
        caption=request.form.get("caption", ""),
        user=session.get("username", "system"),
        log_id=request.form.get("log_id", type=int)))


@blueprint.route("/photo/<int:photo_id>")
def photo_file(photo_id):
    """Отдаёт снимок. Файлы лежат вне статики, поэтому только через маршрут."""
    if not AuthController.is_authenticated():
        return redirect(url_for("login"))
    from flask import send_file
    from modules.netmon import store as st
    with_ = [p for f in st.facilities() for p in st.facility_photos(f["id"])
             if p["id"] == photo_id]
    if not with_:
        return jsonify({"success": False, "message": "снимок не найден"}), 404
    return send_file(with_[0]["file_path"])


@blueprint.route("/api/plugs")
def api_plugs():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.plugs())


@blueprint.route("/api/plugs/<ip>/<state>", methods=["POST"])
def api_plug_switch(ip, state):
    if (g := _guard()) is not None:
        return g
    if state not in ("on", "off"):
        return jsonify({"success": False, "message": "состояние: on или off"}), 400
    return _reply(NetmonController.switch_plug(ip, state == "on",
                                               user=session.get("username", "system")))


@blueprint.route("/api/storage")
def api_storage():
    """Диски сервера баз данных: тома RAID, физические диски, заполнение."""
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.storage())


@blueprint.route("/api/vpn")
def api_vpn():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.vpn())


@blueprint.route("/api/vpn/clients", methods=["POST"])
def api_vpn_create():
    if (g := _guard()) is not None:
        return g
    body = request.get_json(silent=True) or {}
    return _reply(NetmonController.vpn_create(
        body.get("name"), user=session.get("username", "system"),
        share_minutes=body.get("share_minutes"), share_lang=body.get("share_lang", "ru")))


@blueprint.route("/api/vpn/clients/<name>/share", methods=["POST"])
def api_vpn_share(name):
    """Ссылка для получателя на уже выданный сертификат (15 минут по умолчанию)."""
    if (g := _guard()) is not None:
        return g
    body = request.get_json(silent=True) or {}
    return _reply(NetmonController.vpn_share(name, body.get("minutes"), body.get("lang", "ru"),
                                             user=session.get("username", "system")))


@blueprint.route("/api/vpn/shares")
def api_vpn_shares():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.vpn_shares())


@blueprint.route("/api/vpn/shares/<int:share_id>/revoke", methods=["POST"])
def api_vpn_share_revoke(share_id):
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.vpn_share_revoke(share_id,
                                                    user=session.get("username", "system")))


@blueprint.route("/api/vpn/clients/<name>/revoke", methods=["POST"])
def api_vpn_revoke(name):
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.vpn_revoke(name, user=session.get("username", "system")))


@blueprint.route("/api/vpn/clients/<name>/profile")
def api_vpn_profile(name):
    """Отдаёт .ovpn УЖЕ выданного сертификата файлом, без нового выпуска.

    Профиль содержит закрытый ключ — не кэшируем. Раньше этот адрес выпускал
    сертификат заново, и повторное скачивание падало с «уже выдан».
    """
    if (g := _guard()) is not None:
        return g
    payload, code = NetmonController.vpn_profile(name)
    if code != 200:
        return jsonify(payload), code
    from flask import Response
    return Response(payload["data"]["profile"], mimetype="application/x-openvpn-profile",
                    headers={"Content-Disposition": f'attachment; filename="{name}.ovpn"',
                             "Cache-Control": "no-store"})


# ------------------------------------------------------------- MikroTik

@blueprint.route("/api/mikrotik")
def api_mikrotik():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.mikrotik())


@blueprint.route("/api/mikrotik/users", methods=["POST"])
def api_mikrotik_create():
    """Новая учётка L2TP/IPsec; share_minutes — сразу ссылка для получателя."""
    if (g := _guard()) is not None:
        return g
    body = request.get_json(silent=True) or {}
    return _reply(NetmonController.mikrotik_create(
        body.get("name"), user=session.get("username", "system"),
        share_minutes=body.get("share_minutes"), share_lang=body.get("share_lang", "ru")))


@blueprint.route("/api/mikrotik/users/<name>/reset", methods=["POST"])
def api_mikrotik_reset(name):
    """Новый пароль и ссылка для получателя (старые ссылки гаснут)."""
    if (g := _guard()) is not None:
        return g
    body = request.get_json(silent=True) or {}
    return _reply(NetmonController.mikrotik_reset(
        name, user=session.get("username", "system"),
        share_minutes=body.get("minutes", 15), share_lang=body.get("lang", "ru")))


@blueprint.route("/api/mikrotik/users/<name>/disable", methods=["POST"])
def api_mikrotik_disable(name):
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.mikrotik_disable(name, True, user=session.get("username", "system")))


@blueprint.route("/api/mikrotik/users/<name>/enable", methods=["POST"])
def api_mikrotik_enable(name):
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.mikrotik_disable(name, False, user=session.get("username", "system")))


# ------------------------------------------------ файловые ресурсы 192.168.0.21

def _who():
    return session.get("username", "system")


@blueprint.route("/api/fs")
def api_fs():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.fs_status())


@blueprint.route("/api/fs/plan")
def api_fs_plan():
    """Пробный расчёт новой политики — ничего не меняет."""
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.fs_plan(request.args.get("mode", "transition")))


@blueprint.route("/api/fs/apply", methods=["POST"])
def api_fs_apply():
    """Применить политику. Требует md5 из пробного расчёта: если smb.conf
    изменился после него, применение отказывает."""
    if (g := _guard()) is not None:
        return g
    body = request.get_json(silent=True) or {}
    if body.get("confirm") != "ПРИМЕНИТЬ":
        return jsonify({"success": False, "message": "нужно подтверждение: confirm = ПРИМЕНИТЬ"}), 400
    return _reply(NetmonController.fs_apply(body.get("mode", ""), body.get("md5", ""), user=_who()))


@blueprint.route("/api/fs/backups")
def api_fs_backups():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.fs_backups())


@blueprint.route("/api/fs/rollback", methods=["POST"])
def api_fs_rollback():
    if (g := _guard()) is not None:
        return g
    body = request.get_json(silent=True) or {}
    return _reply(NetmonController.fs_rollback(body.get("backup", ""), user=_who()))


@blueprint.route("/api/fs/people", methods=["POST"])
def api_fs_add():
    if (g := _guard()) is not None:
        return g
    b = request.get_json(silent=True) or {}
    return _reply(NetmonController.fs_add_person(
        b.get("email"), b.get("full_name"), b.get("role"), user=_who(),
        share_minutes=b.get("share_minutes"), share_lang=b.get("share_lang", "ru")))


@blueprint.route("/api/fs/people/<login>/role", methods=["POST"])
def api_fs_role(login):
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.fs_set_role(login, (request.get_json(silent=True) or {}).get("role"),
                                               user=_who()))


@blueprint.route("/api/fs/people/<login>/disable", methods=["POST"])
def api_fs_disable(login):
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.fs_set_disabled(login, True, user=_who()))


@blueprint.route("/api/fs/people/<login>/enable", methods=["POST"])
def api_fs_enable(login):
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.fs_set_disabled(login, False, user=_who()))


@blueprint.route("/api/fs/people/<login>/reset", methods=["POST"])
def api_fs_reset(login):
    if (g := _guard()) is not None:
        return g
    b = request.get_json(silent=True) or {}
    return _reply(NetmonController.fs_reset(login, user=_who(), share_minutes=b.get("minutes", 15),
                                            share_lang=b.get("lang", "ru")))
