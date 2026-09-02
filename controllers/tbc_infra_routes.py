"""TBControl — маршруты инфраструктурных панелей (Proxmox, SSL-сертификаты).

Отдельный Blueprint по правилу №2 CLAUDE.md: в `app.py` остаётся одна
строка регистрации. Маршруты `/api/tbc/services*` исторически объявлены в
`app.py` и там и остались — они лишь вызывают контроллер.
"""
from flask import Blueprint, jsonify, request

from controllers.auth_controller import AuthController
from controllers.tbcontrol_controller import TBControlController

tbc_infra_bp = Blueprint("tbc_infra", __name__)


def _auth_required():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return None


@tbc_infra_bp.route("/api/tbc/proxmox", methods=["GET"])
def api_tbc_proxmox():
    return jsonify(TBControlController.get_proxmox(
        request.args.get("source_code"), request.args.get("obj_type"), request.args.get("health")))


@tbc_infra_bp.route("/api/tbc/proxmox/sync", methods=["POST"])
def api_tbc_proxmox_sync():
    denied = _auth_required()
    if denied:
        return denied
    data = request.get_json(silent=True) or {}
    return jsonify(TBControlController.sync_proxmox(data.get("source_code")))


@tbc_infra_bp.route("/api/tbc/certs", methods=["GET"])
def api_tbc_certs():
    return jsonify(TBControlController.get_certs())


@tbc_infra_bp.route("/api/tbc/certs", methods=["POST"])
def api_tbc_cert_save():
    denied = _auth_required()
    if denied:
        return denied
    return jsonify(TBControlController.save_cert(request.get_json(silent=True) or {}))


@tbc_infra_bp.route("/api/tbc/certs/<int:cert_id>", methods=["DELETE"])
def api_tbc_cert_delete(cert_id):
    denied = _auth_required()
    if denied:
        return denied
    return jsonify(TBControlController.delete_cert(cert_id))


@tbc_infra_bp.route("/api/tbc/certs/check", methods=["POST"])
def api_tbc_certs_check():
    denied = _auth_required()
    if denied:
        return denied
    data = request.get_json(silent=True) or {}
    return jsonify(TBControlController.check_certs(data.get("id")))
