"""Autopark — маршруты аудиторского отчёта.

Свой файл по правилу №2: общий `routes.py` не трогаем, здесь только
аудит. Адреса без префикса модуля — его подставляет ядро.

Всё закрыто входом. Готовые примеры (сгенерированный набор) лежат в
`docs/Autopark/examples` и отдаются оттуда: файл, который уже собран и
проверен, незачем пересобирать на каждый клик, а книга по боевым данным
строится по запросу — период выбирает пользователь.
"""
from __future__ import annotations

import os

from flask import jsonify, request, send_file, send_from_directory

from controllers.auth_controller import AuthController
from modules.autopark import blueprint
from modules.autopark.audit_controller import AuditController

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
EXAMPLES_DIR = os.path.join(os.path.dirname(os.path.dirname(MODULE_DIR)),
                            "docs", "Autopark", "examples")

DEMO_XLSX = "autopark_audit_demo.xlsx"
DEMO_PDF = "autopark_audit_demo.pdf"


def _guard():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "message": "Требуется авторизация"}), 401
    return None


@blueprint.route("/api/audit", methods=["GET"])
def api_audit():
    """Сводка проверки боевых данных за период."""
    return _guard() or jsonify(AuditController.report(request.args.to_dict()))


@blueprint.route("/api/audit/demo", methods=["GET"])
def api_audit_demo():
    """Сводка по сгенерированному набору вместе с листом самопроверки."""
    return _guard() or jsonify(AuditController.demo_report())


@blueprint.route("/audit/report.xlsx", methods=["GET"])
def audit_workbook():
    """Книга Excel с BI-панелью по боевым данным за выбранный период."""
    denied = _guard()
    if denied:
        return denied
    try:
        path, name = AuditController.workbook(request.args.to_dict())
    except Exception as exc:                        # noqa: BLE001
        return jsonify({"success": False,
                        "message": f"Книга не собрана: {exc}"}), 500
    return send_file(path, as_attachment=True, download_name=name,
                     mimetype="application/vnd.openxmlformats-officedocument."
                              "spreadsheetml.sheet")


@blueprint.route("/audit/demo.xlsx", methods=["GET"])
def audit_demo_xlsx():
    """Готовый пример на сгенерированном наборе — без обращения к Oracle."""
    denied = _guard()
    if denied:
        return denied
    if not os.path.exists(os.path.join(EXAMPLES_DIR, DEMO_XLSX)):
        return jsonify({"success": False, "message":
                        "Пример не собран: запустите autopark_audit.py "
                        "--demo --xlsx"}), 404
    return send_from_directory(EXAMPLES_DIR, DEMO_XLSX, as_attachment=True)


@blueprint.route("/audit/demo.pdf", methods=["GET"])
def audit_demo_pdf():
    """PDF-версия примера — для печати и приложения к акту."""
    denied = _guard()
    if denied:
        return denied
    if not os.path.exists(os.path.join(EXAMPLES_DIR, DEMO_PDF)):
        return jsonify({"success": False, "message": "PDF-пример не собран"}), 404
    return send_from_directory(EXAMPLES_DIR, DEMO_PDF)
