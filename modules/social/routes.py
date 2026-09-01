"""Маршруты панели автопостинга. Префикс подставляет ядро."""

from flask import jsonify, redirect, render_template, request

from controllers.auth_controller import AuthController
from modules.social import blueprint, channels, content, scheduler


def _guard():
    if AuthController.is_authenticated():
        return None
    return jsonify({"success": False, "message": "Требуется вход"}), 401


@blueprint.route("/")
@blueprint.route("")
def panel():
    if not AuthController.is_authenticated():
        return redirect("/login?next=/UNA.md/orasldev/social")
    return render_template("social.html")


@blueprint.route("/api/state")
def api_state():
    err = _guard()
    if err:
        return err
    lang = scheduler._setting(scheduler.K_LANG, "ro") or "ro"
    return jsonify({"success": True, "data": {
        "networks": channels.configured(),
        "enabled": scheduler._setting(scheduler.K_ENABLED, "0") == "1",
        "hour": scheduler._setting(scheduler.K_HOUR, str(scheduler.DEFAULT_HOUR)),
        "lang": lang,
        "last": scheduler._setting(scheduler.K_LAST, ""),
        "preview": (content.today_post(lang) or {}).get("text", ""),
    }})


@blueprint.route("/api/settings", methods=["POST"])
def api_settings():
    err = _guard()
    if err:
        return err
    b = request.get_json(silent=True) or {}
    if "enabled" in b:
        scheduler._set_setting(scheduler.K_ENABLED, "1" if b["enabled"] else "0")
    if "hour" in b:
        try:
            scheduler._set_setting(scheduler.K_HOUR,
                                   str(max(0, min(23, int(b["hour"])))))
        except (TypeError, ValueError):
            pass
    if b.get("lang") in ("ro", "ru"):
        scheduler._set_setting(scheduler.K_LANG, b["lang"])
    return jsonify({"success": True})


@blueprint.route("/api/post", methods=["POST"])
def api_post():
    err = _guard()
    if err:
        return err
    b = request.get_json(silent=True) or {}
    return jsonify(scheduler.post_now(b.get("lang")))
