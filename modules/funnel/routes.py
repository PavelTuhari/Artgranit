"""Маршруты панели воронки. Адреса без префикса — его подставляет ядро."""

from flask import jsonify, redirect, render_template, request

from controllers.auth_controller import AuthController
from modules.funnel import blueprint, digest, store


def _guard():
    if AuthController.is_authenticated():
        return None
    return jsonify({"success": False,
                    "message": "Требуется вход в систему"}), 401


@blueprint.route("/")
@blueprint.route("")
def panel():
    if not AuthController.is_authenticated():
        return redirect("/login?next=/UNA.md/orasldev/funnel")
    return render_template("funnel.html")


@blueprint.route("/api/summary")
def api_summary():
    err = _guard()
    if err:
        return err
    days = request.args.get("days", 7, type=int)
    return jsonify({"success": True, "data": store.summary(days)})


@blueprint.route("/api/tops")
def api_tops():
    err = _guard()
    if err:
        return err
    days = request.args.get("days", 30, type=int)
    return jsonify({"success": True, "data": {
        "groups": store.top_groups(days, 10),
        "products": store.top_products(days, 10),
        "stale": store.stale_orders(3, 20),
    }})


@blueprint.route("/api/digest/preview")
def api_digest_preview():
    err = _guard()
    if err:
        return err
    return jsonify({"success": True, "data": {
        "text": digest.compose(),
        "enabled": digest._setting(digest.K_ENABLED, "1") != "0",
        "hour": digest._setting(digest.K_HOUR, str(digest.DEFAULT_HOUR)),
        "last": digest._setting(digest.K_LAST, ""),
    }})


@blueprint.route("/api/digest/send", methods=["POST"])
def api_digest_send():
    err = _guard()
    if err:
        return err
    return jsonify(digest.send_now())


@blueprint.route("/api/digest/settings", methods=["POST"])
def api_digest_settings():
    err = _guard()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    if "enabled" in body:
        digest._set_setting(digest.K_ENABLED, "1" if body["enabled"] else "0")
    if "hour" in body:
        try:
            hour = max(0, min(23, int(body["hour"])))
            digest._set_setting(digest.K_HOUR, str(hour))
        except (TypeError, ValueError):
            pass
    store.clear_cache()
    return jsonify({"success": True})
